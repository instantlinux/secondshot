#!/bin/sh -e

if [ ! -f /etc/timezone ] && [ ! -z "$TZ" ]; then
  # At first startup, set timezone
  cp /usr/share/zoneinfo/$TZ /etc/localtime
  echo $TZ >/etc/timezone
fi

sed -i -e "s/{{ DBHOST }}/$DBHOST/" \
    -e "s/{{ DBNAME }}/$DBNAME/" \
    -e "s/{{ DBPORT }}/$DBPORT/" \
    -e "s/{{ DBUSER }}/$DBUSER/" \
    -e "s/{{ DBTYPE }}/$DBTYPE/" \
    /usr/local/bin/cron-secondshot.sh

USER=secondshot
HOMEDIR=/home/$USER
RSYNC_USER=$USER
SSHKEY=secondshot-rsync-sshkey

cp /run/secrets/$SSHKEY /run/$SSHKEY && chmod 400 /run/$SSHKEY
if [ ! -s $HOMEDIR/.ssh/config ]; then
    mkdir -p $HOMEDIR/.ssh
    chmod 700 $HOMEDIR/.ssh
    cat <<EOF >$HOMEDIR/.ssh/config
      Host *
      IdentityFile /run/$SSHKEY
      User $RSYNC_USER
EOF
fi
if [ ! -s $HOMEDIR/.ssh/authorized_keys ]; then
    cat <<EOF >>$HOMEDIR/.ssh/authorized_keys
no-pty,no-agent-forwarding,no-X11-forwarding,no-port-forwarding,command="/usr/local/bin/rrsync -ro /" $(cat $HOMEDIR/.ssh/id_rsa.pub)
EOF
fi
if [ -s /etc/secondshot/conf.d/backup-daily.conf ]; then
    cp -a /etc/secondshot/conf.d/backup-daily.conf /etc
fi

cat <<EOF >/etc/crontabs/$USER
$CRON_MINUTE $CRON_HOUR * * * /usr/local/bin/cron-secondshot.sh
EOF

touch /var/log/cron.log
crond -L /var/log/cron.log
exec tail -f -n0 /var/log/cron.log

