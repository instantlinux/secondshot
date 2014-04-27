#! /bin/bash
# $Id: archive_rsnap.sh,v 1.4 2013/03/26 14:46:19 root Exp $
#  Archive backup - for offline save sets
#  Parameters:
#   $1  saveset name (e.g. backup01a, backup02c)

SAVESET_NAME=$1

. /etc/default/source.sh
case $SAVESET_NAME in
  backup01b) HOSTS="cumbre pvr01" ;;
#  backup01c|backup02a) HOSTS="transcend cumbre mission pvr01" ;;
  backup01c|backup02a) HOSTS="cumbre mission pvr01" ;;
  backup02b) HOSTS="cumbre pvr01" ;;
  *) HOSTS="cumbre" ;;
esac

SNAPSHOT_ROOT=/var/backup/$SAVESET_NAME

CONFIG=~rsnap/etc/$SAVESET_NAME.conf
RET=0

il_syslog info START

# Sync each destination, and inject filename metadata into the backup saveset
for HOST in $HOSTS; do
  BKPHOST=`hostname -s`
  SAVESET=`~rsnap/bin/rsnap-start.sh $HOST $SAVESET_NAME`
  if [ $? == 0 ]; then
    rsnapshot -c $CONFIG sync $HOST
    ERR=$?
    if [ $ERR == 0 ]; then
      ~rsnap/bin/rsnap-inject.sh $HOST $SAVESET_NAME $SNAPSHOT_ROOT/.sync $SAVESET
      if [ $? != 0 ]; then
        RET=$?
      else
	il_syslog info "Backgrounding checksum calc for $SAVESET"
        ~rsnap/bin/rsnap-calc-sums.sh $SNAPSHOT_ROOT $SAVESET &
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
  rsnapshot -c $CONFIG main
  ~rsnap/bin/rsnap-rotate.sh main
fi

il_syslog info FINISHED
exit $RET
