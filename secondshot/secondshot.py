#!/usr/bin/env python
"""secondshot

Linux-based backup utility with integrity-verification

created 28-jul-2018 by richb@instantlinux.net

Usage:
  secondshot [--action=ACTION] [--dbhost=HOST] [--dbuser=USER] [--dbpass=PASS]
           [--dbname=DB] [--dbport=PORT] [--dbtype=TYPE]
           [--backup-host=HOST] [--host=HOST]... [--logfile=FILE]
           [--list-hosts] [--list-savesets] [--list-volumes]
           [--filter=STR] [--format=FORMAT] [--hashtype=ALGORITHM]
           [--rsnapshot-conf=FILE] [--autoverify=BOOL] [--volume=VOL] [-v]...
  secondshot --action=start --host=HOST --volume=VOL [--autoverify=BOOL]
           [-v]...
  secondshot --action=rotate --interval=INTERVAL [-v]...
  secondshot --verify=SAVESET... [--format=FORMAT] [--hashtype=ALG] [-v]...
  secondshot (-h | --help)

Options:
  --action=ACTION       Action to take (archive, rotate, start)
  --backup-host=HOST    Hostname taking the backup
  --dbhost=HOST         DB host [default: db00]
  --dbname=DB           DB name [default: rsnap]
  --dbport=PORT         DB port [default: 18306]
  --dbuser=USER         DB user [default: bkp]
  --dbpass=PASS         DB password (default env variable DBPASS)
  --dbtype=TYPE         DB type, e.g. sqlite [default: mysql+pymysql]
  --host=HOST           Source host(s) to back up
  --interval=INTERVAL   Rotation interval: hourly, daysago, weeksago,
                        semiannually, yearsago or main
  --list-hosts          List hosts
  --list-savesets       List savesets
  --list-volumes        List volumes
  --filter=STR          Filter to limit listing [default: *]
  --format=FORMAT       Format (text or json) [default: text]
  --logfile=FILE        Logging destination [default: /var/log/secondshot]
  --rsnapshot-conf=FILE Path of rsnapshot's config file
                        [default: /etc/backup-daily.conf]
  --autoverify=BOOL     Verify each just-created saveset [default: yes]
  --hashtype=ALGORITHM  Hash algorithm md5, sha256, sha512 [default: md5]
  --verify=SAVESET      Verify checksums of stored files
  --volume=VOLUME       Volume to back up
  -v --verbose          Verbose output
  -h --help             List options

license: lgpl-2.1
"""

import binascii
import datetime
import docopt
import grp
import hashlib
import json
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

if (sys.version_info.major == 2):
    from config import ReadConfig
    from models import Backup, File, Host, Saveset, Volume
    from syslogger import Syslog
else:
    # Python 3 requires explicit relative-path syntax
    from .config import ReadConfig
    from .models import Backup, File, Host, Saveset, Volume
    from .syslogger import Syslog

DBPASS_FILE = '/run/secrets/secondshot-db-password'
DBFILE_PATH = '/metadata'
DEFAULT_SEQUENCE = ['hourly', 'daysago', 'weeksago', 'monthsago',
                    'semiannually', 'yearsago']
SNAPSHOT_ROOT = '/var/backup'
SYNC_PATH = '.sync'


class Secondshot(object):
    global logger

    def __init__(self, opts):
        self.backup_host = socket.gethostname().split('.')[0]
        if (opts['--format'] in ['json', 'text']):
            self.format = opts['--format']
        else:
            sys.exit('format must be json or text')
        if (opts['--hashtype'] in ['md5', 'sha256', 'sha512']):
            self.hashtype = opts['--hashtype']
        else:
            sys.exit('hashtype must be md5, sha256 or sha512')
        self.rsnapshot_conf = opts['--rsnapshot-conf']
        self.sequence = DEFAULT_SEQUENCE
        self.snapshot_root = SNAPSHOT_ROOT
        self.time_fmt = '%Y-%m-%d %H:%M:%S'
        if (opts['--dbtype'] == 'sqlite'):
            db_url = ('sqlite:////%(path)s/%(database)' % {
                          'path': DBFILE_PATH,
                          'database': opts['--dbname']
                      })
        else:
            pw = ''
            db_url = None
            if ('--db-url' in opts):
                db_url = opts['--db-url']
            elif ('DB_URL' in os.environ):
                db_url = os.environ['db_url']
            elif ('--db-pass' in opts):
                pw = opts['--dbpass']
            elif ('DBPASS' in os.environ):
                pw = os.environ['DBPASS']
            elif(os.path.isfile(DBPASS_FILE)):
                pw = open(DBPASS_FILE, 'r').read()
            else:
                logger.warn('Database password is not set')

            if (not db_url):
                db_url = ('%(dbtype)s://%(user)s:%(password)s@'
                          '%(endpoint)s/%(database)s' % {
                              'dbtype': opts['--dbtype'],
                              'user': opts['--dbuser'],
                              'password': pw,
                              'endpoint': '%s:%d' % (opts['--dbhost'],
                                                     int(opts['--dbport'])),
                              'database': opts['--dbname']
                          })
        self.engine = create_engine(db_url)
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
            host = self.session.query(Saveset).filter_by(
                id=saveset_id).one().host.hostname
            location = self.session.query(Saveset).filter_by(
                id=saveset_id).one().location
            missing_sha = self.session.query(Backup). \
                join(Backup.file). \
                filter(Backup.saveset_id == saveset_id,
                       File.shasum == None,  # noqa: E711
                       File.type == 'f',
                       File.size > 0)
            saveset = self.session.query(Saveset).filter_by(
                id=saveset_id).one().saveset
        except Exception as ex:
            logger.warn('action=calc_sums msg=%s' % ex.message)
        if (not host or not location):
            sys.exit('action=calc_sums msg=missing host/location')
        total = self.session.query(sqlalchemy.sql.func.sum(
            File.size).label('total')).filter(
            Backup.saveset_id == saveset_id).join(
            Backup, File.id == Backup.file_id).one()[0]
        logger.info("START action=calc_sums saveset=%s (size=%.3fGB) from "
                    "host=%s for location=%s" %
                    (saveset, float(total) / 1e9, host, location))
        (bytes, count) = (0, 0)
        for file in missing_sha:
            count += 1
            try:
                filename = os.path.join(
                    self.snapshot_root, location, file.file.path,
                    file.file.filename)
                file.file.shasum = self._filehash(filename, self.hashtype)
                self.session.add(file.file)
                bytes += file.file.size
            except Exception as ex:
                logger.warn("action=calc_sums id=%d msg=skipped error=%s" %
                            (file.file.id, ex.message))
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
            vol = self.session.query(Volume).filter_by(
                volume=volume).one()
            host_record = self.session.query(Host).filter_by(
                hostname=host).one()
            saveset = self.session.query(Saveset).filter_by(
                id=saveset_id).one()
        except Exception as ex:
            sys.exit('action=inject Invalid host or volume: %s' % ex.message)
        (count, skipped) = (0, 0)
        for dirpath, _, filenames in os.walk(pathname):
            for filename in filenames:
                try:
                    stat = os.lstat(os.path.join(dirpath, filename))
                    _path = pymysql.escape_string(os.path.relpath(
                        dirpath, self.snapshot_root + '/' + SYNC_PATH
                        ).encode('unicode_escape'))
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

                for retry in range(4):
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
                    except sqlalchemy.exc.OperationalError as ex:
                        logger.warn('action=inject path=%s filename=%s msg=%s'
                                    % (_path, _filename, ex.message))
                        if ('Deadlock found' in ex.message):
                            time.sleep((retry + 1) * 10)
                        else:
                            time.sleep(1)
                    except Exception as ex:
                        logger.warn('action=inject path=%s filename=%s msg=%s'
                                    % (_path, _filename, ex.message))
                        time.sleep(1)
                        raise
                    if (retry == 4):
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
        if (interval not in self.intervals):
            sys.exit(
                'action=rotate interval=%s must be in %s' %
                (interval, ','.join(sorted(self.intervals.keys()))))
        host_record = self.session.query(Host).filter_by(
            hostname=self.backup_host).one()
        interval_max = int(self.intervals[interval])

        try:
            ret = subprocess.call(['rsnapshot', '-c',
                                   self.rsnapshot_conf, interval])
        except Exception as ex:
            msg = 'action=rotate subprocess error=%s' % ex.message
            logger.error(msg)
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
            prev += ".%d" % (int(self.intervals[prev]) - 1)
        else:
            sys.exit('action=rotate interval=%s unrecognized' % interval)

        # delete savesets that match <interval>.<interval_max - 1>
        count = self.session.query(Saveset).filter_by(
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
        count = self.session.query(Saveset).filter(
            Saveset.location == prev,
            Saveset.backup_host_id == host_record.id,
            Saveset.finished is not None).update({
                Saveset.location: '%s.0' % interval})
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

        vol = self.session.query(Volume).filter_by(volume=volume).one()
        host_record = self.session.query(Host).filter_by(
            hostname=host).one()
        backup_host_record = self.session.query(Host).filter_by(
            hostname=self.backup_host).one()
        if (not host or not vol):
            sys.exit('Invalid host or volume')
        saveset = Saveset(
            saveset='%(host)s-%(volume)s-%(date)s' % dict(
                host=host,
                volume=volume,
                date=datetime.datetime.now().strftime('%Y%m%d-%H')),
            location=SYNC_PATH,
            host=host_record,
            backup_host=backup_host_record
        )
        try:
            self.session.add(saveset)
            self.session.commit()
        except sqlalchemy.exc.IntegrityError as ex:
            if ('Duplicate entry' in ex.message):
                sys.exit('ERROR: duplicate saveset=%s' % saveset.saveset)
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
                record = self.session.query(Saveset).filter_by(
                        saveset=saveset).one()
            except sqlalchemy.orm.exc.NoResultFound:
                raise RuntimeError('VERIFY saveset=%s not found' % saveset)

            count = missing = self.session.query(Backup).join(
                    File).filter(
                        Backup.saveset_id == record.id,
                        File.type == 'f',
                        File.shasum == None,  # noqa: E711
                        File.size > 0).count()
            (errors, skipped) = (0, 0)
            for file in self.session.query(Backup).join(
                    File).filter(
                        Backup.saveset_id == record.id,
                        File.type == 'f',
                        File.shasum != None,  # noqa: E711
                        File.size > 0):
                count += 1
                if (self.hashtype != self._hashtype(file.file.shasum)):
                    self.hashtype = self._hashtype(file.file.shasum)
                    logger.info('action=verify hashtype=%s' % self.hashtype)
                try:
                    filename = os.path.join(
                        self.snapshot_root, record.location, file.file.path,
                        file.file.filename)
                    sha = self._filehash(filename, self.hashtype)
                    if (sha != file.file.shasum):
                        logger.warn('BAD CHECKSUM: action=verify file=%s/%s '
                                    'expected=%s actual=%s' %
                                    (file.file.path, file.file.filename,
                                     binascii.hexlify(file.file.shasum),
                                     binascii.hexlify(sha)))
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
        items = self.session.query(Host).filter(
            Host.hostname.like(filter)).order_by('hostname')
        return {'hosts': [dict(
                    name=item.hostname,
                    created=item.created.strftime(self.time_fmt)
                    ) for item in items]}

    def list_savesets(self, filter):
        """List savesets"""
        items = self.session.query(Saveset).filter(
            Saveset.saveset.like(filter)).order_by('saveset')
        return {'savesets': [dict(
                    name=item.saveset, location=item.location,
                    created=item.created.strftime(self.time_fmt),
                    host=item.host.hostname,
                    backup_host=item.backup_host.hostname,
                    finished=item.finished.strftime(self.time_fmt) if
                             item.finished else None) for item in items]}

    def list_volumes(self, filter):
        """List volumes"""
        items = self.session.query(Volume).filter(
            Volume.volume.like(filter)).order_by('volume')
        return {'volumes': [dict(
                    name=item.volume, path=item.path, size=item.size,
                    created=item.created.strftime(self.time_fmt),
                    host=item.host.hostname) for item in items]}

    @staticmethod
    def _filehash(file, hashtype):
        """Read a file and return its hash

        Args:
            file (str): name of file
            hashtype (str): type of hash
        Returns:
            str:  binary digest (as 16, 32 or 64 bytes)
        Raises:
            OS exceptions
        """
        with open(file, 'r') as f:
            if (hashtype == 'md5'):
                return hashlib.md5(f.read()).digest()
            elif (hashtype == 'sha256'):
                return hashlib.sha256(f.read()).digest()
            elif (hashtype == 'sha512'):
                return hashlib.sha512(f.read()).digest()

    @staticmethod
    def _hashtype(shasum):
        """Identify hashtype of a shasum value

        Args:
            shasum (str): binary string
        Returns:
            str:  hash type md5, sha256 or sha512
        Raises:
            RuntimeError on failure
        """
        if (len(shasum) == 16):
            return 'md5'
        elif (len(shasum) == 32):
            return 'sha256'
        elif (len(shasum) == 64):
            return 'sha512'
        else:
            raise RuntimeError('Hash type of %s unrecognized' %
                               binascii.hexlify(shasum))

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


def main():
    global logger
    opts = docopt.docopt(__doc__)
    logger = Syslog(opts)
    obj = Secondshot(opts)
    obj.rsnapshot_cfg = ReadConfig().rsnapshot_cfg(
        opts['--rsnapshot-conf'])
    if ('snapshot_root' in obj.rsnapshot_cfg):
        obj.snapshot_root = obj.rsnapshot_cfg['snapshot_root'].rstrip('/')
    if ('retain' in obj.rsnapshot_cfg):
        obj.intervals = obj.rsnapshot_cfg['retain']
    else:
        obj.intervals = obj.rsnapshot_cfg['interval']
    filter = opts['--filter'].replace('*', '%')
    result = {}
    status = 'ok'

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
        sys.stdout.write(json.dumps(result) + '\n')
    elif (obj.format == 'text' and result and next(iter(result.keys())) in [
            'hosts', 'savesets', 'volumes']):
        for item in result[next(iter(result.keys()))]:
            sys.stdout.write(item['name'] + '\n')
    if (status != 'ok'):
        exit(1)


if __name__ == '__main__':
    main()
