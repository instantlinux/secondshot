#! /bin/bash
# $Id: rsnap-rotate.sh,v 1.10 2013/03/31 17:03:25 root Exp $

. /etc/default/source.sh
. /etc/default/secure.sh
INTERVAL=$1

DBHOST=mdb00
DBNAME=rsnap
DBUSER=$BKP_USER

BKPHOST=`hostname -s`
BKPHOST_ID=`mysql -N -h $DBHOST -u $DBUSER -p$BKP_PASSWD $DBNAME -e "SELECT id FROM hosts WHERE hostname='$BKPHOST';"`
RET=0

il_syslog info "Rotating $INTERVAL for $BKPHOST"
if [ "$INTERVAL" == "hourly" ]; then
  mysql -h $DBHOST -u $DBUSER -p$BKP_PASSWD $DBNAME <<EOT
    DELETE backups FROM backups JOIN savesets ON savesets.id=backups.saveset_id WHERE location='hourly.2' AND backup_host_id=$BKPHOST_ID;
    DELETE FROM savesets WHERE location='hourly.2' AND backup_host_id=$BKPHOST_ID;
    UPDATE savesets SET location=CONCAT('$INTERVAL','.',substr(location,locate('.',location)+1)+1) WHERE location LIKE '$INTERVAL%' AND backup_host_id=$BKPHOST_ID;
    UPDATE savesets SET location='hourly.0' WHERE location='.sync' AND backup_host_id=$BKPHOST_ID AND finished IS NOT NULL;
EOT
  RET=$?
else
  case $INTERVAL in
    daysago)      MAX=6 ; PREV='hourly.2' ;;
    weeksago)     MAX=3 ; PREV='daysago.6' ;;
    monthsago)    MAX=5 ; PREV='weeksago.4' ;;
    semiannually) MAX=1 ; PREV='monthsago.5' ;;
    yearsago)     MAX=98 ; PREV='seminnually.1' ;;
    main)         MAX=99 ; PREV='.sync' ;;
    *)
     echo "Unknown interval"
     exit 1
  esac
  mysql -h $DBHOST -u $DBUSER -p$BKP_PASSWD $DBNAME <<EOT
    DELETE backups FROM backups JOIN savesets ON savesets.id=backups.saveset_id WHERE location='$INTERVAL.$MAX' AND backup_host_id=$BKPHOST_ID;
    DELETE FROM savesets WHERE location='$INTERVAL.$MAX' AND backup_host_id=$BKPHOST_ID;
    UPDATE savesets SET location=CONCAT('$INTERVAL','.',substr(location,locate('.',location)+1)+1) WHERE location LIKE '$INTERVAL%' AND backup_host_id=$BKPHOST_ID;
    UPDATE savesets SET location=CONCAT('$INTERVAL','.0') WHERE location='$PREV' AND backup_host_id=$BKPHOST_ID AND finished IS NOT NULL;
EOT
  [ $? != 0 ] && RET=$?
fi

exit $RET
