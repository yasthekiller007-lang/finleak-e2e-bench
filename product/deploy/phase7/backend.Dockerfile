ARG PYTHON_IMAGE=python:3.12.15-alpine3.24
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.12.19
FROM alpine:3.24 AS patched-zlib
RUN apk add --no-cache build-base git \
 && git init /source \
 && git -C /source remote add origin https://github.com/madler/zlib.git \
 && git -C /source fetch --depth 1 origin df84af25dc1942490e1d1c899a07619152a46148 \
 && git -C /source checkout --detach FETCH_HEAD \
 && test "$(git -C /source rev-parse HEAD)" = df84af25dc1942490e1d1c899a07619152a46148 \
 && cd /source && ./configure --prefix=/usr --shared \
 && make -j2 && make check && make install DESTDIR=/out \
 && mkdir -p /out/usr/share/pilot \
 && printf '{"profile":"pilot-zlib-patch/1","source_commit":"df84af25dc1942490e1d1c899a07619152a46148","path":"/usr/lib/libz.so.1","library_sha256":"%s"}\n' "$(sha256sum /out/usr/lib/libz.so.1 | cut -d ' ' -f 1)" > /out/usr/share/pilot/zlib-patch.json

FROM ${UV_IMAGE} AS uv
FROM ${PYTHON_IMAGE} AS dependencies
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

FROM ${PYTHON_IMAGE} AS runtime
ARG RELEASE_SHA
LABEL org.opencontainers.image.revision=${RELEASE_SHA}
RUN rm -f /lib/libz.so* /usr/lib/libz.so*
COPY --from=patched-zlib /out/usr/lib/libz.so* /usr/lib/
COPY --from=patched-zlib /out/usr/share/pilot/zlib-patch.json /usr/share/pilot/zlib-patch.json
ENV PATH=/app/.venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 FLA_ENVIRONMENT=production FLA_RELEASE_SHA=${RELEASE_SHA}
RUN apk add --no-cache libseccomp=2.6.1-r0
RUN addgroup -g 10001 app && adduser -D -H -u 10001 -G app app
WORKDIR /app
COPY --from=dependencies /app/.venv /app/.venv
COPY backend/app /app/app
COPY backend/migrations /app/migrations
COPY backend/alembic.ini /app/alembic.ini
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["python", "-m", "app.operations.runtime"]
CMD ["serve"]
