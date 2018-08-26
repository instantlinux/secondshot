#! /bin/bash -e
#  Run this 3 times daily, 1:30 9:30 and 17:30
#  with HOSTS="--host=localhost --host=secondhost ..."
#       VOLUME="--volume=daily-$(hostname -s)"

export DBPASS=$(cat /run/secrets/secondshot-db-password)
export DBHOST="{{ DBHOST }}"
export DBNAME="{{ DBNAME }}"
export DBPORT="{{ DBPORT }}"
export DBTYPE="{{ DBTYPE }}"
export DBUSER="{{ DBUSER }}"
[ -x /etc/secondshot-env ] && source /etc/secondshot-env

HOUR=`date +%H`
WEEKDAY=`date +%w`
DAY=`date +%d`
MONTH=`date +%m`

secondshot --action=start $VOLUME $HOSTS
if [ $HOUR -le 02 ]; then
  [ $WEEKDAY == 0 ] && secondshot --action=rotate --interval=weeksago
  if [ $DAY -eq 1 ]; then
    [ $MONTH -eq 9 ] && secondshot --action=rotate --interval=yearsago
    [ $MONTH -eq 9 ] || [ $MONTH -eq 3 ] && secondshot --action=rotate --interval=semiannually
    secondshot --action=rotate --interval=monthsago
  fi
  secondshot --action=rotate --interval=daysago
fi
secondshot --action=rotate --interval=hourly
