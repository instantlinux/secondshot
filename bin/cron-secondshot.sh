#! /bin/bash -e
#  Run this 1 or more times daily, e.g. 1:30 9:30 and 17:30
#  with HOSTS="--host=localhost --host=secondhost ..."
#       VOLUME="--volume=daily-$(hostname -s)" in env file or database

export DBPASS=$(cat /run/secrets/secondshot-db-password)
export DBHOST="{{ DBHOST }}"
export DBNAME="{{ DBNAME }}"
export DBPORT="{{ DBPORT }}"
export DBTYPE="{{ DBTYPE }}"
export DBUSER="{{ DBUSER }}"
[ -x /etc/secondshot-env ] && source /etc/secondshot-env

HOUR=$(date +%H)
WEEKDAY=$(date +%w)
DAY=$(date +%d)
MONTH=$(date +%m)

secondshot --action=start $VOLUME $HOSTS

# This example assumes exactly one run between midnight and 1:59am local time
#  with annual savesets each September, semi-annual savesets also kept for
#  March, monthlies on the 1st and weeklies on Sundays.
if [ $HOUR -le 02 ]; then
  if [ $DAY -eq 1 ]; then
    [ $MONTH -eq 9 ] && secondshot --action=rotate --interval=yearsago
    [ $MONTH -eq 9 ] || [ $MONTH -eq 3 ] && secondshot --action=rotate --interval=semiannually
    secondshot --action=rotate --interval=monthsago
  fi
  [ $WEEKDAY == 0 ] && secondshot --action=rotate --interval=weeksago
  secondshot --action=rotate --interval=daysago
fi
secondshot --action=rotate --interval=hourly
