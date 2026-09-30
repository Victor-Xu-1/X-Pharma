FROM public.ecr.aws/docker/library/python:3.13.14-slim@sha256:6771159cd4fa5d9bba1258caf0b82e6b73458c694d178ad97c5e925c2d0e1a91

ARG OCR_PYPI_INDEX_URL=https://pypi.org/simple
ARG CPYTHON_HTML_PARSER_COMMIT=7933f4bf7131aa4140750f9404f5de0aa2969ced
ARG CPYTHON_HTML_PARSER_SHA256=4274e9112adf3fa57c7f9afa7c9b5c631456b18b7403cc627cc5027d02cdd2ae
ARG CPYTHON_TARFILE_COMMIT=771d12dda5140313db0ac550292987975651bbde
ARG CPYTHON_TARFILE_SHA256=0ad8c3869f9ab172fc5fc539528eb94c44d0745aef15dc8a0f1a773fae3b6c52
LABEL io.pharma.cpython-html-parser-commit=${CPYTHON_HTML_PARSER_COMMIT} \
      io.pharma.cpython-tarfile-commit=${CPYTHON_TARFILE_COMMIT}

ENV PIP_DEFAULT_TIMEOUT=300 \
    PIP_RETRIES=3 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_INDEX_URL=${OCR_PYPI_INDEX_URL}

RUN apt-get update \
    && apt-get install --yes --no-install-recommends libgl1 libglib2.0-0t64 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY deploy/cpython/html-parser.py /tmp/cpython-html-parser.py
COPY deploy/cpython/tarfile.py /tmp/cpython-tarfile.py
RUN echo "${CPYTHON_HTML_PARSER_SHA256}  /tmp/cpython-html-parser.py" | sha256sum --check --strict \
    && install -m 0644 /tmp/cpython-html-parser.py /usr/local/lib/python3.13/html/parser.py \
    && rm -f /tmp/cpython-html-parser.py \
    && rm -f /usr/local/lib/python3.13/html/__pycache__/parser.*.pyc \
    && python -c "from html.parser import HTMLParser; p=HTMLParser(); p.feed('<!--'); [p.feed('a' * 64) for _ in range(200000)]; p.feed('-->'); p.close()"
RUN echo "${CPYTHON_TARFILE_SHA256}  /tmp/cpython-tarfile.py" | sha256sum --check --strict \
    && install -m 0644 /tmp/cpython-tarfile.py /usr/local/lib/python3.13/tarfile.py \
    && rm -f /tmp/cpython-tarfile.py \
    && rm -f /usr/local/lib/python3.13/__pycache__/tarfile.*.pyc \
    && python -c "import inspect, tarfile; assert 'if not data:' in inspect.getsource(tarfile._Stream.seek); assert 'unfiltered.replace(name=tarinfo.name' in inspect.getsource(tarfile.TarFile.makelink_with_filter)"

WORKDIR /service
COPY services/ocr/requirements.lock ./requirements.lock
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    python -m pip install --require-hashes -r requirements.lock

RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app
COPY --chown=app:app services/ocr/service.py ./service.py

ENV HOME=/tmp/ocr-home \
    PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True \
    PYTHONUNBUFFERED=1
USER 10001:10001
EXPOSE 8071
ENTRYPOINT ["python", "/service/service.py"]
