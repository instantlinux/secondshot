#!/bin/sh -e

MINUTE=30
HOUR=0,8,16

cat <<EOF >/etc/crontabs/root
$MINUTE $HOUR * * * /usr/local/bin/cron-secondshot
EOF
crond -L /var/log/cron.log
tail -f -n0 /var/log/cron.log

