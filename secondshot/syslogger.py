"""syslogger

Syslog functions

created 11-aug-2018 by richb@instantlinux.net

license: lgpl-2.1
"""

import datetime
import logging
import logging.handlers
import os.path
import sys

logger = logging.getLogger()


class Syslog(object):

    def __init__(self, opts):
        global logger

        self.prog = os.path.basename(__file__).split('.')[0]
        self.log_facility = 'local1'
        self.syslog_enable = True
        if (opts['verbose'] or opts['log-level'].lower() == 'debug'):
            self.log_level = logging.DEBUG
        elif (opts['log-level'].lower() == 'info'):
            self.log_level = logging.INFO
        elif (opts['log-level'].lower() == 'warn'):
            self.log_level = logging.WARN
        elif (opts['log-level'].lower() == 'none'):
            self.log_level = logging.INFO
            self.syslog_enable = False
        else:
            sys.stderr.write('Unrecognized --log-level=%s' % opts['log-level'])
            self.log_level = logging.INFO
        if (self.syslog_enable):
            logger.setLevel(self.log_level)
            if (os.path.exists('/dev/log')):
                handler = logging.handlers.SysLogHandler(
                    address='/dev/log', facility=self.log_facility)
                logger.addHandler(handler)
            else:
                self.syslog_enable = False
        self.logfile = opts['logfile']

    def debug(self, msg):
        global logger
        if (self.log_level == logging.DEBUG):
            sys.stderr.write('DEBUG: %s\n' % msg)
            if (self.syslog_enable):
                logger.debug('%s %s' % (self.prog, msg))
            with open(self.logfile, 'a') as f:
                f.write(self._date_prefix('D', msg))

    def error(self, msg):
        global logger
        sys.stderr.write('ERROR: %s\n' % msg)
        if (self.syslog_enable):
            logger.error('%s %s' % (self.prog, msg))
        with open(self.logfile, 'a') as f:
            f.write(self._date_prefix('E', msg))

    def info(self, msg):
        global logger
        if (self.log_level == logging.DEBUG):
            sys.stderr.write('INFO: %s\n' % msg)
        if (self.syslog_enable):
            logger.info('%s %s' % (self.prog, msg))
        with open(self.logfile, 'a') as f:
            f.write(self._date_prefix('I', msg))

    def warn(self, msg):
        global logger
        sys.stderr.write('WARN: %s\n' % msg)
        if (self.syslog_enable):
            logger.warn('%s %s' % (self.prog, msg))
        with open(self.logfile, 'a') as f:
            f.write(self._date_prefix('W', msg))

    def _date_prefix(self, severity, msg):
        return '[%s] %s %s\n' % (
            self._now().strftime('%d/%b/%Y-%H:%M:%S'),
            severity, msg)

    @staticmethod
    def _now():
        return datetime.datetime.now()
