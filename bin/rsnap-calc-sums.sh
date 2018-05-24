#! /bin/bash
# $Id: rsnap-calc-sums.sh,v 1.4 2013/03/27 05:21:24 root Exp $

# Arguments
#  $1    snapshot root path e.g. /var/backup/daily
#  $2    saveset name or numeric ID

# TODO: deal with special filenames (back-ticks, apostrophes)

. /etc/default/source.sh
PATHNAME=$1
SAVESET=$2

DBHOST=node2
DBPORT=18306
DBNAME=rsnap
DBUSER=$BKP_USER
[ "$SAVESET" -eq "$SAVESET" ] 2> /dev/null
if [ $? == 0 ]; then
 # Numeric ID specified, find the saveset name
 SAVESET_ID=$SAVESET
 SAVESET=`mysql -N -h $DBHOST -P $DBPORT -u $DBUSER -p$BKP_PASSWD $DBNAME -e "SELECT saveset FROM savesets WHERE id='$SAVESET_ID'"`
else
 SAVESET_ID=`mysql -N -h $DBHOST -P $DBPORT -u $DBUSER -p$BKP_PASSWD $DBNAME -e "SELECT id FROM savesets WHERE saveset='$SAVESET'"`
fi

if [ "$SAVESET" == "" ] || [ "$SAVESET_ID" == "" ]; then
  echo "Error:  database access failure"
  il_syslog err "Database access failure"
  il_syslog info ABORTED
  exit 1
fi

HOST=`mysql -N -h $DBHOST -P $DBPORT -u $DBUSER -p$BKP_PASSWD $DBNAME -e "SELECT hostname FROM savesets JOIN hosts ON savesets.host_id=hosts.id WHERE savesets.id=$SAVESET_ID"`
LOCATION=`mysql -N -h $DBHOST -P $DBPORT -u $DBUSER -p$BKP_PASSWD $DBNAME -e "SELECT location FROM savesets WHERE savesets.id=$SAVESET_ID"`

if [ "$LOCATION" == "" ] || [ "$HOST" == "" ]; then
  echo "Error:  database access failure"
  il_syslog err "Database access failure"
  il_syslog info ABORTED
  exit 1
fi

il_syslog info "START - saveset $SAVESET"

renice +10 -p $$ >/dev/null
SQL_Q=/tmp/sqlquery.$$

mysql --raw -N -h $DBHOST -P $DBPORT -u $DBUSER -p$BKP_PASSWD $DBNAME <<EOT >$SQL_Q
SELECT 'MYSQL="mysql -h $DBHOST -P $DBPORT -u $DBUSER -p$BKP_PASSWD $DBNAME"';
SELECT CONCAT('SUM=\`sha256sum ',QUOTE(SUBSTRING(path,2)),'/',QUOTE(filename),'|cut -d" " -f 1\`\n',
 "[ \$? == 0 ] && \$MYSQL -e \"UPDATE files SET sha256sum='\$SUM' WHERE id=",files.id,';"')
 FROM backups
 JOIN files ON backups.file_id=files.id
 WHERE files.size>0 AND files.type='f' AND files.sha256sum IS NULL AND backups.saveset_id=$SAVESET_ID
 AND filename NOT LIKE '%\`%';
EOT
if [ $? != 0 ]; then
  il_syslog err "Query failed for saveset contents"
  il_syslog info ABORT
  exit 1
fi

cd $PATHNAME/$LOCATION/$HOST
NUMFILES=$((( `wc -l $SQL_Q|cut -d" " -f 1` - 1 ) / 2 ))
GBTOTAL=`mysql -N -h $DBHOST -P $DBPORT -u $DBUSER -p$BKP_PASSWD $DBNAME -e "SELECT CONCAT(ROUND(SUM(size)/1e9,2)) FROM files JOIN backups ON backups.file_id=files.id WHERE saveset_id=$SAVESET_ID;"`
GBNEW=`mysql -N -h $DBHOST -P $DBPORT -u $DBUSER -p$BKP_PASSWD $DBNAME -e "SELECT CONCAT(ROUND(SUM(size)/1e9,3)) FROM files JOIN backups ON backups.file_id=files.id WHERE saveset_id=$SAVESET_ID AND size>0 AND type='f' AND sha256sum IS NULL;"`
il_syslog info " - running checksums for $NUMFILES files ($GBNEW/${GBTOTAL}GB) from $HOST for $LOCATION"
bash $SQL_Q
rm $SQL_Q

il_syslog info FINISHED
exit 0
