#! /bin/bash -e
# $Id: daily-rsnapshot.sh,v 1.6 2013/02/23 20:26:14 root Exp $
#  Run this 3 times daily, 1:30 9:30 and 17:30

. /etc/default/source.sh
export BKP_PASSWD
PATH=/var/lib/ilinux/rsnap/bin:$PATH
HOSTS="--host=cumbre --host=mckinley"
if [ $(hostname -s) == "cumbre" ]; then
  HOSTS="$HOSTS --host=k2 --host=vinson"
fi

HOUR=`date +%H`
WEEKDAY=`date +%w`
DAY=`date +%d`
MONTH=`date +%m`

rsnap.py --action=start --volume=daily-$(hostname -s) --autoverify=yes \
  --hashtype=sha512 $HOSTS
rsnap.py --action=rotate --interval=hourly
if [ $HOUR -le 02 ]; then
  rsnap.py --action=rotate --interval=daysago
  [ $WEEKDAY == 0 ] && rsnap-rotate.sh --interval=weeksago
  if [ $DAY -eq 1 ]; then
    rsnap.py --action=rotate --interval=monthsago
    [ $MONTH -eq 9 ] || [ $MONTH -eq 3 ] && rsnap.py --action=rotate --interval=semiannually
    [ $MONTH -eq 9 ] && rsnap.py --action=rotate --interval=yearsago
  fi
fi
