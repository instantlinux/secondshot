#! /bin/bash
# $Id: rsnap-inject.sh,v 1.4 2013/03/25 02:34:31 root Exp root $

. /etc/default/source.sh
HOST=$1
VOLUME=$2
PATHNAME=$3
SAVESET_ID=$4

DBHOST=db01
DBNAME=rsnap
DBUSER=$BKP_USER
HOST_ID=`mysql -N -h $DBHOST -u $DBUSER -p$BKP_PASSWD $DBNAME -e "SELECT id FROM hosts WHERE hostname='$HOST';"`
VOLUME_ID=`mysql -N -h $DBHOST -u $DBUSER -p$BKP_PASSWD $DBNAME -e "SELECT id FROM volumes WHERE volume='$VOLUME';"`

if [ "$HOST_ID" == "" ] || [ "$SAVESET_ID" == "" ] || [ "$VOLUME_ID" == "" ]; then
  echo "Error:  database access failure"
  il_syslog err "Database access failure"
  il_syslog info ABORTED
  exit 1
fi

SQL_INSERT=/tmp/sqlinsert.$$

cd $PATHNAME/$HOST
find . -not -path "*'*" -printf "INSERT INTO files (path,filename,uid,gid,mode,size,ctime,mtime,type,links,sparseness,host_id) VALUES(SUBSTRING('%h',2),'%f',%U,%G,%m,%s,'%C+','%T+','%y',%n,%S,$HOST_ID) ON DUPLICATE KEY UPDATE owner='%u',grp='%g',id=LAST_INSERT_ID(id),last_backup=NOW();\nINSERT INTO backups (saveset_id,volume_id,file_id) VALUES($SAVESET_ID,$VOLUME_ID,LAST_INSERT_ID());\n" > $SQL_INSERT

mysql -h $DBHOST -u $DBUSER -p$BKP_PASSWD $DBNAME 2>&1 >/tmp/sqlinsert.msg < $SQL_INSERT
if [ $? != 0 ]; then
  echo "Error: MySQL insertion failure"
  il_syslog err "MySQL insertion failure"
  mv $SQL_INSERT /tmp/sqlinsert.lastfailure
  exit 1
fi

mysql -h $DBHOST -u $DBUSER -p$BKP_PASSWD $DBNAME -e "UPDATE savesets SET finished=NOW() WHERE id=$SAVESET_ID;"
COUNT=`mysql -N -h $DBHOST -u $DBUSER -p$BKP_PASSWD $DBNAME -e "SELECT count(*) FROM backups WHERE saveset_id='$SAVESET_ID';"`
rm $SQL_INSERT
il_syslog info "FINISHED $SAVESET - $COUNT files"
exit 0
