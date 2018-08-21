import alembic.config
import alembic.script
import mock
import os

import test_base
from actions import Actions
from models import AlembicVersion
from syslogger import Syslog


class TestSchemaUpdate(test_base.TestBase):

    @mock.patch('syslogger.logger')
    def setUp(self, mock_log):
        super(TestSchemaUpdate, self).setUp()
        test_config = os.path.join(os.path.abspath(os.path.dirname(
            __file__)), '..', '..', 'etc', 'backup-daily.conf')
        self.cli.update({
            'backup-host': self.testhost, 'host': [self.testhost],
            'db-url': 'sqlite:///:memory:', 'filter': '*',
            'log-level': 'none', 'logfile': self.logfile_name,
            'rsnapshot-conf': test_config,
            'sequence': 'short', 'volume': 'test1', 'verbose': None})
        Syslog.logger = Syslog(self.cli)

    def test_schema_up_to_date(self):
        """The test_base class generates sqlite schema from model metadata.
        This test adds the get_heads alembic version_num and confirms that
        action schema-update skips migration.
        """

        cfg = alembic.config.Config()
        cfg.set_main_option('script_location', os.path.join(
            os.path.abspath(os.path.dirname(__file__)), '..', '..',
            'secondshot', 'alembic'))
        cfg.set_main_option('url', str(self.engine.url))
        script = alembic.script.ScriptDirectory.from_config(cfg)

        alembic_ver = script.get_heads()[0]
        self.session.add(AlembicVersion(version_num=alembic_ver))
        self.session.commit()

        expected = {
            'status': 'ok',
            'schema-update': [{'action': 'skipped', 'name': alembic_ver}]}

        obj = Actions(self.cli, db_engine=self.engine, db_session=self.session)
        ret = obj.schema_update()
        self.assertEqual(len(alembic_ver), 12)
        self.assertEqual(ret, expected)
