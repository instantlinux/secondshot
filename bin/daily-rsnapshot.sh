#! /bin/bash
# $Id: daily-rsnapshot.sh,v 1.6 2013/02/23 20:26:14 root Exp $
#  Run this 3 times daily, 1:30 9:30 and 17:30

. /etc/default/source.sh
HOSTS="mission cumbre"
SNAPSHOT_ROOT=/var/backup/daily

HOUR=`date +%H`
WEEKDAY=`date +%w`
DAY=`date +%d`
MONTH=`date +%m`

CONFIG=~rsnap/etc/backup-daily.conf
RET=0

il_syslog info START

# Sync each destination, and inject filename metadata into the backup saveset
for HOST in $HOSTS; do
  BKPHOST=`hostname -s`
  SAVESET=`~rsnap/bin/rsnap-start.sh $HOST daily-$BKPHOST`
  if [ $? == 0 ]; then
    rsnapshot -c $CONFIG sync $HOST
    ERR=$?
    if [ $ERR == 0 ]; then
      ~rsnap/bin/rsnap-inject.sh $HOST daily-$BKPHOST $SNAPSHOT_ROOT/.sync $SAVESET
      if [ $? != 0 ]; then
        RET=$?
      else
        ~rsnap/bin/rsnap-calc-sums.sh $SNAPSHOT_ROOT $SAVESET
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
  ~rsnap/bin/rsnap-rotate.sh hourly
  if [ $HOUR -le 02 ]; then
    rsnapshot -c $CONFIG daysago
    ~rsnap/bin/rsnap-rotate.sh daysago
    [ $WEEKDAY == 0 ] && rsnapshot -c $CONFIG weeksago && ~rsnap/bin/rsnap-rotate.sh weeksago
    if [ $DAY == 1 ]; then
      rsnapshot -c $CONFIG monthsago
      ~rsnap/bin/rsnap-rotate.sh monthsago
      [ $MONTH == 9 ] || [ $MONTH == 3 ] && rsnapshot -c $CONFIG semiannually && ~rsnap/bin/rsnap-rotate.sh semiannually
      [ $MONTH == 9 ] && rsnapshot -c yearsago && ~rsnap/bin/rsnap-rotate.sh yearsago
    fi
  fi
fi

il_syslog info FINISHED
exit $RET
