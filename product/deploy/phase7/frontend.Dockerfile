ARG NODE_IMAGE=node:24.21.0-alpine3.24
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

FROM ${NODE_IMAGE} AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/next.config.ts frontend/tsconfig.json ./
COPY frontend/src ./src
RUN npm run build

FROM ${NODE_IMAGE} AS runtime
ARG RELEASE_SHA
LABEL org.opencontainers.image.revision=${RELEASE_SHA}
RUN rm -f /lib/libz.so* /usr/lib/libz.so*
COPY --from=patched-zlib /out/usr/lib/libz.so* /usr/lib/
COPY --from=patched-zlib /out/usr/share/pilot/zlib-patch.json /usr/share/pilot/zlib-patch.json
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000 FLA_RELEASE_SHA=${RELEASE_SHA}
RUN rm -rf /usr/local/lib/node_modules/npm /opt/yarn* /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/yarn /usr/local/bin/yarnpkg
WORKDIR /app
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY deploy/phase7/frontend-entrypoint.cjs ./frontend-entrypoint.cjs
USER node
EXPOSE 3000
CMD ["node", "frontend-entrypoint.cjs"]
