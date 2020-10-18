"""test_schema_update

Tests for alembic DB schema migrations

created 25-aug-2018 by richb@instantlinux.net

license: lgpl-2.1
"""

import alembic.config
import alembic.script
import mock
import os

import test_base
from secondshot import Actions
from secondshot.syslogger import Syslog
from secondshot.models import AlembicVersion


class TestSchemaUpdate(test_base.TestBase):

    @mock.patch('secondshot.syslogger.logger')
    def setUp(self, mock_log):
        super(TestSchemaUpdate, self).setUp()
        test_config = os.path.join(os.path.abspath(os.path.dirname(
            __file__)), '..', '..', 'etc', 'backup-daily.conf')
        self.cli.update({
            'db-url': 'sqlite:///:memory:',
            'rsnapshot-conf': test_config})
        Syslog.logger = Syslog(self.cli)

        cfg = alembic.config.Config()
        cfg.set_main_option('script_location', os.path.join(
            os.path.abspath(os.path.dirname(__file__)), '..',
            'secondshot', 'alembic'))
        cfg.set_main_option('url', str(self.engine.url))
        script = alembic.script.ScriptDirectory.from_config(cfg)
        self.alembic_ver = script.get_heads()[0]

    def test_schema_blank_db(self):
        """Apply migrations to a blank database.
        """

        expected = {
            'status': 'ok',
            'schema-update': [{'action': 'migrated',
                               'name': self.alembic_ver}]}

        obj = Actions(self.cli)
        ret = obj.schema_update()
        self.assertEqual(ret, expected)

    def test_schema_already_current(self):
        """The test_base class generates sqlite schema from model metadata.
        This test adds the get_heads alembic version_num and confirms that
        action schema-update skips migration.
        """

        self.session.add(AlembicVersion(version_num=self.alembic_ver))
        self.session.commit()

        expected = {
            'status': 'ok',
            'schema-update': [{'action': 'skipped', 'name': self.alembic_ver}]}

        obj = Actions(self.cli, db_engine=self.engine, db_session=self.session)
        ret = obj.schema_update()
        self.assertEqual(len(self.alembic_ver), 12)
        self.assertEqual(ret, expected)
