"""test_config

Tests for Config class

created 25-aug-2018 by richb@instantlinux.net

license: lgpl-2.1
"""

import os.path
import shutil
import tempfile

import test_base
from secondshot import Config, Constants
from secondshot.models import ConfigTable


class TestConfig(test_base.TestBase):

    def test_get_config_from_db(self):
        cfg = Config()
        ret = cfg.init_db_get_config(self.session, self.testhost)
        self.assertEqual(ret, dict(
            autoverify='false', host=['test', 'cnn', 'fox']))

        self.session.add(ConfigTable(keyword='hashtype', value='sha256',
                                     host_id=self.testhost_id))
        self.session.commit()
        ret = cfg.init_db_get_config(self.session, self.testhost)
        self.assertEqual(ret, dict(
            autoverify='false', host=['test', 'cnn', 'fox'],
            hashtype='sha256'))

        cfg.db_set('autoverify', 'true')
        ret = cfg.init_db_get_config(self.session, self.testhost)
        self.assertEqual(ret, dict(
            autoverify='true', host=['test', 'cnn', 'fox'],
            hashtype='sha256'))

        ret = Config().init_db_get_config(self.session, 'not-a-host')
        self.assertEqual(ret, {})

    def test_validate_configs(self):
        cfg = Config()
        cfg.validate_configs(dict(hashtype='sha256'), ['hashtype'])
        cfg.validate_configs(dict(autoverify='yes'), ['autoverify'])
        with self.assertRaises(ValueError):
            cfg.validate_configs(dict(autoverify='badvalue'), ['autoverify'])
        with self.assertRaises(ValueError):
            cfg.validate_configs(dict(format='badvalue'), ['format'])
        with self.assertRaises(ValueError):
            cfg.validate_configs(dict(hashtype='badvalue'), ['hashtype'])
        with self.assertRaises(ValueError):
            cfg.validate_configs(dict(boguskeyword='test'), ['command'])

    def test_db_set_new_item(self):
        cfg = Config()
        cfg.init_db_get_config(self.session, self.testhost)
        ret = cfg.db_get('volume')
        self.assertEqual(ret, None)
        cfg.db_set('volume', 'mybackup')
        ret = cfg.db_get('volume')
        self.assertEqual(ret, 'mybackup')

    def test_get_db_url(self):
        ret = Config.get_db_url({
            'dbhost': 'database',
            'dbname': 'secondshot',
            'dbpass': 'password',
            'dbport': 3306,
            'dbtype': 'mysql+pymysql',
            'dbuser': 'bkp',
            'db-url': None})
        self.assertEqual(ret, 'mysql+pymysql://bkp:password@database:3306/'
                         'secondshot')

        ret = Config.get_db_url({
            'dbhost': 'database',
            'dbname': 'testdb',
            'dbpass': 'password',
            'dbport': 3306,
            'dbtype': 'sqlite',
            'dbuser': 'bkp',
            'db-url': None})
        self.assertEqual(ret, 'sqlite:////metadata/testdb')

        ret = Config.get_db_url({
            'dbhost': 'database',
            'dbname': 'secondshot',
            'dbpass': 'password',
            'dbport': 3306,
            'dbtype': 'mysql+pymysql',
            'dbuser': 'bkp',
            'db-url': 'postgresql://backup:password@database:5432/secondshot'})
        self.assertEqual(ret, 'postgresql://backup:password@database:5432/'
                         'secondshot')

    def test_docopt_convert(self):
        ret = Config().docopt_convert({'--test': 'value'})
        self.assertEqual(ret, {'test': 'value'})

    def test_rsnapshot_cfg(self):
        expected = dict(
            exclude_file='/var/lib/ilinux/rsnap/etc/exclude',
            include_conf=['/etc/rsnapshot.conf'],
            logfile='/var/log/rsnapshot',
            one_fs='1',
            retain=dict(
                hourly='3',
                daysago='7',
                weeksago='4',
                monthsago='6',
                semiannually='2',
                yearsago='99'),
            snapshot_root='/var/backup/daily/',
            ssh_args='-i /home/secondshot/.ssh/id_rsa -c aes192-ctr')

        test_config = os.path.join(os.path.abspath(os.path.dirname(
            __file__)), '..', 'etc', 'backup-daily.conf')
        Config.rsnapshot_conf = test_config
        ret = Config().rsnapshot_cfg()
        self.assertEqual(ret, expected)

        temp = tempfile.mkstemp(prefix='_test')[1]
        shutil.copyfile(test_config, temp)
        with open(temp, 'a') as f:
            f.write('badcommand')
        Config.rsnapshot_conf = temp
        with self.assertRaises(SyntaxError):
            Config().rsnapshot_cfg()

        shutil.copyfile(test_config, temp)
        with open(temp, 'a') as f:
            f.write('logfile	/var/log/dup')
            f.write('logfile	/var/log/dup')
        with self.assertRaises(SyntaxError):
            Config().rsnapshot_cfg()

        os.remove(temp)

    def test_set_opts(self):
        expected = {
            'action': 'list-hosts',
            'autoverify': 'false',
            'db-url': None,
            'dbhost': 'db00',
            'dbname': 'secondshot',
            'dbpass': None,
            'dbport': '3306',
            'dbtype': 'sqlite',
            'dbuser': 'bkp',
            'hashtype': 'md5',
            'host': ['test', 'cnn', 'fox'],
            'logfile': '/var/log/test',
            'manifest': '.snapshot-manifest',
            'rsnapshot-conf': Constants.OPTS_DEFAULTS['rsnapshot-conf'],
            'sequence': 'default'}

        cli = Constants.OPTS_DEFAULTS.copy()
        cli.update(dict(
            logfile='/var/log/test', action='list-hosts',
            host=[self.testhost], sequence='default'))
        cfg = Config()
        ret = cfg.set_opts(cli, self.session, self.testhost)
        self.assertEqual(ret, expected)

        # DB value takes precedence over CLI (TODO: reverse that)
        cli['autoverify'] = 'true'
        expected['autoverify'] = 'false'
        ret = cfg.set_opts(cli, self.session, self.testhost)
        self.assertEqual(ret, expected)

        # DB value not present, verify CLI value
        cli['hashtype'] = 'sha256'
        expected['hashtype'] = 'sha256'
        ret = cfg.set_opts(cli, self.session, self.testhost)
        self.assertEqual(ret, expected)

    def test_set_opts_bad_dbentry(self):
        cfg = Config()
        cfg.init_db_get_config(self.session, self.testhost)

        cli = Constants.OPTS_DEFAULTS.copy()
        cli['badopt'] = 'test'
        with self.assertRaises(SystemExit):
            cfg.set_opts(cli, self.session, self.testhost)

        cfg.db_set('badopt', 'test')
        cli = Constants.OPTS_DEFAULTS.copy()
        with self.assertRaises(SystemExit):
            cfg.set_opts(cli, self.session, self.testhost)
