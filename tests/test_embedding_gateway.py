from __future__ import annotations

import json

import httpx
import pytest
import respx

from pharma_intel.config import Settings
from pharma_intel.search.embedding import (
    EmbeddingGatewayError,
    OpenAICompatibleEmbeddingGateway,
    _validate_vector,
)


@respx.mock
def test_embedding_gateway_validates_and_orders_openai_compatible_response() -> None:
    route = respx.post("https://model.test/v1/embeddings").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0, 1, 0]},
                    {"index": 0, "embedding": [1, 0, 0]},
                ],
                "model": "provider-alias",
            },
        )
    )
    gateway = OpenAICompatibleEmbeddingGateway(
        Settings(
            _env_file=None,
            search_embedding_base_url="https://model.test/v1",
            search_embedding_api_key="embedding-secret",
            search_embedding_model="approved-embedding-v1",
            search_embedding_dimensions=3,
        )
    )

    vectors = gateway.embed(["EGFR", "C797S"])

    assert vectors == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    request = route.calls.last.request
    assert request.headers["authorization"] == "Bearer embedding-secret"
    assert json.loads(request.content) == {
        "model": "approved-embedding-v1",
        "input": ["EGFR", "C797S"],
        "encoding_format": "float",
    }


@pytest.mark.parametrize(
    "data",
    [
        [{"index": 0, "embedding": [1.0, 2.0]}],
        [{"index": 0, "embedding": [1.0, "invalid", 3.0]}],
        [{"index": 0, "embedding": [1.0, 2.0, 3.0]}, {"index": 0, "embedding": [3.0, 2.0, 1.0]}],
    ],
)
@respx.mock
def test_embedding_gateway_rejects_untrusted_response_shapes(data: list[dict[str, object]]) -> None:
    respx.post("https://model.test/v1/embeddings").mock(return_value=httpx.Response(200, json={"data": data}))
    gateway = OpenAICompatibleEmbeddingGateway(
        Settings(
            _env_file=None,
            search_embedding_base_url="https://model.test",
            search_embedding_api_key="secret",
            search_embedding_model="approved-embedding-v1",
            search_embedding_dimensions=3,
        )
    )

    with pytest.raises(EmbeddingGatewayError, match="failed validation"):
        gateway.embed(["first"] if len(data) == 1 else ["first", "second"])


@respx.mock
def test_embedding_gateway_retries_bounded_transient_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    route = respx.post("https://model.test/v1/embeddings").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0, 0.0, 0.0]}]}),
        ]
    )
    monkeypatch.setattr("pharma_intel.search.embedding.time.sleep", lambda _seconds: None)
    gateway = OpenAICompatibleEmbeddingGateway(
        Settings(
            _env_file=None,
            search_embedding_base_url="https://model.test",
            search_embedding_api_key="secret",
            search_embedding_model="approved-embedding-v1",
            search_embedding_dimensions=3,
            search_embedding_max_retries=1,
        )
    )

    assert gateway.embed(["EGFR"]) == [[1.0, 0.0, 0.0]]
    assert route.call_count == 2


def test_embedding_gateway_rejects_invalid_configuration_and_inputs() -> None:
    with pytest.raises(EmbeddingGatewayError, match="HTTPS remote API root"):
        OpenAICompatibleEmbeddingGateway(
            Settings(
                _env_file=None,
                search_embedding_base_url="file:///model",
                search_embedding_api_key="secret",
                search_embedding_model="approved-embedding-v1",
            )
        )
    with pytest.raises(EmbeddingGatewayError, match="embedding API key"):
        OpenAICompatibleEmbeddingGateway(
            Settings(
                _env_file=None,
                search_embedding_base_url="https://model.test",
                search_embedding_api_key="",
                search_embedding_model="approved-embedding-v1",
            )
        )
    gateway = OpenAICompatibleEmbeddingGateway(
        Settings(
            _env_file=None,
            search_embedding_base_url="https://model.test",
            search_embedding_api_key="secret",
            search_embedding_model="approved-embedding-v1",
            search_embedding_batch_size=1,
            search_embedding_max_input_chars=256,
        )
    )
    with pytest.raises(EmbeddingGatewayError, match="batch"):
        gateway.embed(["one", "two"])
    with pytest.raises(EmbeddingGatewayError, match="empty"):
        gateway.embed([" "])
    with pytest.raises(EmbeddingGatewayError, match="character limit"):
        gateway.embed(["x" * 257])
    with pytest.raises(ValueError, match="non-finite"):
        _validate_vector([1.0, float("nan"), 3.0], 3)
    with pytest.raises(ValueError, match="zero vector"):
        _validate_vector([0.0, 0.0, 0.0], 3)


@respx.mock
def test_embedding_gateway_normalizes_non_retryable_http_errors_without_retrying() -> None:
    route = respx.post("https://model.test/v1/embeddings").mock(return_value=httpx.Response(403, text="denied"))
    gateway = OpenAICompatibleEmbeddingGateway(
        Settings(
            _env_file=None,
            search_embedding_base_url="https://model.test",
            search_embedding_api_key="secret",
            search_embedding_model="approved-embedding-v1",
            search_embedding_max_retries=3,
        )
    )

    with pytest.raises(EmbeddingGatewayError, match="status 403") as caught:
        gateway.embed(["EGFR"])

    assert route.call_count == 1
    assert "secret" not in str(caught.value)
