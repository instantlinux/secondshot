#!/usr/bin/env python
"""Rsnap backup utility

created 28-jul-2018 by richb@instantlinux.net

Usage:
  rsnap.py [--action=ACTION] [--dbhost=HOST] [--dbuser=USER] [--dbpass=PASS]
           [--dbname=DB] [--dbport=PORT]
           [--backup-host=HOST] [--host=HOST] [--logfile=FILE]
           [--snapshot-root=PATH]
           [--volume=VOL] [-v]...
  rsnap.py --action=start --host=HOST --volume=VOL
  rsnap.py --action=inject --host=HOST --volume=VOL --pathname=PATH
           [--saveset-id=ID]
  rsnap.py --action=rotate --interval=INTERVAL
  rsnap.py (-h | --help)

Options:
  --action=ACTION       Action to take (archive, calc-sums, inject,
                        rotate, start, list-savesets)
  --backup-host=HOST    Hostname taking the backup
  --dbhost=HOST         DB host [default: db00]
  --dbpass=PASS         DB password
  --dbname=DB           DB name [default: rsnap]
  --dbport=PORT         DB port [default: 18306]
  --dbuser=USER         DB user [default: bkp]
  --host=HOST           Source host to back up
  --interval=INTERVAL   Rotation interval: hourly, daysago, weeksago,
                        semiannually, yearsago or main
  --logfile=FILE        Logging destination
  --saveset-id=ID       ID of saveset
  --snapshot-root=PATH  Top-level directory to hold
                        snapshots [default: /var/backup/daily]
  --volume=VOLUME       Volume to back up
  -v --verbose          Verbose output
  -h --help             List options
"""

import datetime
import docopt
import grp
import logging
import logging.handlers
import os
import os.path
import pwd
import socket
from sqlalchemy import create_engine
import sqlalchemy.orm
import stat
import sys

import models


class RsnapShot(object):
    global logger

    def __init__(self, opts):
        if ('--db-pass' in opts):
            pw = opts['--dbpass']
        else:
            pw = os.environ['BKP_PASSWD']
        self.backup_host = socket.gethostname().split('.')[0]
        self.snapshot_root = opts['--snapshot-root']
        self.engine = create_engine(
            'mysql+pymysql://%(user)s:%(password)s@%(endpoint)s/%(database)s'
            % {
                'user': opts['--dbuser'],
                'password': pw,
                'endpoint': '%s:%d' % (opts['--dbhost'],
                                       int(opts['--dbport'])),
                'database': opts['--dbname']
            })
        self.session = sqlalchemy.orm.scoped_session(
            sqlalchemy.orm.sessionmaker(autocommit=False, bind=self.engine))

    def archive(self):
        """Create backup archives"""
        raise NotImplementedError

    def calc_sums(self):
        """Calculate checksums"""
        raise NotImplementedError

    def inject(self, host, volume, pathname, saveset_id):
        """Inject pathnames from filesystem into database

        Args:
            host (str):       host from which to copy files
            volume (str):     saveset's volume name
            pathname (str):   path where current backup is stored
            saveset_id (int): record ID of new saveset
        """
        try:
            vol = self.session.query(models.Volume).filter_by(volume=volume).one()
            host_record = self.session.query(models.Host).filter_by(
                hostname=host).one()
            saveset = self.session.query(models.Saveset).filter_by(id=saveset_id).one()
        except Exception as ex:
            logger.error('action=inject message=%s' % ex.message)
            raise ValueError('Invalid host or volume: %s' % ex.message)
        count = 0
        for dirpath, dirnames, filenames in os.walk(pathname):
            for filename in filenames:
                full_path = os.path.join(dirpath, filename)
                stat = os.stat(full_path)
                record = models.File(
                    path=dirpath,
                    filename=filename,
                    ctime=stat.st_ctime,
                    gid=stat.st_gid,
                    # grp=grp.getgrgid(stat.st_gid).gr_name,
                    last_backup=sqlalchemy.func.now(),
                    links=stat.st_nlink,
                    mode=stat.st_mode,
                    mtime=stat.st_mtime,
                    # owner=pwd.getpwuid(stat.st_uid).pw_name,
                    size=stat.st_size,
                    sparseness=1,
                    type=self._filetype(stat.st_mode),
                    uid=stat.st_uid,
                    host=host_record)
                print full_path + ':' + str(stat)
                print record
                item = models.Backup(
                    saveset=saveset,
                    volume=vol,
                    file=record)
                self.session.add(record)
                self.session.add(item)
                count += 1
        self.session.commit()
        saveset.finished = sqlalchemy.func.now()
        self.session.add(saveset)
        self.session.commit()
        logger.info('FINISHED %s, file_count=%d' % (saveset.saveset, count))

    def rotate(self, interval):
        """Rotate backup entries based on specified interval
        Args:
            interval (str): Valid values are hourly, daysago, weeksago,
                            semiannually, yearsago or main
        """
        raise NotImplementedError

    def start(self, host, volume):
        """Set up new saveset entry in database
        Args:
            host (str):   host from which to copy files
            volume (str): volume path of destination

        Returns:
            int: id of new record in saveset table
        """

        vol = self.session.query(models.Volume).filter_by(volume=volume).one()
        host_record = self.session.query(models.Host).filter_by(
            hostname=host).one()
        backup_host_record = self.session.query(models.Host).filter_by(
            hostname=self.backup_host).one()
        if (not host or not vol):
            raise ValueError('Invalid host or volume')
        pathname = '%s/hourly.0' % self.snapshot_root
        saveset = models.Saveset(
            saveset='%(host)s-%(volume)s-%(date)s' % {
                'host': host,
                'volume': volume,
                'date': datetime.datetime.now().strftime('%Y%m%d-%H')},
            location='.sync',
            host=host_record,
            backup_host=backup_host_record
        )
        self.session.add(saveset)
        try:
            self.session.commit()
        except sqlalchemy.exc.IntegrityError as ex:
            print >>sys.stderr, 'ERROR: %s' % ex.message
            logger.error(ex.message)
            exit(1)
        logger.info('START %s' % saveset.saveset)
        return saveset.id

    def list_hosts(self):
        """List hosts"""
        items = self.session.query(
            models.Host).order_by('hostname')
        for item in items:
            print item.hostname

    def list_savesets(self):
        """List savesets"""
        items = self.session.query(models.Saveset).order_by('saveset')
        for item in items:
            print item.saveset

    def list_volumes(self):
        """List savesets"""
        items = self.session.query(models.Volume).order_by('volume')
        for item in items:
            print item.volume

    @staticmethod
    def _filetype(mode):
        """Determine file type given the stat mode bits

        Args:
           mode (int): mode bits returned by os.stat()
        Returns:
           char:  character-special, directory, file, link (symbolic), pipe, socket
        """
        if (stat.S_ISCHR(mode)):
            return 'c'
        elif (stat.S_ISDIR(mode)):
            return 'd'
        elif (stat.S_ISREG(mode)):
            return 'f'
        elif (stat.S_ISLNK):
            return 'l'
        elif (stat.S_ISFIFO):
            return 'p'
        elif (stat.S_ISSOCK):
            return 's'
        else:
            raise RuntimeError('Unexpected file mode %d' % mode)

class Syslog(object):
    def __init__(self):
        self.prog = os.path.basename(__file__).split('.')[0]
        self.logger = logging.getLogger()
        self.log_facility = 'local1'
        self.log_level = logging.INFO
        self.logger.setLevel(self.log_level)
        handler = logging.handlers.SysLogHandler(
            address='/dev/log', facility=self.log_facility)
        self.logger.addHandler(handler)
        self.logfile = '/var/log/%s' % self.prog

    @staticmethod
    def _date_prefix(severity, msg):
        return '[%s] %s %s\n' % (
            datetime.datetime.now().strftime('%d/%b/%Y-%H:%M:%S'),
            severity, msg)

    def error(self, msg):
        self.logger.error('%s %s' % (self.prog, msg))
        with open(self.logfile, 'a') as f:
            f.write(self._date_prefix('E', msg))

    def info(self, msg):
        self.logger.info('%s %s' % (self.prog, msg))
        with open(self.logfile, 'a') as f:
            f.write(self._date_prefix('I', msg))


def main():
    global logger

    opts = docopt.docopt(__doc__)
    obj = RsnapShot(opts)
    logger = Syslog()

    if (opts['--logfile']):
        logger.logfile = opts['--logfile']

    if (opts['--action'] == 'list-hosts'):
        obj.list_hosts()
    elif (opts['--action'] == 'list-savesets'):
        obj.list_savesets()
    elif (opts['--action'] == 'list-volumes'):
        obj.list_volumes()
    elif (opts['--action'] == 'start'):
        result = obj.start(opts['--host'], opts['--volume'])
        print result
    elif (opts['--action'] == 'inject'):
        result = obj.inject(opts['--host'], opts['--volume'], opts['--pathname'],
                            int(opts['--saveset-id']))
    elif (opts['--action'] == 'rotate'):
        result = obj.rotate(opts['--interval'])
    else:
        print >>sys.stderr, 'ERROR Unknown action: %s' % opts['--action']
        exit(1)


if __name__ == '__main__':
    main()
