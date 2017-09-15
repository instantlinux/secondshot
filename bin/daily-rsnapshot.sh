#! /bin/bash
# $Id: daily-rsnapshot.sh,v 1.6 2013/02/23 20:26:14 root Exp $
#  Run this 3 times daily, 1:30 9:30 and 17:30

. /etc/default/source.sh
if [ `hostname -s` == "cumbre" ]; then
 HOSTS="k2 cumbre mckinley vinson"
else
 HOSTS="cumbre mckinley"
fi
SNAPSHOT_ROOT=/var/backup/daily

HOUR=`date +%H`
WEEKDAY=`date +%w`
DAY=`date +%d`
MONTH=`date +%m`

CONFIG=/var/lib/ilinux/rsnap/etc/backup-daily.conf
BIN=/var/lib/ilinux/rsnap/bin
RET=0

il_syslog info START

# Sync each destination, and inject filename metadata into the backup saveset
for HOST in $HOSTS; do
  BKPHOST=`hostname -s`
  SAVESET=`$BIN/rsnap-start.sh $HOST daily-$BKPHOST`
  if [ $? == 0 ]; then
    rsnapshot -c $CONFIG sync $HOST
    ERR=$?
    if [ $ERR == 0 ]; then
      $BIN/rsnap-inject.sh $HOST daily-$BKPHOST $SNAPSHOT_ROOT/.sync $SAVESET
      if [ $? != 0 ]; then
        RET=$?
      else
        $BIN/rsnap-calc-sums.sh $SNAPSHOT_ROOT $SAVESET
      fi
    else
      RET=$ERR
    fi
  else
    RET=1
  fi
done

# Rotate the snapshots
if [ $RET == 0 ]; then
  rsnapshot -c $CONFIG hourly
  $BIN/rsnap-rotate.sh hourly
  if [ $HOUR -le 02 ]; then
    rsnapshot -c $CONFIG daysago
    $BIN/rsnap-rotate.sh daysago
    [ $WEEKDAY == 0 ] && rsnapshot -c $CONFIG weeksago && $BIN/rsnap-rotate.sh weeksago
    if [ $DAY -eq 1 ]; then
      rsnapshot -c $CONFIG monthsago
      $BIN/rsnap-rotate.sh monthsago
      [ $MONTH -eq 9 ] || [ $MONTH -eq 3 ] && rsnapshot -c $CONFIG semiannually && $BIN/rsnap-rotate.sh semiannually
      [ $MONTH -eq 9 ] && rsnapshot -c yearsago && $BIN/rsnap-rotate.sh yearsago
    fi
  fi
fi

il_syslog info FINISHED
exit $RET
