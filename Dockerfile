FROM python:3.11.4-alpine3.18
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
    PYTHONPATH=/usr/lib/python3.8/site-packages \
    TZ=UTC

ARG RSNAPSHOT_VERSION=1.4.5-r0
ARG SECONDSHOT_VERSION=0.10.5
ARG RRSYNC_SHA=292468318c71c1817df2077558788256ed00a259ee6a1fc5a64d47bc28ab34bd

VOLUME /backups /metadata /etc/secondshot/conf.d

COPY requirements.txt /tmp/
RUN apk add --no-cache --update rsnapshot=$RSNAPSHOT_VERSION dcron make \
      patch py3-cryptography py3-six py3-urllib3 shadow tzdata && \
    pip install -r /tmp/requirements.txt && \
    adduser -s /bin/sh -S -D -G adm secondshot && \
    usermod -o -u 0 secondshot && \
    rm -fr /var/cache/apk/* /tmp/*

COPY etc/backup-daily.conf /etc/
COPY . /build/
RUN cd /build && make package && \
    pip install file:///build/dist/secondshot-$SECONDSHOT_VERSION.tar.gz && \
    cp /etc/rsnapshot.conf.default /etc/rsnapshot.conf && \
    patch /etc/rsnapshot.conf /build/etc/rsnapshot.conf.patch && \
    cat /build/etc/rsnapshot.conf.docker >> /etc/rsnapshot.conf && \
    echo "$RRSYNC_SHA  /usr/local/bin/rrsync" > checksum && \
    sha256sum -c checksum && \
    rm -fr /build 

COPY bin/entrypoint.sh /usr/local/bin
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
