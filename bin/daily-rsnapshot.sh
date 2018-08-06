#! /bin/bash
# $Id: daily-rsnapshot.sh,v 1.6 2013/02/23 20:26:14 root Exp $
#  Run this 3 times daily, 1:30 9:30 and 17:30

. /etc/default/source.sh
export BKP_PASSWD
if [ `hostname -s` == "cumbre" ]; then
 HOSTS="--host=k2 --host=cumbre --host=mckinley --host=vinson"
else
 HOSTS="--host=cumbre --host=mckinley"
fi

HOUR=`date +%H`
WEEKDAY=`date +%w`
DAY=`date +%d`
MONTH=`date +%m`

CONFIG=/var/lib/ilinux/rsnap/etc/backup-daily.conf
BIN=/var/lib/ilinux/rsnap/bin

il_syslog info START

$BIN/rsnap.py -v --action=start --volume=daily-$(hostname -s) $HOSTS
RET=$?

# Rotate the snapshots
if [ $RET == 0 ]; then
  rsnapshot -c $CONFIG hourly && $BIN/rsnap.py --action=rotate --interval=hourly
  if [ $HOUR -le 02 ]; then
    rsnapshot -c $CONFIG daysago && $BIN/rsnap.py --action=rotate --interval=daysago
    [ $WEEKDAY == 0 ] && rsnapshot -c $CONFIG weeksago && $BIN/rsnap-rotate.sh weeksago
    if [ $DAY -eq 1 ]; then
      rsnapshot -c $CONFIG monthsago && $BIN/rsnap.py --action=rotate --interval=monthsago
      [ $MONTH -eq 9 ] || [ $MONTH -eq 3 ] && rsnapshot -c $CONFIG semiannually && $BIN/rsnap.py --action=rotate --interval=semiannually
      [ $MONTH -eq 9 ] && rsnapshot -c yearsago && $BIN/rsnap.py --action=rotate --interval=yearsago
    fi
  fi
fi

il_syslog info FINISHED
exit $RET
