"""test_base

Fixtures for testing

created 20-aug-2018 by richb@instantlinux.net

license: lgpl-2.1
"""

import os
from sqlalchemy import create_engine
import sqlalchemy.orm
import tempfile
import unittest

from secondshot.config import Config
from secondshot.constants import Constants
from secondshot.models import ConfigTable, Host, Volume, metadata


class TestBase(unittest.TestCase):

    def setUp(self):
        """Most tests require a database: this base class creates
        an in-memory sqlite instance with host/volume records
        and a couple of config entries."""

        self.logfile_name = tempfile.mkstemp(prefix='_test')[1]
        self.testhost = 'test'

        db_url = os.environ.get('DB_URL', 'sqlite:///:memory:')
        self.engine = create_engine(db_url)
        self.session = sqlalchemy.orm.scoped_session(
            sqlalchemy.orm.sessionmaker(
                autocommit=False, bind=self.engine))
        metadata.create_all(self.engine)
        record = Host(hostname=self.testhost)
        self.session.add(record)
        self.session.flush()
        self.testhost_id = record.id
        volume = Volume(
            volume=Constants.DEFAULT_VOLUME,
            path=Constants.SNAPSHOT_ROOT,
            host_id=self.testhost_id)
        self.session.add(volume)
        self.session.add(ConfigTable(
            keyword='autoverify', value='false',
            host_id=self.testhost_id))
        self.session.add(ConfigTable(
            keyword='host', value='test,cnn,fox',
            host_id=self.testhost_id))
        self.session.commit()
        self.volume_id = volume.id
        self.config = Config()
        self.config.init_db_get_config(self.session, self.testhost)

        self.cli = Constants.OPTS_DEFAULTS.copy()
        self.cli.update({
            'backup-host': self.testhost, 'host': [self.testhost],
            'db-url': None, 'filter': '*',
            'log-level': 'none', 'logfile': self.logfile_name,
            'sequence': 'default: hourly,daysago,weeksago,monthsago,\
semiannually,yearsago',
            'verbose': None, 'volume': Constants.DEFAULT_VOLUME})

    def tearDown(self):
        os.remove(self.logfile_name)
