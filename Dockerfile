FROM python:3.7.0-alpine3.8
MAINTAINER Rich Braun <docker@instantlinux.net>
ARG BUILD_DATE
ARG VCS_REF
LABEL org.label-schema.build-date=$BUILD_DATE \
    org.label-schema.license=LGPL-2.1 \
    org.label-schema.name=secondshot \
    org.label-schema.vcs-ref=$VCS_REF \
    org.label-schema.vcs-url=https://github.com/instantlinux/docker-tools

ARG RSNAPSHOT_VERSION=1.4.2-r0
ENV TZ=UTC

COPY . /build
RUN apk add --no-cache --update rsnapshot=$RSNAPSHOT_VERSION dcron && \
    cd /build && make package && \
    pip install mypackage --no-index --find-links file:///build/dist/*.whl

COPY entrypoint.sh /usr/local/bin
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
