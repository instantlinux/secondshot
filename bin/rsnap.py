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
import hashlib
import logging
import logging.handlers
import os
import os.path
import pymysql
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

    def calc_sums(self, saveset_id):
        """Calculate checksums"""
        try:
            host = self.session.query(models.Saveset).filter_by(
                id=saveset_id).one().host.hostname
            location = self.session.query(models.Saveset).filter_by(
                id=saveset_id).one().location
            missing_sha = self.session.query(models.Backup). \
                join(models.Backup.file). \
                filter(models.Backup.saveset_id == saveset_id). \
                filter(models.File.sha256sum is None). \
                filter(models.File.type == 'f'). \
                filter(models.File.size > 0)
        except Exception as ex:
            logger.error('action=calc_sums msg=%s' % ex.message)
        if (not host or not location):
            logger.error('action=calc_sums msg=missing host/location')
            exit(1)
        total = self.session.query(sqlalchemy.sql.func.sum(
            models.File.size).label('total')).filter(
            models.Backup.saveset_id == saveset_id).join(
            models.Backup, models.File.id == models.Backup.file_id).one()[0]
        logger.info("action=calc_sums started for files (size=%.3fGB) from "
                    "host=%s for location=%s" %
                    (float(total) / 1e9, host, location))
        bytes = 0
        for record in missing_sha:
            try:
                with open('%s/%s' % (
                        record.file.path, record.file.filename), 'r') as f:
                    sha256 = hashlib.sha256(f.read()).hexdigest()
                record.file.sha256sum = sha256
                self.session.add(record.file)
                bytes += record.file.size
            except Exception as ex:
                logger.error("action=calc_sums id=%d msg=skipped" %
                             record.file.id)
        self.session.commit()
        logger.info("FINISHED action=calc_sums size=%.3fGB" % (
            bytes / 1e9))

    def inject(self, host, volume, pathname, saveset_id):
        """Inject pathnames from filesystem into database;
        if successful, also calculate sha256sums for any
        missing entries

        Args:
            host (str):       host from which to copy files
            volume (str):     saveset's volume name
            pathname (str):   path where current backup is stored
            saveset_id (int): record ID of new saveset
        """
        try:
            vol = self.session.query(models.Volume).filter_by(
                volume=volume).one()
            host_record = self.session.query(models.Host).filter_by(
                hostname=host).one()
            saveset = self.session.query(models.Saveset).filter_by(
                id=saveset_id).one()
        except Exception as ex:
            logger.error('action=inject message=%s' % ex.message)
            raise ValueError('Invalid host or volume: %s' % ex.message)
        count = 0
        for dirpath, dirnames, filenames in os.walk(pathname):
            for filename in filenames:
                try:
                    stat = os.stat(os.path.join(dirpath, filename))
                except OSError as ex:
                    if ex.errno != 2:
                        logger.error(
                            'action=inject count=%d filename=%s message=%s' %
                            (count, filename, ex.message))
                        raise
                    continue
                record = dict(
                    path=pymysql.escape_string(dirpath),
                    filename=pymysql.escape_string(filename),
                    ctime=datetime.datetime.fromtimestamp(
                        stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
                    gid=stat.st_gid,
                    last_backup=datetime.datetime.now().strftime(
                        '%Y-%m-%d %H:%M:%S'),
                    links=stat.st_nlink,
                    mode=stat.st_mode,
                    mtime=datetime.datetime.fromtimestamp(
                        stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    size=stat.st_size,
                    sparseness=1,
                    type=self._filetype(stat.st_mode),
                    uid=stat.st_uid,
                    host_id=host_record.id)
                try:
                    owner = pwd.getpwuid(stat.st_uid).pw_name
                    group = grp.getgrgid(stat.st_gid).gr_name
                except KeyError:
                    pass

                # Bypass sqlalchemy for ON DUPLICATE KEY UPDATE and
                # LAST_INSERT_ID functionality
                try:
                    self.session.execute(
                        u"INSERT INTO files (%(columns)s) VALUES('%(values)s')"
                        u" ON DUPLICATE KEY UPDATE owner='%(owner)s',"
                        u"grp='%(group)s',id=LAST_INSERT_ID(id),"
                        u"last_backup=NOW();" % dict(
                            columns=','.join(record.keys()),
                            values="','".join(str(item) for item
                                              in record.values()),
                            owner=owner, group=group))
                    self.session.execute(
                        "INSERT INTO backups (saveset_id,volume_id,file_id) "
                        "VALUES(%(saveset_id)d,%(volume_id)d,"
                        "LAST_INSERT_ID());" %
                        dict(saveset_id=saveset.id, volume_id=vol.id))
                except UnicodeDecodeError as ex:
                    logger.error(u"action=inject dir=%s file=%s msg=%s" %
                                 (dirpath, filename.encode('ascii', 'ignore'),
                                  ex.message))
                except Exception as ex:
                    logger.error(u"action=inject dir=%s file=%s msg=%s" %
                                 (dirpath, filename, ex.message))
                count += 1
                if (count % 1000 == 0):
                    logger.info('action=inject count=%d' % count)
        try:
            self.session.commit()
        except Exception as ex:
            logger.error('action=inject msg=%s' % ex.message)
            exit(1)
        saveset.finished = sqlalchemy.func.now()
        self.session.add(saveset)
        self.session.commit()
        logger.info('FINISHED action=inject saveset=%s, file_count=%d' % (
            saveset.saveset, count))
        self.calc_sums(saveset.id)

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
            logger.error(ex.message)
            exit(1)
        logger.info('START saveset=%s' % saveset.saveset)
        return saveset.id

    def list_hosts(self):
        """List hosts"""
        items = self.session.query(models.Host).order_by('hostname')
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
           char:  character-special, directory, file, link (symbolic),
                  pipe, socket
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
        print >>sys.stderr, "ERROR: %s" % msg
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
        result = obj.inject(
            opts['--host'], opts['--volume'], opts['--pathname'],
            int(opts['--saveset-id']))
    elif (opts['--action'] == 'rotate'):
        result = obj.rotate(opts['--interval'])
    else:
        print >>sys.stderr, 'ERROR Unknown action: %s' % opts['--action']
        exit(1)


if __name__ == '__main__':
    main()
