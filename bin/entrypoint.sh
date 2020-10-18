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
# this is an example authorized_keys file: distribute to all hosts
no-pty,no-agent-forwarding,no-X11-forwarding,no-port-forwarding,command="/usr/local/bin/rrsync -ro /" $(cat $HOMEDIR/.ssh/id_rsa.pub)
EOF
fi
set +e
# make sure host keys are present, if not already distributed by a
#  more-secure method
for host in "$(secondshot --list-hosts)"; do
    [ $host == $(hostname -s) ] && continue
    if ! grep -q "^$host " $HOMEDIR/.ssh/known_hosts; then
        ssh-keyscan $host | grep rsa >> $HOMEDIR/.ssh/known_hosts
    fi
done
set -e
if [ -s /etc/secondshot/conf.d/backup-daily.conf ]; then
    cp -a /etc/secondshot/conf.d/backup-daily.conf /etc
fi

cat <<EOF >/etc/crontabs/$USER
$CRON_MINUTE $CRON_HOUR * * * /usr/local/bin/cron-secondshot.sh
EOF

crond -L /var/log/cron.log
touch /var/log/secondshot
exec tail -f -n0 /var/log/secondshot
