"""test_secondshot

Tests for main (docopt cli parser)

created 25-aug-2018 by richb@instantlinux.net

license: lgpl-2.1
"""

import json
import mock
import os
import sys
import tempfile

import test_base
from secondshot.main import main
from secondshot._version import __version__


class TestMain(test_base.TestBase):

    def setUp(self):
        super(TestMain, self).setUp()

        self.rsnapshot_conf = tempfile.mkstemp(prefix='_test')[1]
        with open(self.rsnapshot_conf, 'w') as f:
            f.write(
                "include_conf	/etc/rsnapshot.conf\n"
                "snapshot_root	%(snapshot_root)s\n"
                "backup	%(testdata)s	%(hostname)s\n"
                "retain	short	2\n"
                "retain	long	3\n" % dict(
                    snapshot_root='/backups',
                    testdata='/home',
                    hostname=self.testhost))

    def tearDown(self):
        super(TestMain, self).tearDown()
        os.remove(self.rsnapshot_conf)

    @mock.patch('secondshot.actions.Actions.list_hosts')
    def test_list_hosts(self, mock_list_hosts):
        sys.argv = ['secondshot', '--list-hosts',
                    '--logfile=%s' % self.logfile_name,
                    '--log-level=none',
                    '--rsnapshot-conf=%s' % self.rsnapshot_conf]
        mock_list_hosts.return_value = dict(hosts=[dict(
            name='test', created='2018-08-01 03:00:00')])
        main()
        mock_list_hosts.assert_called_once_with()

    @mock.patch('sys.stdout.write')
    @mock.patch('secondshot.actions.Actions.list_savesets')
    def test_list_savesets(self, mock_list_savesets, mock_stdout):
        sys.argv = ['secondshot', '--list-savesets',
                    '--logfile=%s' % self.logfile_name,
                    '--log-level=none',
                    '--rsnapshot-conf=%s' % self.rsnapshot_conf]
        mock_list_savesets.return_value = dict(savesets=[dict(
            name='test1', created='2018-08-01 03:00:00')])
        main()
        mock_list_savesets.assert_called_once_with()
        mock_stdout.assert_called_once_with('test1\n')

    @mock.patch('sys.stdout.write')
    @mock.patch('secondshot.actions.Actions.list_savesets')
    def test_json_format(self, mock_list_savesets, mock_stdout):
        sys.argv = ['secondshot', '--list-savesets', '--format=json',
                    '--logfile=%s' % self.logfile_name,
                    '--log-level=none',
                    '--rsnapshot-conf=%s' % self.rsnapshot_conf]
        mock_list_savesets.return_value = dict(savesets=[dict(
            name='test1', created='2018-08-01 03:00:00')])
        main()
        mock_list_savesets.assert_called_once_with()
        mock_stdout.assert_called_once_with(
            json.dumps(mock_list_savesets.return_value) + '\n')

    @mock.patch('secondshot.actions.Actions.start')
    def test_start(self, mock_start):
        sys.argv = ['secondshot', '--action=start',
                    '--logfile=%s' % self.logfile_name,
                    '--log-level=none',
                    '--rsnapshot-conf=%s' % self.rsnapshot_conf]
        inject = dict(inject=dict(
            status='ok', saveset='test', file_count=444, skipped=0))
        calc = dict(calc_sums=dict(
            status='ok', saveset='test', size=150505, processed=4040))
        verify = dict(verify=dict(
            status='ok', saveset='test', count=444, errors=0, missing=0,
            skipped=0))

        mock_start.return_value = dict(start=dict(
            status='ok', results=[inject, calc, verify]))
        main()
        mock_start.assert_called_once()

    @mock.patch('secondshot.actions.Actions.list_volumes')
    @mock.patch('secondshot.actions.Actions.verify')
    @mock.patch('secondshot.actions.Actions.rotate')
    def test_misc_actions(self, mock_rotate, mock_verify, mock_volumes):
        sys.argv = ['secondshot', '--list-volumes',
                    '--logfile=%s' % self.logfile_name,
                    '--log-level=none',
                    '--rsnapshot-conf=%s' % self.rsnapshot_conf]
        mock_volumes.return_value = dict(volumes=[dict(
            name='test1', created='2018-08-01 03:00:00')])
        mock_verify.return_value = dict(verify=dict(
            status='ok', saveset='test', count=444, errors=0, missing=0,
            skipped=0))
        mock_rotate.return_value = dict(rotate=dict(
            status='ok', actions=[dict(
                host=self.testhost,
                location='short.0', prev='.sync', savesets=1)]))
        main()
        sys.argv[1] = '--verify=test'
        main()
        sys.argv[1] = '--action=rotate'
        sys.argv.append('--interval=short')
        main()

        mock_volumes.assert_called_once_with()
        mock_verify.assert_called_once_with(['test'])
        mock_rotate.assert_called_once_with('short')

    @mock.patch('sys.stdout.write')
    def test_version(self, mock_stdout):
        sys.argv = ['secondshot', '--version',
                    '--logfile=%s' % self.logfile_name]
        main()
        mock_stdout.assert_called_once_with(
            'secondshot %s\n' % __version__)

    @mock.patch('secondshot.actions.Actions.schema_update')
    def test_schema_update(self, mock_schema_update):
        sys.argv = ['secondshot', '--action=schema-update',
                    '--logfile=%s' % self.logfile_name,
                    '--log-level=none',
                    '--rsnapshot-conf=%s' % self.rsnapshot_conf]
        mock_schema_update.return_value = {
            'status': 'ok',
            'schema-update': [dict(name='4170b1e2a53d533d',
                                   action='migrated')]}
        main()
        mock_schema_update.assert_called_once()

    @mock.patch('secondshot.actions.Actions.schema_update')
    def test_schema_error(self, mock_schema_update):
        sys.argv = ['secondshot', '--action=schema-update',
                    '--logfile=%s' % self.logfile_name,
                    '--log-level=none',
                    '--rsnapshot-conf=%s' % self.rsnapshot_conf]
        mock_schema_update.return_value = {
            'status': 'error',
            'schema-update': []}
        with self.assertRaises(SystemExit):
            main()

    def test_bad_action(self):
        sys.argv = ['secondshot', '--action=invalid',
                    '--logfile=%s' % self.logfile_name,
                    '--log-level=none',
                    '--rsnapshot-conf=%s' % self.rsnapshot_conf]
        with self.assertRaises(SystemExit):
            main()
