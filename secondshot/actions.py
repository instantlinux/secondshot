"""actions

Secondshot action logic

created 11-aug-2018 by richb@instantlinux.net

license: lgpl-2.1
"""

import alembic.config
import alembic.script
from alembic.runtime.environment import EnvironmentContext
import binascii
import datetime
import grp
import hashlib
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
    from config import Config
    from constants import Constants
    from models import (Backup, File, Host, Saveset, Volume, metadata,
                        AlembicVersion)
    from syslogger import Syslog
else:
    from .config import Config
    from .constants import Constants
    from .models import (Backup, File, Host, Saveset, Volume, metadata,
                         AlembicVersion)
    from .syslogger import Syslog


class Actions(object):

    def __init__(self, opts, db_engine=None, db_session=None):
        """Initialize database session"""

        if (db_session):
            self.engine = db_engine
            self.session = db_session
        else:
            self.db_url = Config.get_db_url(opts)
            self.engine = create_engine(self.db_url)
            self.session = sqlalchemy.orm.scoped_session(
                sqlalchemy.orm.sessionmaker(autocommit=False,
                                            bind=self.engine))
        self.set_options(opts)

    def set_options(self, cli_opts):
        """Set configs and define runtime instance variables

        Args:
            cli_opts (dict): command-line as parsed by docopt
        """

        cfg = Config()
        if (cli_opts['backup-host']):
            self.backup_host = cli_opts['backup-host']
        else:
            self.backup_host = socket.gethostname().split('.')[0]
        runtime = cfg.set_opts(cli_opts, self.session, self.backup_host)

        Syslog.logger.debug("Running with options %s" % str(runtime))

        self.filter = runtime['filter'].replace('*', '%')
        self.hosts = runtime['host']
        self.rsnapshot_cfg = cfg.rsnapshot_cfg()
        self.time_fmt = '%Y-%m-%d %H:%M:%S'
        self.volume = runtime['volume']

        if ('snapshot_root' in self.rsnapshot_cfg):
            Config.snapshot_root = self.rsnapshot_cfg[
                'snapshot_root'].rstrip('/')
        if ('retain' in self.rsnapshot_cfg):
            self.intervals = self.rsnapshot_cfg['retain']
        elif ('interval' in self.rsnapshot_cfg):
            self.intervals = self.rsnapshot_cfg['interval']
        else:
            self.intervals = Config.sequence

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
            Syslog.logger.warn('action=calc_sums msg=%s' % str(ex))
            Syslog.logger.traceback(ex)
        if (not host or not location):
            sys.exit('action=calc_sums msg=missing host/location')
        total = self.session.query(sqlalchemy.sql.func.sum(
            File.size).label('total')).filter(
            Backup.saveset_id == saveset_id).join(
            Backup, File.id == Backup.file_id).one()[0]
        Syslog.logger.info('START action=calc_sums saveset=%s (size=%.3fGB) '
                           'from host=%s for location=%s' %
                           (saveset, float(total) / 1e9, host, location))
        (bytes, count) = (0, 0)
        for file in missing_sha:
            count += 1
            try:
                filename = os.path.join(
                    Config.snapshot_root, location, file.file.path,
                    file.file.filename).encode('utf8').decode('ISO-8859-1')
                file.file.shasum = self._filehash(filename, Config.hashtype)
                self.session.add(file.file)
                bytes += file.file.size
            except Exception as ex:
                Syslog.logger.warn('action=calc_sums id=%d msg=skipped '
                                   'error=%s' % (file.file.id, str(ex)))
            if (count % 1000 == 0):
                Syslog.logger.debug('action=calc_sums count=%d bytes=%d' %
                                    (count, bytes))
                self.session.commit()

        self.session.commit()
        Syslog.logger.info('FINISHED action=calc_sums saveset=%s '
                           'processed=%.3fGB' %
                           (saveset, float(bytes) / 1e9))
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
            sys.exit('action=inject Invalid host or volume: %s' % str(ex))

        (count, skipped) = (0, 0)
        for dirpath, _, filenames in os.walk(pathname):
            for filename in filenames:
                try:
                    stat = os.lstat(os.path.join(dirpath, filename))
                    _path = pymysql.escape_string(os.path.relpath(
                        dirpath, Config.snapshot_root + '/' +
                        Constants.SYNC_PATH).encode(
                        'utf8', 'surrogateescape').decode('ISO-8859-1'))
                    _filename = pymysql.escape_string(filename.encode(
                        'utf8', 'surrogateescape').decode('ISO-8859-1'))
                except OSError as ex:
                    if ex.errno != 2:
                        Syslog.logger.error(
                            'action=inject filename=%s message=%s' %
                            (filename, str(ex)))
                        raise
                    skipped += 1
                    Syslog.logger.debug('action=inject path=%s filename=%s '
                                        'msg=%s' %
                                        (dirpath, filename, str(ex)))
                    continue
                except UnicodeDecodeError as ex:
                    msg = 'action=inject inode=inode=%d dev=%s' % (
                        stat.st_ino, stat.st_dev)
                    try:
                        msg += ' path=%s filename=%s msg=%s' % (
                            dirpath, filename, str(ex))
                    except Exception:
                        pass
                    skipped += 1
                    Syslog.logger.debug(msg)
                    continue
                record = dict(
                    path=_path,
                    filename=_filename,
                    ctime=datetime.datetime.fromtimestamp(
                        stat.st_ctime).strftime(self.time_fmt),
                    gid=stat.st_gid,
                    last_backup=Syslog._now().strftime(
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
                        if (self.engine.name == 'sqlite'):
                            # sqlite lacks UPSERT capability, but this is
                            # good enough for exisiting unit-test. TODO: fix
                            #  this so we don't require a 'real' SQL.
                            sql_insert1 = (
                                u"INSERT OR IGNORE INTO files (%(columns)s)"
                                u" VALUES('%(values)s');" % dict(
                                    columns=','.join(record.keys()),
                                    values="','".join(str(item) for item
                                                      in record.values()),
                                    owner=owner, group=group))
                            sql_insert2 = (
                                "INSERT INTO backups (saveset_id,volume_id,"
                                "file_id) VALUES(%(saveset_id)d,%(volume_id)d,"
                                "LAST_INSERT_ROWID());" %
                                dict(saveset_id=saveset.id, volume_id=vol.id))
                        else:
                            sql_insert1 = (
                                u"INSERT INTO files (%(columns)s)"
                                u" VALUES('%(values)s')"
                                u" ON DUPLICATE KEY UPDATE owner='%(owner)s',"
                                u"grp='%(group)s',id=LAST_INSERT_ID(id),"
                                u"last_backup=NOW();" % dict(
                                    columns=','.join(record.keys()),
                                    values="','".join(str(item) for item
                                                      in record.values()),
                                    owner=owner, group=group))
                            sql_insert2 = (
                                "INSERT INTO backups (saveset_id,volume_id,"
                                "file_id) VALUES(%(saveset_id)d,%(volume_id)d,"
                                "LAST_INSERT_ID());" %
                                dict(saveset_id=saveset.id, volume_id=vol.id))
                        self.session.execute(sql_insert1)
                        self.session.execute(sql_insert2)
                        break
                    except sqlalchemy.exc.OperationalError as ex:
                        Syslog.logger.warn('action=inject path=%s filename=%s '
                                           'msg=%s' %
                                           (_path, _filename, str(ex)))
                        if ('Deadlock found' in str(ex)):
                            time.sleep((retry + 1) * 10)
                        else:
                            time.sleep(1)
                    except Exception as ex:
                        Syslog.logger.warn('action=inject path=%s filename=%s '
                                           'msg=%s' %
                                           (_path, _filename, str(ex)))
                        time.sleep(1)
                        raise
                    if (retry == 4):
                        skipped += 1
                count += 1
                if (count % Constants.MAX_INSERT == 0):
                    Syslog.logger.debug('action=inject count=%d' % count)
                    self.session.commit()

        self.session.commit()
        saveset.finished = sqlalchemy.func.now()
        self.session.add(saveset)
        self.session.commit()
        Syslog.logger.info('FINISHED action=inject saveset=%s, file_count=%d, '
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
                                   Config.rsnapshot_conf, interval])
        except Exception as ex:
            msg = 'action=rotate subprocess error=%s' % str(ex)
            Syslog.logger.error(msg)
            Syslog.logger.traceback(ex)
            sys.exit(msg)
        if (ret != 0):
            msg = 'action=rotate subprocess returned=%d' % ret
            Syslog.logger.error(msg)
            sys.exit(msg)

        # figure out oldest item in previous interval
        if (interval in ['hourly', 'main', 'short']):
            prev = Constants.SYNC_PATH
        elif (interval in Config.sequence):
            prev = Config.sequence[Config.sequence.index(interval) - 1]
            prev += ".%d" % (int(self.intervals[prev]) - 1)
        else:
            sys.exit('action=rotate interval=%s unrecognized' % interval)

        # delete savesets that match <interval>.<interval_max - 1>
        count = self.session.query(Saveset).filter_by(
            location='%s.%d' % (interval, interval_max - 1),
            backup_host_id=host_record.id).delete()
        if (count > 0):
            results.append(dict(
                action='delete',
                host=self.backup_host,
                location='%s.%d' % (interval, interval_max - 1),
                savesets=count))
            Syslog.logger.info(
                'action=rotate host=%s location=%s.%d savesets=%d removed' %
                (self.backup_host, interval, interval_max - 1, count))

        # move all savesets location <interval>.<n> => <n+1>
        if (self.engine.name == 'sqlite'):
            self.session.execute(
                "UPDATE savesets SET location='%(interval)s'||'.'||"
                "(SUBSTR(location,INSTR(location,'.')+1)+1) WHERE location "
                "LIKE '%(interval)s%%' AND backup_host_id=%(host)d" % {
                    'interval': interval, 'host': host_record.id})
        else:
            self.session.execute(
                "UPDATE savesets SET location=CONCAT('%(interval)s','.',"
                "SUBSTR(location,INSTR(location,'.')+1)+1) WHERE location "
                "LIKE '%(interval)s%%' AND backup_host_id=%(host)d" % {
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
            Syslog.logger.info('action=rotate host=%s savesets=%d '
                               'location=%s.0 prev=%s' %
                               (self.backup_host, count, interval, prev))
        self.session.commit()
        return {'rotate': dict(status='ok' if results else 'error',
                               actions=results)}

    def start(self, hosts, volume):
        """Start a backup for each of the specified hosts; if
        successful, also calculate sha checksums for any missing
        entries and re-read each stored file to verify

        Args:
            hosts (list):      hosts to back up
            volume (str):      volume path of destination
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
                Syslog.logger.error('action=start database error=%s'
                                    % str(ex))
                status = 'error'
                continue
            try:
                ret = subprocess.call(['rsnapshot', '-c',
                                       Config.rsnapshot_conf, 'sync', host])
            except Exception as ex:
                Syslog.logger.error('action=start subprocess error=%s'
                                    % str(ex))
                status = 'error'
                continue
            if (ret != 0):
                Syslog.logger.error('action=start rsnapshot process error=%d'
                                    % ret)
                status = 'error'
                continue
            try:
                results.append(
                    self.inject(host, volume, '%s/%s' %
                                (Config.snapshot_root, Constants.SYNC_PATH),
                                saveset_id))
            except Exception as ex:
                Syslog.logger.error('action=start inject error=%s' % str(ex))
                Syslog.logger.traceback(ex)
                status = 'error'
                continue
            results.append(self.calc_sums(saveset_id))
            if (Config.autoverify):
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
                date=Syslog._now().strftime('%Y%m%d-%H')),
            location=Constants.SYNC_PATH,
            host=host_record,
            backup_host=backup_host_record
        )
        try:
            self.session.add(saveset)
            self.session.commit()
        except sqlalchemy.exc.IntegrityError as ex:
            if ('Duplicate entry' in str(ex)):
                sys.exit('ERROR: duplicate saveset=%s' % saveset.saveset)
        Syslog.logger.info('START saveset=%s' % saveset.saveset)
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
                if (Config.hashtype != self._hashtype(file.file.shasum)):
                    Config.hashtype = self._hashtype(file.file.shasum)
                    Syslog.logger.info('action=verify hashtype=%s'
                                       % Config.hashtype)
                try:
                    filename = os.path.join(
                        Config.snapshot_root, record.location, file.file.path,
                        file.file.filename)
                    sha = self._filehash(filename, Config.hashtype)
                    if (sha != file.file.shasum):
                        Syslog.logger.warn(
                            'BAD CHECKSUM: action=verify file=%s/%s '
                            'expected=%s actual=%s' %
                            (file.file.path, file.file.filename,
                             binascii.hexlify(file.file.shasum),
                             binascii.hexlify(sha)))
                        errors += 1
                except Exception as ex:
                    Syslog.logger.debug('sha(%s): %s' % (
                        file.file.filename, str(ex)))
                    skipped += 1
                if (count % 1000 == 0):
                    Syslog.logger.debug('action=verify count=%d skipped=%d '
                                        'errors=%d' % (count, skipped, errors))

            msg = ('VERIFY: saveset=%s count=%d errors=%d missing=%d '
                   'skipped=%d' % (saveset, count, errors, missing, skipped))
            if (errors):
                Syslog.logger.error(msg)
            else:
                Syslog.logger.info(msg)
            results.append(dict(
                saveset=saveset, count=count, errors=errors,
                missing=missing, skipped=skipped))

        return {'verify': dict(
            status='ok' if errors == 0 else 'error',
            results=results)}

    def schema_update(self):
        """Examines the Alembic schema version and performs database
        migration if needed

        Returns:
            result (dict): summary of changes made
                  status = ok if no errors
        """

        results = []
        errors = 0
        try:
            version = self.session.query(AlembicVersion).one().version_num
        except (sqlalchemy.orm.exc.NoResultFound,
                sqlalchemy.exc.OperationalError,
                sqlalchemy.exc.ProgrammingError) as ex:
            Syslog.logger.warn('DB schema does not yet exist: %s' % str(ex))
            version = None
        cfg = alembic.config.Config()
        cfg.set_main_option('script_location', os.path.join(
            os.path.abspath(os.path.dirname(__file__)), 'alembic'))
        cfg.set_main_option('url', str(self.engine.url))
        script = alembic.script.ScriptDirectory.from_config(cfg)
        env = EnvironmentContext(cfg, script)
        if (version == script.get_heads()[0]):
            Syslog.logger.info('action=schema-update version=%s is current, '
                               'skipping' % version)
            results.append(dict(name=version, action='skipped'))
        else:
            def _do_upgrade(revision, context):
                return script._upgrade_revs(script.get_heads(), revision)

            conn = self.engine.connect()
            env.configure(connection=conn, target_metadata=metadata,
                          fn=_do_upgrade)
            with env.begin_transaction():
                env.run_migrations()
            results.append(dict(name=script.get_heads()[0], action='migrated'))
            Syslog.logger.info('action=schema-update finished migration, '
                               'version=%s' % script.get_heads()[0])
            if (version is None):
                # Seed a new db with host and volume records

                record = Host(hostname=self.backup_host)
                self.session.add(record)
                self.session.flush()
                self.session.add(Volume(
                    volume=Constants.DEFAULT_VOLUME,
                    path=Constants.SNAPSHOT_ROOT,
                    host_id=record.id))
                self.session.commit()
        return {
            'status': 'ok' if errors == 0 else 'error',
            'schema-update': results}

    def list_hosts(self):
        """List hosts"""
        items = self.session.query(Host).filter(
            Host.hostname.like(self.filter)).order_by('hostname')
        return {'hosts': [dict(
                    name=item.hostname,
                    created=item.created.strftime(self.time_fmt)
                    ) for item in items]}

    def list_savesets(self):
        """List savesets"""
        items = self.session.query(Saveset).filter(
            Saveset.saveset.like(self.filter)).order_by('saveset')
        return {'savesets': [dict(
                    name=item.saveset, location=item.location,
                    created=item.created.strftime(self.time_fmt),
                    host=item.host.hostname,
                    backup_host=item.backup_host.hostname,
                    finished=item.finished.strftime(self.time_fmt) if
                             item.finished else None) for item in items]}

    def list_volumes(self):
        """List volumes"""
        items = self.session.query(Volume).filter(
            Volume.volume.like(self.filter)).order_by('volume')
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
        with open(file, 'rb') as f:
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
            msg = ('Hash type of %s unrecognized' % binascii.hexlify(shasum))
            Syslog.logger.error(msg)
            raise RuntimeError(msg)

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
        elif (stat.S_ISLNK(mode)):
            return 'l'
        elif (stat.S_ISSOCK(mode)):
            return 's'
        elif (stat.S_ISFIFO(mode)):
            return 'p'
        else:
            raise RuntimeError('Unexpected file mode %d' % mode)
