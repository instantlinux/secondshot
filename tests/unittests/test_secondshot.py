import mock
import unittest2
import sys

# from secondshot import main, Actions, Syslog


class TestMain(unittest2.TestCase):

    @mock.patch('actions.Actions.list_hosts')
    @mock.patch('syslogger.Syslog')
    def test_actions(self, mock_log, mock_list_hosts):
        sys.argv = ['secondshot', '--list-hosts']
        """ TODO
        main()
        mock_log.return_value = 'foo'
        mock_list_hosts.return_value = dict(
            name='test', created='2018-08-01 03:00:00')
        """
