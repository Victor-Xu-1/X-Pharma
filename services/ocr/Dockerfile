ARG DOCKER_LIBRARY_REGISTRY=public.ecr.aws/docker/library
FROM ${DOCKER_LIBRARY_REGISTRY}/python:3.13.16-slim@sha256:bf44cdfcb76cd3b41e879bc058fc37ec5872002ccfde7fcb765e218cde0cd79c

ARG OCR_PYPI_INDEX_URL=https://pypi.org/simple

ENV PIP_DEFAULT_TIMEOUT=300 \
    PIP_RETRIES=3 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_INDEX_URL=${OCR_PYPI_INDEX_URL}

COPY deploy/security/debian13-runtime-packages.lock /tmp/security-packages.lock
COPY deploy/security/install-runtime-security-packages.sh /tmp/install-security-packages.sh
RUN bash /tmp/install-security-packages.sh /tmp/security-packages.lock \
    && rm -f /tmp/security-packages.lock /tmp/install-security-packages.sh

RUN apt-get update \
    && apt-get install --yes --no-install-recommends libgl1 libglib2.0-0t64 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY scripts/verify_cpython_tarfile.py scripts/verify_cpython_tls.py scripts/verify_cpython_html.py /tmp/cpython-probes/
RUN python /tmp/cpython-probes/verify_cpython_tarfile.py \
    && python /tmp/cpython-probes/verify_cpython_tls.py \
    && python /tmp/cpython-probes/verify_cpython_html.py \
    && rm -rf /tmp/cpython-probes

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
