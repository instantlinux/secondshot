"""test_actions

Tests for Actions class

created 25-aug-2018 by richb@instantlinux.net

license: lgpl-2.1
"""

import binascii
from datetime import datetime
import mock
import os.path
import shutil
import subprocess
import tempfile

import test_base
from constants import Constants
from models import Backup, Saveset, Volume
from secondshot import Actions
from syslogger import Syslog


class TestActions(test_base.TestBase):

    @mock.patch('syslogger.logger')
    def setUp(self, mock_log):
        super(TestActions, self).setUp()
        self.snapshot_root = tempfile.mkdtemp(prefix='_testdir')
        self.saveset = 'saveset1'
        self.volume = 'test1'
        self.volume_path = os.path.join(self.snapshot_root,
                                        Constants.SYNC_PATH)
        self.testdata_path = tempfile.mkdtemp(prefix='_backup')
        subprocess.call(['tar', 'xf', os.path.join(os.path.abspath(
            os.path.dirname(__file__)), '..', 'testdata', 'testfiles.tar.bz'),
                '-C', self.testdata_path, '.'])
        self.rsnapshot_conf = tempfile.mkstemp(prefix='_test')[1]
        with open(self.rsnapshot_conf, 'w') as f:
            f.write(
                "include_conf	/etc/rsnapshot.conf\n"
                "snapshot_root	%(snapshot_root)s\n"
                "backup	%(testdata)s	%(hostname)s\n"
                "retain	short	2\n"
                "retain	long	3\n"
                "retain	longer	99\n" % dict(
                    snapshot_root=self.snapshot_root,
                    testdata=self.testdata_path,
                    hostname=self.testhost))
        self.cli.update({
            'action': 'start', 'sequence': 'short,long,longer',
            'rsnapshot-conf': self.rsnapshot_conf,
            'verbose': True, 'volume': self.volume})
        saveset = Saveset(
            location=Constants.SYNC_PATH, saveset=self.saveset,
            host_id=self.testhost_id,
            backup_host_id=self.testhost_id)
        volume = Volume(
            volume=self.volume,
            path=self.snapshot_root,
            host_id=self.testhost_id)
        self.session.add(saveset)
        self.session.add(volume)
        self.session.flush()
        self.saveset_id = saveset.id
        self.session.commit()

        Syslog.logger = Syslog(self.cli)

    def tearDown(self):
        super(TestActions, self).tearDown()

        os.remove(self.rsnapshot_conf)
        shutil.rmtree(self.snapshot_root)
        shutil.rmtree(self.testdata_path)

    @mock.patch('syslogger.Syslog._now')
    def test_new_saveset(self, mock_now):
        expected = dict(id=2, saveset='%s-%s-%s' % (
            self.testhost, self.volume, '20180801-13'))

        mock_now.return_value = datetime.strptime('Aug 1 2018  1:47PM',
                                                  '%b %d %Y %I:%M%p')
        obj = Actions(self.cli, db_engine=self.engine, db_session=self.session)
        ret = obj.new_saveset(self.testhost, self.volume)
        self.assertEqual(ret, expected)

    def test_inject(self):
        expected = dict(inject=dict(
            status='ok', saveset=self.saveset, file_count=15, skipped=0))

        shutil.copytree(
            self.testdata_path,
            os.path.join(self.volume_path, Constants.SYNC_PATH, self.testhost))
        obj = Actions(self.cli, db_engine=self.engine, db_session=self.session)
        ret = obj.inject(self.testhost, self.volume, self.volume_path,
                         self.saveset_id)
        self.assertEqual(ret, expected)

        # verify contents of database tables
        count = 0
        for item in self.session.query(Backup):
            self.assertEqual('/'.join(item.file.path.split('/')[:2]),
                             os.path.join(Constants.SYNC_PATH, self.testhost))
            self.assertEqual(item.file.size, 52)
            self.assertEqual(item.file.shasum, None)
            count += 1
        self.assertEqual(count, expected['inject']['file_count'])

    def test_calc_sums(self):
        expected = dict(calc_sums=dict(
            status='ok',
            saveset=self.saveset,
            size=780,
            processed=780))

        shutil.copytree(
            self.testdata_path,
            os.path.join(self.volume_path, Constants.SYNC_PATH, self.testhost))
        obj = Actions(self.cli, db_engine=self.engine, db_session=self.session)
        obj.inject(self.testhost, self.volume, self.volume_path,
                   self.saveset_id)
        ret = obj.calc_sums(self.saveset_id)
        self.assertEqual(ret, expected)

        count = 0
        for item in self.session.query(Backup):
            self.assertEqual(item.file.shasum,
                             binascii.unhexlify(item.file.filename[9:41]))
            count += 1
        self.assertEqual(count, 15)

    @mock.patch('subprocess.call')
    def test_rotate(self, mock_subprocess):
        mock_subprocess.return_value = 0
        expected = dict(rotate=dict(
            status='ok', actions=[dict(
                host=self.testhost,
                location='short.0',
                prev=Constants.SYNC_PATH,
                savesets=1)]))

        saveset = Saveset(
            location='short.0', saveset='testrotate',
            host_id=self.testhost_id,
            backup_host_id=self.testhost_id)

        self.maxDiff = None
        self.session.add(saveset)
        self.session.commit()

        shutil.copytree(
            self.testdata_path,
            os.path.join(self.volume_path, 'short.0', self.testhost))
        obj = Actions(self.cli, db_engine=self.engine, db_session=self.session)
        obj.inject(self.testhost, self.volume, self.volume_path,
                   saveset.id)
        ret = obj.rotate('short')
        self.assertEqual(ret, expected)
        mock_subprocess.assert_called_once_with(
            ['rsnapshot', '-c', self.rsnapshot_conf, 'short'])

        record = self.session.query(Saveset).filter(Saveset.saveset ==
                                                    'testrotate').one()
        self.assertEqual(record.location, 'short.1')

    @mock.patch('subprocess.call')
    @mock.patch('actions.Actions.verify')
    @mock.patch('actions.Actions.calc_sums')
    @mock.patch('actions.Actions.inject')
    @mock.patch('actions.Actions.new_saveset')
    def test_start(self, mock_saveset, mock_inject, mock_calc, mock_verify,
                   mock_subprocess):
        mock_subprocess.return_value = 0
        mock_saveset.return_value = dict(id=555, saveset='test')
        mock_inject.return_value = dict(inject=dict(
            status='ok', saveset='test', file_count=444, skipped=0))
        mock_calc.return_value = dict(calc_sums=dict(
            status='ok', saveset='test', size=150505, processed=4040))
        mock_verify.return_value = dict(verify=dict(
            status='ok', saveset='test', count=444, errors=0, missing=0,
            skipped=0))
        expected = dict(start=dict(
            status='ok', results=[
                mock_inject.return_value,
                mock_calc.return_value,
                mock_verify.return_value]))

        self.config.db_set('autoverify', 'true')
        obj = Actions(self.cli, db_engine=self.engine, db_session=self.session)
        ret = obj.start([self.testhost], self.volume)
        self.assertEqual(ret, expected)
        mock_saveset.assert_called_once_with(self.testhost, self.volume)
        mock_inject.assert_called_once_with(
            self.testhost, self.volume, '%s/%s' % (
                self.snapshot_root, Constants.SYNC_PATH), 555)
        mock_verify.assert_called_once_with(['test'])
        mock_subprocess.assert_called_once_with(
            ['rsnapshot', '-c', self.rsnapshot_conf, 'sync', self.testhost])

    def test_verify(self):
        expected = dict(verify=dict(
            status='ok', results=[dict(
                saveset=self.saveset,
                count=15,
                errors=0, missing=0, skipped=0)]))

        shutil.copytree(
            self.testdata_path,
            os.path.join(self.volume_path, Constants.SYNC_PATH, self.testhost))
        obj = Actions(self.cli, db_engine=self.engine, db_session=self.session)
        obj.inject(self.testhost, self.volume, self.volume_path,
                   self.saveset_id)
        ret = obj.calc_sums(self.saveset_id)
        ret = obj.verify([self.saveset])
        self.assertEqual(ret, expected)

    def test_list_hosts(self):
        expected = dict(hosts=[dict(name=self.testhost)])

        obj = Actions(self.cli, db_engine=self.engine, db_session=self.session)
        ret = obj.list_hosts()
        del(ret['hosts'][0]['created'])
        self.assertEqual(ret, expected)

    def test_list_savesets(self):
        expected = dict(savesets=[dict(
            name=self.saveset,
            location=Constants.SYNC_PATH,
            host=self.testhost,
            backup_host=self.testhost,
            finished=None)])

        obj = Actions(self.cli, db_engine=self.engine, db_session=self.session)
        ret = obj.list_savesets()
        del(ret['savesets'][0]['created'])
        self.assertEqual(ret, expected)

    def test_list_volumes(self):
        expected = dict(volumes=[
            dict(name=Constants.DEFAULT_VOLUME,
                 path=Constants.SNAPSHOT_ROOT,
                 host=self.testhost,
                 size=None),
            dict(name=self.volume,
                 path=self.snapshot_root,
                 host=self.testhost,
                 size=None)])

        obj = Actions(self.cli, db_engine=self.engine, db_session=self.session)
        ret = obj.list_volumes()
        del(ret['volumes'][0]['created'])
        del(ret['volumes'][1]['created'])
        self.assertEqual(ret, expected)

    def test_filehash(self):
        expected = dict(
            md5='724993f99db6ae3f6dd0f06f640ee865',
            sha256='84a48fed6fc0d3148f97a39d176059c7'
                   '777f524b513e4d1a136ede1cfe165cf7',
            sha512='418e33685a9dc21c68e68e0d5a69bef6'
                   '9dd068b1d1839167b65e08f00604e9a0'
                   'd01a4f34442844023763c452c9b838a1'
                   '0f8d370b6cb2803b3f64bae620566272')
        fname = os.path.join(self.testdata_path,
                             'TESTfile-%s.txt' % expected['md5'])

        for hash in ['md5', 'sha256', 'sha512']:
            self.assertEqual(binascii.hexlify(Actions._filehash(fname, hash)),
                             expected[hash])

    def test_hashtype(self):
        ret = Actions._hashtype(binascii.unhexlify(
            'd41d8cd98f00b204e9800998ecf8427e'))
        self.assertEqual(ret, 'md5')
        ret = Actions._hashtype(binascii.unhexlify(
            'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852'
            'b855'))
        self.assertEqual(ret, 'sha256')
        ret = Actions._hashtype(binascii.unhexlify(
            'cf83e1357eefb8bdf1542850d66d8007d620e4050b5715dc83f4a921d36c'
            'e9ce47d0d13c5d85f2b0ff8318d2877eec2f63b931bd47417a81a538327a'
            'f927da3e'))
        self.assertEqual(ret, 'sha512')
        with self.assertRaises(RuntimeError):
            Actions._hashtype('invalid')

    def test_filetype(self):
        self.assertEqual(Actions._filetype(0010000), 'p')
        self.assertEqual(Actions._filetype(0020000), 'c')
        self.assertEqual(Actions._filetype(0040000), 'd')
        self.assertEqual(Actions._filetype(0100000), 'f')
        self.assertEqual(Actions._filetype(0120000), 'l')
        self.assertEqual(Actions._filetype(0140000), 's')
        with self.assertRaises(RuntimeError):
            Actions._filetype(0)
