from datetime import datetime
import mock
import unittest2

from secondshot import Syslog


class TestSyslog(unittest2.TestCase):

    @mock.patch('syslogger.Syslog._now')
    def test_data_prefix(self, mock_now):
        mock_now.return_value = datetime.strptime('Aug 1 2018  1:47PM',
                                                  '%b %d %Y %I:%M%p')
        ret = Syslog({'verbose': False, 'logfile': None,
                      'log-level': 'none'})._date_prefix('W', 'test log')
        self.assertEqual(ret, '[01/Aug/2018-13:47:00] W test log\n')
