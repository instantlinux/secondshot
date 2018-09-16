FROM python:3.7.0-alpine3.8
MAINTAINER Rich Braun <docker@instantlinux.net>
ARG BUILD_DATE
ARG VCS_REF
LABEL org.label-schema.build-date=$BUILD_DATE \
    org.label-schema.license=LGPL-2.1 \
    org.label-schema.name=secondshot \
    org.label-schema.vcs-ref=$VCS_REF \
    org.label-schema.vcs-url=https://github.com/instantlinux/docker-tools

ENV CRON_HOUR=0,8,16 \
    CRON_MINUTE=30 \
    DBHOST=db00 \
    DBNAME=secondshot \
    DBPORT=3306 \
    DBUSER=bkp \
    DBTYPE=sqlite \
    TZ=UTC

ARG RSNAPSHOT_VERSION=1.4.2-r0
ARG SECONDSHOT_VERSION=0.9.2
ARG RRSYNC_SHA=8c9482dee40c77622e3bde2da3967cc92a0b04e0c0ce3978738410d2dbd3d436

VOLUME /backups /metadata /etc/secondshot/conf.d

COPY requirements.txt /tmp/
RUN apk add --no-cache --update rsnapshot=$RSNAPSHOT_VERSION dcron make \
      tzdata && \
    apk add --no-cache --virtual .fetch-deps gcc libffi-dev musl-dev \
      openssl-dev shadow && \
    pip install -r /tmp/requirements.txt && \
    adduser -s /bin/sh -S -D -G adm secondshot && \
    usermod -o -u 0 secondshot && \
    apk del .fetch-deps && rm -fr /var/cache/apk/* /tmp/*

COPY etc/backup-daily.conf /etc/
COPY . /build/
RUN cd /build && ls -lR && make package && \
    pip install file:///build/dist/secondshot-$SECONDSHOT_VERSION.tar.gz && \
    cp /etc/rsnapshot.conf.default /etc/rsnapshot.conf && \
    patch /etc/rsnapshot.conf /build/etc/rsnapshot.conf.patch && \
    cat /build/etc/rsnapshot.conf.docker >> /etc/rsnapshot.conf && \
    echo "$RRSYNC_SHA  /usr/local/bin/rrsync" > checksum && \
    sha256sum -c checksum && \
    rm -fr /build 

COPY bin/entrypoint.sh /usr/local/bin
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
