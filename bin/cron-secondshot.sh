#! /bin/bash -e
#  Run this 3 times daily, 1:30 9:30 and 17:30

export DBPASS=$(cat /run/secrets/secondshot-db-password)
HOSTS="--host=localhost --host=secondhost"

HOUR=`date +%H`
WEEKDAY=`date +%w`
DAY=`date +%d`
MONTH=`date +%m`

secondshot --action=start --volume=daily-$(hostname -s) --autoverify=no \
  --hashtype=md5 $HOSTS
secondshot --action=rotate --interval=hourly
if [ $HOUR -le 02 ]; then
  secondshot --action=rotate --interval=daysago
  [ $WEEKDAY == 0 ] && rsnap-rotate.sh --interval=weeksago
  if [ $DAY -eq 1 ]; then
    secondshot --action=rotate --interval=monthsago
    [ $MONTH -eq 9 ] || [ $MONTH -eq 3 ] && secondshot --action=rotate --interval=semiannually
    [ $MONTH -eq 9 ] && secondshot --action=rotate --interval=yearsago
  fi
fi
