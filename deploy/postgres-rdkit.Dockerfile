ARG POSTGRES_IMAGE=public.ecr.aws/docker/library/postgres:18.4-trixie@sha256:a02db8cac496f15b094798a38254f14d6e00741f709360e5e00bb6668ea31636

FROM ${POSTGRES_IMAGE} AS rdkit-builder

ARG RDKIT_TAG=Release_2026_03_3
ARG RDKIT_SOURCE_SHA256=21e22e5e6b3a313527256fbde41c757f22d834b19caf2908e3c2dd11061e1fea
ARG CATCH2_TAG=v3.4.0
ARG CATCH2_SOURCE_SHA256=122928b814b75717316c71af69bd2b43387643ba076a6ec16e7882bfb2dfacbb
ARG BETTER_ENUMS_COMMIT=c35576bed0295689540b39873126129adfa0b4c8
ARG BETTER_ENUMS_SOURCE_SHA256=9b78dcef7f88d1345b6f25335bfbcba5f024b08990c7d6dc605b833f4128b8dd
ARG APT_HTTP_PROXY

USER root

RUN rm -f /etc/apt/apt.conf.d/docker-clean \
    && if [ -n "${APT_HTTP_PROXY}" ]; then \
        printf 'Acquire::http::Proxy "%s";\n' "${APT_HTTP_PROXY}" > /etc/apt/apt.conf.d/99pharma-build-proxy; \
    fi \
    && timeout --foreground --signal=TERM --kill-after=15s 600s \
        apt-get -o APT::Update::Error-Mode=any -o Acquire::Retries=3 \
        -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 update \
    && DEBIAN_FRONTEND=noninteractive timeout --foreground --signal=TERM --kill-after=15s 600s apt-get \
        -o Acquire::Retries=3 \
        -o Acquire::http::Timeout=30 \
        -o Acquire::https::Timeout=30 \
        install --yes --no-install-recommends \
        build-essential \
        ca-certificates \
        cmake \
        curl \
        git \
        libboost-all-dev \
        libeigen3-dev \
        ninja-build \
        postgresql-server-dev-18 \
    && rm -f /etc/apt/apt.conf.d/99pharma-build-proxy \
    && rm -rf /var/lib/apt/lists/*

# RDKit declares Catch2 and better-enums through CMake FetchContent even when
# its own test targets are disabled. Materialize verified archives first so
# the build does not perform mutable or retry-dependent Git clones.
WORKDIR /tmp/rdkit

RUN mkdir -p /tmp/deps/catch2 /tmp/deps/better-enums \
    && curl --fail --location --retry 5 --retry-all-errors \
        --connect-timeout 30 --max-time 1800 \
        "https://github.com/rdkit/rdkit/archive/refs/tags/${RDKIT_TAG}.tar.gz" \
        --output /tmp/rdkit-source.tar.gz \
    && curl --fail --location --retry 5 --retry-all-errors \
        --connect-timeout 30 --max-time 300 \
        "https://github.com/catchorg/Catch2/archive/refs/tags/${CATCH2_TAG}.tar.gz" \
        --output /tmp/catch2-source.tar.gz \
    && curl --fail --location --retry 5 --retry-all-errors \
        --connect-timeout 30 --max-time 300 \
        "https://github.com/aantron/better-enums/archive/${BETTER_ENUMS_COMMIT}.tar.gz" \
        --output /tmp/better-enums-source.tar.gz \
    && echo "${RDKIT_SOURCE_SHA256}  /tmp/rdkit-source.tar.gz" | sha256sum --check --strict \
    && echo "${CATCH2_SOURCE_SHA256}  /tmp/catch2-source.tar.gz" | sha256sum --check --strict \
    && echo "${BETTER_ENUMS_SOURCE_SHA256}  /tmp/better-enums-source.tar.gz" | sha256sum --check --strict \
    && tar --extract --gzip --file /tmp/rdkit-source.tar.gz --strip-components=1 \
    && tar --extract --gzip --file /tmp/catch2-source.tar.gz \
        --strip-components=1 --directory=/tmp/deps/catch2 \
    && tar --extract --gzip --file /tmp/better-enums-source.tar.gz \
        --strip-components=1 --directory=/tmp/deps/better-enums \
    && rm /tmp/rdkit-source.tar.gz /tmp/catch2-source.tar.gz /tmp/better-enums-source.tar.gz

RUN --mount=type=cache,id=rdkit-2026-03-3-build,target=/tmp/rdkit-build \
    cmake -S /tmp/rdkit -B /tmp/rdkit-build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
        -DBUILD_TESTING=OFF \
        -DRDK_BUILD_AVALON_SUPPORT=OFF \
        -DRDK_BUILD_CAIRO_SUPPORT=OFF \
        -DRDK_BUILD_CHEMDRAW_SUPPORT=OFF \
        -DRDK_BUILD_COORDGEN_SUPPORT=OFF \
        -DRDK_BUILD_CPP_TESTS=OFF \
        -DRDK_BUILD_DESCRIPTORS3D=OFF \
        -DRDK_BUILD_FREETYPE_SUPPORT=OFF \
        -DRDK_BUILD_INCHI_SUPPORT=OFF \
        -DRDK_BUILD_MAEPARSER_SUPPORT=OFF \
        -DRDK_BUILD_MOLINTERCHANGE_SUPPORT=OFF \
        -DRDK_BUILD_PGSQL=ON \
        -DRDK_BUILD_PUBCHEMSHAPE_SUPPORT=OFF \
        -DRDK_BUILD_PYTHON_WRAPPERS=OFF \
        -DRDK_BUILD_YAEHMOP_SUPPORT=OFF \
        -DRDK_INSTALL_DEV_COMPONENT=OFF \
        -DRDK_INSTALL_INTREE=OFF \
        -DRDK_INSTALL_STATIC_LIBS=ON \
        -DRDK_PGSQL_STATIC=ON \
        -DRDK_USE_BOOST_IOSTREAMS=OFF \
        -DRDK_USE_BOOST_SERIALIZATION=OFF \
        -DRDK_USE_BOOST_STACKTRACE=OFF \
        -DRDK_USE_URF=OFF \
        -DFETCHCONTENT_SOURCE_DIR_CATCH2=/tmp/deps/catch2 \
        -DFETCHCONTENT_SOURCE_DIR_BETTER_ENUMS=/tmp/deps/better-enums \
        -DPostgreSQL_CONFIG=/usr/bin/pg_config \
        -DPostgreSQL_TYPE_INCLUDE_DIR=/usr/include/postgresql/18/server \
    && cmake --build /tmp/rdkit-build --target rdkit --parallel 4 \
    && DESTDIR=/tmp/rdkit-stage cmake --install /tmp/rdkit-build --component pgsql

FROM ${POSTGRES_IMAGE}

ARG RDKIT_TAG=Release_2026_03_3

LABEL org.opencontainers.image.title="Pharma PostgreSQL with RDKit" \
      org.opencontainers.image.description="PostgreSQL 18.4 with a source-verified RDKit cartridge" \
      org.opencontainers.image.source="https://github.com/rdkit/rdkit" \
      org.opencontainers.image.version="${RDKIT_TAG}"

USER root

COPY --from=rdkit-builder /tmp/rdkit-stage/ /
COPY deploy/security/debian13-runtime-packages.lock /tmp/security-packages.lock
COPY deploy/security/install-runtime-security-packages.sh /tmp/install-security-packages.sh
RUN bash /tmp/install-security-packages.sh /tmp/security-packages.lock \
    && rm -f /tmp/security-packages.lock /tmp/install-security-packages.sh \
    && rm -rf /var/lib/apt/lists/*

RUN ldconfig \
    && test -f /usr/lib/postgresql/18/lib/rdkit.so \
    && test -f /usr/share/postgresql/18/extension/rdkit.control \
    && ! ldd /usr/lib/postgresql/18/lib/rdkit.so | grep -q "not found" \
    && sed -i 's/exec gosu postgres /exec setpriv --reuid=postgres --regid=postgres --init-groups /' \
        /usr/local/bin/docker-entrypoint.sh \
    && grep -Fq 'exec setpriv --reuid=postgres --regid=postgres --init-groups' \
        /usr/local/bin/docker-entrypoint.sh \
    && rm -f /usr/local/bin/gosu

USER postgres
