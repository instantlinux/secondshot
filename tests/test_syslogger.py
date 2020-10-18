"""test_syslogger

Tests for Syslog class

created 25-aug-2018 by richb@instantlinux.net

license: lgpl-2.1
"""

from datetime import datetime
import mock
import os
import tempfile
import unittest

from secondshot.syslogger import Syslog


class TestSyslog(unittest.TestCase):

    @mock.patch('secondshot.syslogger.Syslog._now')
    def test_data_prefix(self, mock_now):
        mock_now.return_value = datetime.strptime('Aug 1 2018  1:47PM',
                                                  '%b %d %Y %I:%M%p')
        ret = Syslog({'verbose': False, 'logfile': None,
                      'log-level': 'none'})._date_prefix('W', 'test log')
        self.assertEqual(ret, '[01/Aug/2018-13:47:00] W test log\n')

    @mock.patch('sys.stderr.write')
    @mock.patch('logging.Logger.warn')
    def test_syslog_warn(self, mock_logger, mock_stderr):
        logfile_name = tempfile.mkstemp(prefix='_test')[1]
        Syslog({'log-level': 'warn', 'logfile': logfile_name,
                'verbose': None})
        Syslog.logger.warn('test')
        mock_stderr.assert_called_once_with('WARN: test\n')
        # TODO: not yet working in pipeline
        # mock_logger.assert_called_once_with('secondshot test')
        os.remove(logfile_name)

    @mock.patch('sys.stderr.write')
    @mock.patch('logging.Logger.error')
    def test_syslog_error(self, mock_logger, mock_stderr):
        logfile_name = tempfile.mkstemp(prefix='_test')[1]
        Syslog({'log-level': 'info', 'logfile': logfile_name,
                'verbose': None})
        Syslog.logger.error('test')
        mock_stderr.assert_called_once_with('ERROR: test\n')
        # TODO: not yet working in pipeline
        # mock_logger.assert_called_once_with('secondshot test')
        os.remove(logfile_name)

    @mock.patch('sys.stderr.write')
    def test_syslog_init_badopt(self, mock_stderr):
        Syslog({'log-level': 'invalid', 'logfile': None, 'verbose': None})
        mock_stderr.assert_called_once_with(
            'Unrecognized --log-level=invalid\n')
