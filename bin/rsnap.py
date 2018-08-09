#!/usr/bin/env python
"""rsnap

The Linux 'rsnapshot' backup utility with integrity-verification

created 28-jul-2018 by richb@instantlinux.net

Usage:
  rsnap.py [--action=ACTION] [--dbhost=HOST] [--dbuser=USER] [--dbpass=PASS]
           [--dbname=DB] [--dbport=PORT]
           [--backup-host=HOST] [--host=HOST]... [--logfile=FILE]
           [--list-hosts] [--list-savesets] [--list-volumes]
           [--filter=STR] [--format=FORMAT]
           [--rsnapshot-conf=FILE] [--autoverify=BOOL] [--volume=VOL] [-v]...
  rsnap.py --action=start --host=HOST --volume=VOL [--autoverify=BOOL] [-v]...
  rsnap.py --action=rotate --interval=INTERVAL [-v]...
  rsnap.py --verify=SAVESET... [--format=FORMAT] [-v]...
  rsnap.py (-h | --help)

Options:
  --action=ACTION       Action to take (archive, rotate, start)
  --backup-host=HOST    Hostname taking the backup
  --dbhost=HOST         DB host [default: db00]
  --dbname=DB           DB name [default: rsnap]
  --dbport=PORT         DB port [default: 18306]
  --dbuser=USER         DB user [default: bkp]
  --dbpass=PASS         DB password
  --host=HOST           Source host(s) to back up
  --interval=INTERVAL   Rotation interval: hourly, daysago, weeksago,
                        semiannually, yearsago or main
  --list-hosts          List hosts
  --list-savesets       List savesets
  --list-volumes        List volumes
  --filter=STR          Filter to limit listing [default: *]
  --format=FORMAT       Format (text or json) [default: text]
  --logfile=FILE        Logging destination
  --rsnapshot-conf=FILE Path of rsnapshot's config file
                        [default: /var/lib/ilinux/rsnap/etc/backup-daily.conf]
  --autoverify=BOOL     Verify each just-created saveset [default: yes]
  --verify=SAVESET      Verify checksums of stored files
  --volume=VOLUME       Volume to back up
  -v --verbose          Verbose output
  -h --help             List options

license: gplv2
"""

import datetime
import docopt
import grp
import hashlib
import json
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
import subprocess
import sys
import time

import models

DEFAULT_SEQUENCE = ['hourly', 'daysago', 'weeksago', 'monthsago',
                    'semiannually', 'yearsago']
SNAPSHOT_ROOT = '/var/backup'
SYNC_PATH = '.sync'


class RsnapShot(object):
    global logger

    def __init__(self, opts):
        if ('--db-pass' in opts):
            pw = opts['--dbpass']
        else:
            pw = os.environ['BKP_PASSWD']
        self.backup_host = socket.gethostname().split('.')[0]
        if (opts['--format'] in ['json', 'text']):
            self.format = opts['--format']
        else:
            sys.exit('format must be json or text')
        self.rsnapshot_conf = opts['--rsnapshot-conf']
        self.sequence = DEFAULT_SEQUENCE
        self.snapshot_root = SNAPSHOT_ROOT
        self.time_fmt = '%Y-%m-%d %H:%M:%S'
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

    def calc_sums(self, saveset_id):
        """Calculate checksums for any files that haven't already been stored

        Args:
            saveset_id (int): record ID of saveset
        Returns:
            result (dict):    results summary
        """
        try:
            host = self.session.query(models.Saveset).filter_by(
                id=saveset_id).one().host.hostname
            location = self.session.query(models.Saveset).filter_by(
                id=saveset_id).one().location
            missing_sha = self.session.query(models.Backup). \
                join(models.Backup.file). \
                filter(models.Backup.saveset_id == saveset_id,
                       models.File.shasum == None,  # noqa: E711
                       models.File.type == 'f',
                       models.File.size > 0)
            saveset = self.session.query(models.Saveset).filter_by(
                id=saveset_id).one().saveset
        except Exception as ex:
            logger.warn('action=calc_sums msg=%s' % ex.message)
        if (not host or not location):
            sys.exit('action=calc_sums msg=missing host/location')
        total = self.session.query(sqlalchemy.sql.func.sum(
            models.File.size).label('total')).filter(
            models.Backup.saveset_id == saveset_id).join(
            models.Backup, models.File.id == models.Backup.file_id).one()[0]
        logger.info("START action=calc_sums saveset=%s (size=%.3fGB) from "
                    "host=%s for location=%s" %
                    (saveset, float(total) / 1e9, host, location))
        (bytes, count) = (0, 0)
        for record in missing_sha:
            count += 1
            try:
                with open('%s/%s' % (
                        record.file.path, record.file.filename), 'r') as f:
                    sha = hashlib.sha512(f.read()).digest()
                record.file.shasum = sha
                self.session.add(record.file)
                bytes += record.file.size
            except Exception as ex:
                logger.warn("action=calc_sums id=%d msg=skipped error=%s" %
                            (record.file.id, ex.message))
            if (count % 1000 == 0):
                logger.debug('action=calc_sums count=%d bytes=%d' %
                             (count, bytes))
                self.session.commit()

        self.session.commit()
        logger.info("FINISHED action=calc_sums saveset=%s processed=%.3fGB" % (
            saveset, float(bytes) / 1e9))
        return {'calc_sums': dict(
            status='ok', saveset=saveset, size=total, processed=bytes)}

    def inject(self, host, volume, pathname, saveset_id):
        """Inject filesystem metadata for each file in a saveset into database

        Args:
            host (str):       host from which to copy files
            volume (str):     saveset's volume name
            pathname (str):   path where current backup is stored
            saveset_id (int): record ID of new saveset
        Returns:
            result (dict):    results summary
        """
        try:
            vol = self.session.query(models.Volume).filter_by(
                volume=volume).one()
            host_record = self.session.query(models.Host).filter_by(
                hostname=host).one()
            saveset = self.session.query(models.Saveset).filter_by(
                id=saveset_id).one()
        except Exception as ex:
            sys.exit('action=inject Invalid host or volume: %s' % ex.message)
        (count, skipped) = (0, 0)
        for dirpath, dirnames, filenames in os.walk(pathname):
            for filename in filenames:
                try:
                    stat = os.lstat(os.path.join(dirpath, filename))
                    _path = pymysql.escape_string(dirpath.encode(
                            'unicode_escape'))
                    _filename = pymysql.escape_string(filename.encode(
                            'unicode_escape'))
                except OSError as ex:
                    if ex.errno != 2:
                        logger.error(
                            'action=inject filename=%s message=%s' %
                            (filename, ex.message))
                        raise
                    skipped += 1
                    logger.debug('action=inject path=%s filename=%s msg=%s' % (
                        dirpath, filename, ex.message))
                    continue
                except UnicodeDecodeError as ex:
                    msg = 'action=inject inode=inode=%d dev=%s' % (
                        stat.st_ino, stat.st_dev)
                    try:
                        msg += ' path=%s filename=%s msg=%s' % (
                            dirpath, filename, ex.message)
                    except Exception:
                        pass
                    skipped += 1
                    logger.debug(msg)
                    continue
                record = dict(
                    path=_path,
                    filename=_filename,
                    ctime=datetime.datetime.fromtimestamp(
                        stat.st_ctime).strftime(self.time_fmt),
                    gid=stat.st_gid,
                    last_backup=datetime.datetime.now().strftime(
                        '%Y-%m-%d %H:%M:%S'),
                    links=stat.st_nlink,
                    mode=stat.st_mode,
                    mtime=datetime.datetime.fromtimestamp(
                        stat.st_mtime).strftime(self.time_fmt),
                    size=stat.st_size,
                    sparseness=1,
                    type=self._filetype(stat.st_mode),
                    uid=stat.st_uid,
                    host_id=host_record.id)
                try:
                    owner = pwd.getpwuid(stat.st_uid).pw_name
                    group = grp.getgrgid(stat.st_gid).gr_name
                except KeyError:
                    owner = None
                    group = None

                for retry in range(5):
                    try:
                        # Bypass sqlalchemy for ON DUPLICATE KEY UPDATE and
                        # LAST_INSERT_ID functionality
                        self.session.execute(
                            u"INSERT INTO files (%(columns)s)"
                            u" VALUES('%(values)s')"
                            u" ON DUPLICATE KEY UPDATE owner='%(owner)s',"
                            u"grp='%(group)s',id=LAST_INSERT_ID(id),"
                            u"last_backup=NOW();" % dict(
                                columns=','.join(record.keys()),
                                values="','".join(str(item) for item
                                                  in record.values()),
                                owner=owner, group=group))
                        self.session.execute(
                            "INSERT INTO backups (saveset_id,volume_id,file_id"
                            ") VALUES(%(saveset_id)d,%(volume_id)d,"
                            "LAST_INSERT_ID());" %
                            dict(saveset_id=saveset.id, volume_id=vol.id))
                        break
                    except pymysql.err.OperationalError as ex:
                        logger.warn('action=inject path=%s filename=%s msg=%s'
                                    % (_path, _filename, ex.message))
                        if ('Deadlock found' in ex.message):
                            time.sleep((retry + 1) * 10)
                    except Exception as ex:
                        logger.warn('action=inject path=%s filename=%s msg=%s'
                                    % (_path, _filename, ex.message))
                    if (retry == 5):
                        skipped += 1
                count += 1
                if (count % 5000 == 0):
                    logger.debug('action=inject count=%d' % count)
                    self.session.commit()

        self.session.commit()
        saveset.finished = sqlalchemy.func.now()
        self.session.add(saveset)
        self.session.commit()
        logger.info('FINISHED action=inject saveset=%s, file_count=%d, '
                    'skipped=%d' % (saveset.saveset, count, skipped))
        return {'inject': dict(
            status='ok', saveset=saveset.saveset, file_count=count,
            skipped=skipped)}

    def rotate(self, interval):
        """Rotate backup entries based on specified interval
        Args:
            interval (str): Values such hourly, daysago as defined by
                            'interval' keyword in rsnapshot conf file

        Returns:
            response (dict): rotation actions taken, if any
        """

        results = []
        if (interval not in self.rsnapshot_cfg['interval']):
            sys.exit(
                'action=rotate interval=%s must be in %s' %
                (interval, ','.join(sorted(self.rsnapshot_cfg[
                    'interval'].keys()))))
        host_record = self.session.query(models.Host).filter_by(
            hostname=self.backup_host).one()
        interval_max = int(self.rsnapshot_cfg['interval'][interval])

        try:
            ret = subprocess.call(['rsnapshot', '-c',
                                   self.rsnapshot_conf, interval])
        except Exception as ex:
            logger.error(msg)
            msg = 'action=rotate subprocess error=%s' % ex.message
            sys.exit(msg)
        if (ret != 0):
            msg = 'action=rotate subprocess returned=%d' % ret
            logger.error(msg)
            sys.exit(msg)

        # figure out oldest item in previous interval
        if (interval in ['hourly', 'main']):
            prev = SYNC_PATH
        elif (interval in self.sequence):
            prev = self.sequence[self.sequence.index(interval) - 1]
            prev += ".%d" % (int(self.rsnapshot_cfg['interval'][prev]) - 1)
        else:
            sys.exit('action=rotate interval=%s unrecognized' % interval)

        # delete savesets that match <interval>.<interval_max - 1>
        count = self.session.query(models.Saveset).filter_by(
            location='%s.%d' % (interval, interval_max - 1),
            backup_host_id=host_record.id).delete()
        if (count > 0):
            results.append(dict(
                host=self.backup_host,
                location='%s.%d' % (interval, interval_max - 1),
                savesets=count))
            logger.info(
                'action=rotate host=%s location=%s.%d savesets=%d removed' %
                (self.backup_host, interval, interval_max - 1, count))

        # move all savesets location <interval>.<n> => <n+1>
        self.session.execute(
            "UPDATE savesets SET location=CONCAT('%(interval)s','.',"
            "SUBSTR(location,locate('.',location)+1)+1) WHERE "
            "location LIKE '%(interval)s%%' AND backup_host_id=%(host)d" % {
                'interval': interval, 'host': host_record.id})

        # move saveset location=<previous int> to <interval>.0
        count = self.session.query(models.Saveset).filter(
            models.Saveset.location == prev,
            models.Saveset.backup_host_id == host_record.id,
            models.Saveset.finished is not None).update({
                models.Saveset.location: '%s.0' % interval})
        if (count > 0):
            results.append(dict(
                host=self.backup_host,
                savesets=count,
                location='%s.0' % interval,
                prev=prev))
            logger.info('action=rotate host=%s savesets=%d location=%s.0 '
                        'prev=%s' % (self.backup_host, count, interval, prev))
        self.session.commit()
        return {'rotate': dict(status='ok', actions=results)}

    def start(self, hosts, volume, autoverify):
        """Start a backup for each of the specified hosts; if
        successful, also calculate sha checksums for any missing
        entries and re-read each stored file to verify

        Args:
            hosts (list):      hosts to back up
            volume (str):      volume path of destination
            autoverify (bool): verify
        Returns:
            dict: operations performed
        """
        if (len(hosts) == 0):
            sys.exit('action=start must specify at least one --host')
        results = []
        status = 'ok'
        for host in hosts:
            try:
                new_saveset = self.new_saveset(host, volume)
                saveset_id = new_saveset['id']
            except sqlalchemy.exc.IntegrityError as ex:
                logger.error('action=start database error=%s' % ex.message)
                status = 'error'
                continue
            try:
                ret = subprocess.call(['rsnapshot', '-c',
                                       self.rsnapshot_conf, 'sync', host])
            except Exception as ex:
                logger.error('action=start subprocess error=%s' % ex.message)
                status = 'error'
                continue
            if (ret != 0):
                logger.error('action=start rsnapshot process error=%d' % ret)
                status = 'error'
                continue
            try:
                results.append(
                    self.inject(host, volume, '%s/%s' % (
                        self.snapshot_root, SYNC_PATH), saveset_id))
            except Exception as ex:
                logger.error('action=start inject error=%s' % str(ex))
                status = 'error'
                continue
            results.append(self.calc_sums(saveset_id))
            if (autoverify):
                try:
                    result = self.verify([new_saveset['saveset']])
                    results.append(result)
                    if (result['verify']['status'] != 'ok'):
                        status = 'error'
                except RuntimeError:
                    status = 'error'

        return {'start': dict(status=status, results=results)}

    def new_saveset(self, host, volume):
        """Set up new saveset entry in database
        Args:
            host (str):   host from which to copy files
            volume (str): volume path of destination

        Returns:
            dict: id and name of new record in saveset table
        """

        vol = self.session.query(models.Volume).filter_by(volume=volume).one()
        host_record = self.session.query(models.Host).filter_by(
            hostname=host).one()
        backup_host_record = self.session.query(models.Host).filter_by(
            hostname=self.backup_host).one()
        if (not host or not vol):
            sys.exit('Invalid host or volume')
        pathname = '%s/%s.0' % (self.snapshot_root, self.sequence[0])
        saveset = models.Saveset(
            saveset='%(host)s-%(volume)s-%(date)s' % dict(
                host=host,
                volume=volume,
                date=datetime.datetime.now().strftime('%Y%m%d-%H')),
            location=SYNC_PATH,
            host=host_record,
            backup_host=backup_host_record
        )
        self.session.add(saveset)
        self.session.commit()
        logger.info('START saveset=%s' % saveset.saveset)
        return dict(id=saveset.id, saveset=saveset.saveset)

    def verify(self, savesets):
        """Read each file in specified savesets to verify against stored
        checksums

        Parameters:
            savesets (list): saveset names
        Returns:
            result (dict): summary of files checked
                  status = ok if no errors
                  [count = files examined
                   skipped = files that couldn't be read (e.g. permissions)
                   missing = files for which the DB has no stored checksum
                   errors = files with content that does not match checksum]
        Raises:
            RuntimeError: if saveset is missing
        """

        results = []
        for saveset in savesets:
            try:
                record = self.session.query(models.Saveset).filter_by(
                        saveset=saveset).one()
            except sqlalchemy.orm.exc.NoResultFound:
                raise RuntimeError('VERIFY saveset=%s not found' % saveset)

            count = missing = self.session.query(models.Backup).join(
                    models.Backup.file).filter(
                        models.Backup.saveset_id == record.id,
                        models.File.type == 'f',
                        models.File.shasum == None,  # noqa: E711
                        models.File.size > 0).count()
            (errors, skipped) = (0, 0)
            for file in self.session.query(models.Backup).join(
                    models.Backup.file).filter(
                        models.Backup.saveset_id == record.id,
                        models.File.type == 'f',
                        models.File.shasum,
                        models.File.size > 0):
                count += 1
                try:
                    with open('%s/%s' % (
                            file.file.path, file.file.filename), 'r') as f:
                        sha = hashlib.sha512(f.read()).digest()
                    if (sha != file.file.shasum):
                        logger.warn('BAD CHECKSUM: action=verify file=%s/%s'
                                    % (file.file.path, file.file.filename))
                        errors += 1
                except Exception as ex:
                    logger.debug('sha(%s): %s' % (
                        file.file.filename, str(ex)))
                    skipped += 1
                if (count % 1000 == 0):
                    logger.debug('action=verify count=%d skipped=%d errors=%d'
                                 % (count, skipped, errors))

            msg = ('VERIFY: saveset=%s count=%d errors=%d missing=%d '
                   'skipped=%d' % (saveset, count, errors, missing, skipped))
            if (self.format == 'text'):
                print msg
            if (errors):
                logger.error(msg)
            else:
                logger.info(msg)
            results.append(dict(
                saveset=saveset, count=count, errors=errors,
                missing=missing, skipped=skipped))

        return {'verify': dict(
            status='ok' if errors == 0 else 'error',
            results=results)}

    def list_hosts(self, filter):
        """List hosts"""
        items = self.session.query(models.Host).filter(
            models.Host.hostname.like(filter)).order_by('hostname')
        return {'hosts': [dict(
                    name=item.hostname,
                    created=item.created.strftime(self.time_fmt)
                    ) for item in items]}

    def list_savesets(self, filter):
        """List savesets"""
        items = self.session.query(models.Saveset).filter(
            models.Saveset.saveset.like(filter)).order_by('saveset')
        return {'savesets': [dict(
                    name=item.saveset, location=item.location,
                    created=item.created.strftime(self.time_fmt),
                    host=item.host.hostname,
                    backup_host=item.backup_host.hostname,
                    finished=item.finished.strftime(self.time_fmt) if
                             item.finished else None) for item in items]}

    def list_volumes(self, filter):
        """List volumes"""
        items = self.session.query(models.Volume).filter(
            models.Volume.volume.like(filter)).order_by('volume')
        return {'volumes': [dict(
                    name=item.volume, path=item.path, size=item.size,
                    created=item.created.strftime(self.time_fmt),
                    host=item.host.hostname) for item in items]}

    @staticmethod
    def _filetype(mode):
        """Determine file type given the stat mode bits

        Args:
           mode (int): mode bits returned by os.stat()
        Returns:
           char:  character-special, directory, file, link (symbolic),
                  pipe, socket
        Raises:
            RuntimeError: if unexpected status
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

    def debug(self, msg):
        if (self.log_level == logging.DEBUG):
            print >>sys.stderr, "DEBUG: %s" % msg
            self.logger.debug('%s %s' % (self.prog, msg))
            with open(self.logfile, 'a') as f:
                f.write(self._date_prefix('D', msg))

    def error(self, msg):
        print >>sys.stderr, "ERROR: %s" % msg
        self.logger.error('%s %s' % (self.prog, msg))
        with open(self.logfile, 'a') as f:
            f.write(self._date_prefix('E', msg))

    def info(self, msg):
        if (self.log_level == logging.DEBUG):
            print >>sys.stderr, "INFO: %s" % msg
        self.logger.info('%s %s' % (self.prog, msg))
        with open(self.logfile, 'a') as f:
            f.write(self._date_prefix('I', msg))

    def warn(self, msg):
        print >>sys.stderr, "WARN: %s" % msg
        self.logger.warn('%s %s' % (self.prog, msg))
        with open(self.logfile, 'a') as f:
            f.write(self._date_prefix('W', msg))


class ReadConfig(object):
    def __init__(self, filename=None):
        self.multiple_allowed = ['backup', 'backup_script', 'exclude',
                                 'include', 'include_conf', 'interval']

    def rsnapshot_cfg(self, filename):
        """Parse the rsnapshot config file into a dictionary
        Keywords in this config file can have up to two parameters;
        for those which allow multiple statements of the same keyword,
        return a 2-level sub-dictionary or a single-level list

        Args:
            filename (str): name of config file
        Returns:
            dict:  parsed contents
        Raises:
            SyntaxError: if unexpected syntax
        """

        self.filename = filename
        contents = {}
        fp = open(filename, 'r')
        linenum = 1
        for line in fp:
            if '#' in line:
                line, comment = line.split('#', 1)
            tokens = line.strip().split()
            if (len(tokens) == 0):
                continue
            elif (len(tokens) < 2 or len(tokens) > 3):
                raise SyntaxError('file=%s at line %d\n%s' % (
                    filename, linenum, line))
            key = tokens[0]
            if (key in self.multiple_allowed):
                if (len(tokens) == 2):
                    if (key not in contents):
                        contents[key] = []
                    contents[key].append(tokens[1])
                else:
                    if (key not in contents):
                        contents[key] = {}
                    contents[key][tokens[1]] = tokens[2]
            elif (key not in contents):
                contents[key] = ' '.join(tokens[1:])
            else:
                raise SyntaxError('file=%s (%d): duplicate keyword %s' % (
                    filename, linenum, key))
            linenum += 1
        fp.close()
        return contents


def main():
    global logger
    opts = docopt.docopt(__doc__)
    obj = RsnapShot(opts)
    logger = Syslog()
    obj.rsnapshot_cfg = ReadConfig().rsnapshot_cfg(opts['--rsnapshot-conf'])
    if ('snapshot_root' in obj.rsnapshot_cfg):
        obj.snapshot_root = obj.rsnapshot_cfg['snapshot_root'].rstrip('/')
    filter = opts['--filter'].replace('*', '%')
    result = {}
    status = 'ok'

    if (opts['--logfile']):
        logger.logfile = opts['--logfile']
    if (opts['--verbose']):
        logger.log_level = logging.DEBUG
    if (opts['--autoverify'].lower() in ['false', 'no', 'off']):
        autoverify = False
    elif (opts['--autoverify'].lower() in ['true', 'yes', 'on']):
        autoverify = True
    else:
        sys.exit('Unknown value: --autoverify=BOOL')

    if (opts['--list-hosts']):
        result = obj.list_hosts(filter=filter)
    elif (opts['--list-savesets']):
        result = obj.list_savesets(filter=filter)
    elif (opts['--list-volumes']):
        result = obj.list_volumes(filter=filter)
    elif (opts['--verify']):
        result = obj.verify(opts['--verify'])
    elif (opts['--action'] == 'start'):
        result = obj.start(opts['--host'], opts['--volume'], autoverify)
        status = result['start']['status']
    elif (opts['--action'] == 'rotate'):
        result = obj.rotate(opts['--interval'])
    else:
        sys.exit('Unknown action: %s' % opts['--action'])

    if (obj.format == 'json'):
        print json.dumps(result)
    elif (obj.format == 'text' and result and result.keys()[0] in [
            'hosts', 'savesets', 'volumes']):
        for item in result[result.keys()[0]]:
            print item['name']
    if (status != 'ok'):
        exit(1)


if __name__ == '__main__':
    main()
