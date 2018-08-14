#!/bin/sh -e

if [ ! -f /etc/timezone ] && [ ! -z "$TZ" ]; then
  # At first startup, set timezone
  cp /usr/share/zoneinfo/$TZ /etc/localtime
  echo $TZ >/etc/timezone
fi

MINUTE=30
HOUR=0,8,16

cat <<EOF >/etc/crontabs/root
$MINUTE $HOUR * * * /usr/local/bin/cron-secondshot.sh
EOF
touch /var/log/cron.log
crond -L /var/log/cron.log
exec tail -f -n0 /var/log/cron.log

