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


class Syslog(object):
    global logger

    def __init__(self, opts):
        global logger

        self.prog = os.path.basename(__file__).split('.')[0]
        self.logger = logging.getLogger()
        self.log_facility = 'local1'
        if (opts['verbose']):
            self.log_level = logging.DEBUG
        else:
            self.log_level = logging.INFO
        self.logger.setLevel(self.log_level)
        if (os.path.exists('/dev/log')):
            handler = logging.handlers.SysLogHandler(
                address='/dev/log', facility=self.log_facility)
            self.logger.addHandler(handler)
            self.syslog_enable = True
        else:
            self.syslog_enable = False
        self.logfile = opts['logfile']
        logger = self

    def debug(self, msg):
        if (self.log_level == logging.DEBUG):
            sys.stderr.write('DEBUG: %s\n' % msg)
            if (self.syslog_enable):
                self.logger.debug('%s %s' % (self.prog, msg))
            with open(self.logfile, 'a') as f:
                f.write(self._date_prefix('D', msg))

    def error(self, msg):
        sys.stderr.write('ERROR: %s\n' % msg)
        if (self.syslog_enable):
            self.logger.error('%s %s' % (self.prog, msg))
        with open(self.logfile, 'a') as f:
            f.write(self._date_prefix('E', msg))

    def info(self, msg):
        if (self.log_level == logging.DEBUG):
            sys.stderr.write('INFO: %s\n' % msg)
        if (self.syslog_enable):
            self.logger.info('%s %s' % (self.prog, msg))
        with open(self.logfile, 'a') as f:
            f.write(self._date_prefix('I', msg))

    def warn(self, msg):
        sys.stderr.write('WARN: %s\n' % msg)
        if (self.syslog_enable):
            self.logger.warn('%s %s' % (self.prog, msg))
        with open(self.logfile, 'a') as f:
            f.write(self._date_prefix('W', msg))

    def _date_prefix(self, severity, msg):
        return '[%s] %s %s\n' % (
            self._now().strftime('%d/%b/%Y-%H:%M:%S'),
            severity, msg)

    @staticmethod
    def _now():
        return datetime.datetime.now()
