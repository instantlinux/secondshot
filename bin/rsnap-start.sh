#! /bin/bash
# $Id: rsnap-start.sh,v 1.5 2013/03/25 02:33:59 root Exp $

. /etc/default/source.sh
HOST=$1
VOLUME=$2
SAVESET="$HOST-$VOLUME-`date +%Y%m%d-%H`"

DBHOST=node2
DBPORT=18306
DBNAME=rsnap
DBUSER=$BKP_USER
PATHNAME=/var/backup/daily/hourly.0
HOST_ID=`mysql -N -h $DBHOST -P $DBPORT -u $DBUSER -p$BKP_PASSWD $DBNAME -e "SELECT id FROM hosts WHERE hostname='$HOST';"`
BKPHOST=`hostname -s`

if [ "$HOST_ID" == "" ]; then
  echo "Error: hostname $HOST not present in database"
  il_syslog err "Error: hostname $HOST not present in database"
  il_syslog info ABORTED
  exit 1
fi

BKPHOST_ID=`mysql -N -h $DBHOST -P $DBPORT -u $DBUSER -p$BKP_PASSWD $DBNAME -e "SELECT id FROM hosts WHERE hostname='$BKPHOST';"`
SAVESET_ID=`mysql -N -h $DBHOST -P $DBPORT -u $DBUSER -p$BKP_PASSWD $DBNAME -e "INSERT INTO savesets (saveset,location,host_id,backup_host_id) VALUES ('$SAVESET','.sync','$HOST_ID','$BKPHOST_ID'); SELECT LAST_INSERT_ID();"`
VOLUME_ID=`mysql -N -h $DBHOST -P $DBPORT -u $DBUSER -p$BKP_PASSWD $DBNAME -e "SELECT id FROM volumes WHERE volume='$VOLUME';"`

if [ "$SAVESET_ID" == "" ] || [ "$VOLUME_ID" == "" ]; then
  echo "Error:  database access failure"
  il_syslog err "Database access failure"
  il_syslog info ABORTED
  exit 1
fi

il_syslog info "START $SAVESET"
echo $SAVESET_ID
exit 0
