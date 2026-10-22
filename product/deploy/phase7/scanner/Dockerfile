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

FROM clamav/clamav@sha256:57deb108fc4c72778aa83eafbca7bb7153e28c3f57c005afd38d31f16da86f23
ARG RELEASE_SHA
LABEL org.opencontainers.image.revision=${RELEASE_SHA}
# Preserve the qualified engine/signatures. Fix only its OS shared libraries.
RUN apk add --no-cache --upgrade pcre2=10.49-r0 \
 && rm -f /lib/libz.so* /usr/lib/libz.so*
COPY --from=patched-zlib /out/usr/lib/libz.so* /usr/lib/
COPY --from=patched-zlib /out/usr/share/pilot/zlib-patch.json /usr/share/pilot/zlib-patch.json
