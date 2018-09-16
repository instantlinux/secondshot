"""config

Configuration-file parsing

created 11-aug-2018 by richb@instantlinux.net

license: lgpl-2.1
"""

import os
import sqlalchemy.exc
import sys

if (sys.version_info.major == 2):
    from constants import Constants
    from models import ConfigTable, Host
    from syslogger import Syslog
else:
    from .constants import Constants
    from .models import ConfigTable, Host
    from .syslogger import Syslog


class Config(object):

    autoverify = Constants.OPTS_DEFAULTS['autoverify']
    hashtype = Constants.OPTS_DEFAULTS['hashtype']
    rsnapshot_conf = Constants.OPTS_DEFAULTS['rsnapshot-conf']
    sequence = None
    snapshot_root = Constants.SNAPSHOT_ROOT

    def init_db_get_config(self, db_session, hostname):
        """Initialize db session and read host-specific entries from
        config table

        Args:
            db_session (obj): sqlalchemy session
            hostname (str): fetch only these host-specific settings
        Returns:
            result (dict):  key/value pairs found in database
        """

        self.session = db_session
        self.hostname = hostname
        result = {}
        for record in self.session.query(ConfigTable).join(
                ConfigTable.host).filter(Host.hostname == hostname):
            if (record.keyword == 'host'):
                result[record.keyword] = record.value.split(',')
            else:
                result[record.keyword] = record.value
        return result

    def db_set(self, keyword, value):
        """Update a config setting

        Args:
            keyword: Config key
            value: New value
        """
        try:
            record = self.session.query(ConfigTable).join(
                ConfigTable.host).filter(
                    ConfigTable.keyword == keyword,
                    Host.hostname == self.hostname).one()
            record.value = value
        except sqlalchemy.orm.exc.NoResultFound:
            host = self.session.query(Host).filter(
                Host.hostname == self.hostname).one()
            record = ConfigTable(keyword=keyword, value=value,
                                 host=host)
        self.session.add(record)
        self.session.commit()

    def db_get(self, keyword):
        """Fetch a config setting

        Args:
            keyword: Config key
        """
        try:
            record = self.session.query(ConfigTable).join(
                ConfigTable.host).filter(
                    ConfigTable.keyword == keyword,
                    Host.hostname == self.hostname).one()
            return record.value
        except sqlalchemy.orm.exc.NoResultFound:
            return None

    @staticmethod
    def get_db_url(opts):
        """Get the DB url from command-line options

        Args:
            opts (dict): options dictionary
        Returns:
            result (str): URL of database
        Raises:
            RuntimeError
        """

        for item in ['dbhost', 'dbname', 'dbpass', 'dbport', 'dbtype',
                     'dbuser', 'db-url']:
            if (not opts[item]):
                opts[item] = os.environ.get(item.upper().replace('-', '_'),
                                            Constants.OPTS_DEFAULTS[item])
        if (opts['db-url']):
            return opts['db-url']
        else:
            if (opts['dbtype'] == 'sqlite'):
                return ('sqlite:///%(path)s/%(database)s' % {
                    'path': Constants.DBFILE_PATH,
                    'database': opts['dbname']
                })
            else:
                pw = opts['dbpass']
                if (not pw and os.path.isfile(Constants.DBPASS_FILE)):
                    pw = open(Constants.DBPASS_FILE, 'r').read()
                if (not pw):
                    raise RuntimeError('Database password is not set')
                return ('%(dbtype)s://%(user)s:%(password)s@'
                        '%(endpoint)s/%(database)s' % {
                            'dbtype': opts['dbtype'],
                            'user': opts['dbuser'],
                            'password': pw,
                            'endpoint': '%s:%d' % (opts['dbhost'],
                                                   int(opts['dbport'])),
                            'database': opts['dbname']
                        })

    def set_opts(self, cli_opts, db_session, hostname):
        """Read additional options from ConfigTable in database, apply
        precedence rules (there are limitations due to issue cited at
        https://github.com/docopt/docopt/issues/341).

        Args:
            cli_opts (dict): options set on CLI by docopt
            db_session (object): database session
            hostname (str): hostname key for config table lookup
        Returns:
            result (dict): options values after order of precedence
        Raises:
            ValueError
        """

        try:
            opts = self.init_db_get_config(db_session, hostname)
            self.validate_configs(opts, Constants.DBOPTS_ALLOW)
        except ValueError as ex:
            sys.exit('ERROR: DB configuration %s' % str(ex))
        except (sqlalchemy.exc.OperationalError,
                sqlalchemy.exc.ProgrammingError) as ex:
            Syslog.logger.warn('DB config message=%s' % str(ex))
            opts = {}
        for key, value in cli_opts.items():
            if (key not in opts):
                opts[key] = value
        for key, value in Constants.OPTS_DEFAULTS.items():
            if (opts[key] is None):
                opts[key] = value
        try:
            self.validate_configs(opts, cli_opts.keys())
        except ValueError as ex:
            sys.exit('ERROR: %s' % str(ex))

        if (opts['autoverify'].lower() in ['false', 'no', 'off']):
            Config.autoverify = False
        elif (opts['autoverify'].lower() in ['true', 'yes', 'on']):
            Config.autoverify = True
        Config.hashtype = opts['hashtype']
        Config.rsnapshot_conf = opts['rsnapshot-conf']
        Config.sequence = opts['sequence'].split(',')
        Config.snapshot_root = Constants.SNAPSHOT_ROOT
        return opts

    def validate_configs(self, opts, valid_choices):
        """Validate configuration settings; jsonschema would be
        tidier--but overkill.

        Args:
            opts (dict): options dictionary
            valid_choices (list): list of valid keywords
        Raises:
            ValueError if any setting's keyword or value is incorrect
        """

        for keyword, value in opts.items():
            if (keyword == 'format'):
                if (value not in ['json', 'text']):
                    raise ValueError(
                        'format=%s not json or text' % value)
            elif (keyword == 'hashtype'):
                if (value not in ['md5', 'sha256', 'sha512']):
                    raise ValueError(
                        'hashtype=%s not md5, sha256 or sha512' % value)
            elif (keyword == 'autoverify'):
                if (value not in ['false', 'no', 'off', 'true', 'yes', 'on']):
                    raise ValueError(
                        'autoverify=%s invalid boolean value' % value)

            if (keyword not in valid_choices):
                raise ValueError(
                    'keyword=%s unrecognized option setting' % keyword)

    @staticmethod
    def docopt_convert(opts):
        """Convert from dash-dash keyword to just keyword

        Args:
            opts (dict): options dictionary
        Returns:
            result (dict):  command-line options dict, with updated keys
        """

        return {key.strip('-'): value for (key, value) in opts.items()}

    def rsnapshot_cfg(self):
        """Parse the rsnapshot config file into a dictionary
        Keywords in this config file can have up to two parameters;
        for those which allow multiple statements of the same keyword,
        return a 2-level sub-dictionary or a single-level list

        Returns:
            dict:  parsed contents
        Raises:
            SyntaxError: if unexpected syntax
        """

        # Keywords that can have multiple settings in rsnapshot.conf
        self.rsnap_multiple = ['backup', 'backup_script', 'exclude',
                               'include', 'include_conf', 'interval',
                               'retain']
        filename = Config.rsnapshot_conf

        contents = {}
        try:
            fp = open(filename, 'r')
        except IOError as ex:
            Syslog.logger.warn('Cannot read rsnapshot_conf=%s, message=%s'
                               % (filename, str(ex)))
            return contents
        linenum = 1
        for line in fp:
            if '#' in line:
                line, comment = line.split('#', 1)
            tokens = line.strip().split(None, 2)
            if (len(tokens) == 0):
                continue
            elif (len(tokens) < 2):
                raise SyntaxError('file=%s at line %d\n%s' % (
                    filename, linenum, line))
            key = tokens[0]
            if (key in self.rsnap_multiple):
                if (len(tokens) == 2):
                    if (key not in contents):
                        contents[key] = []
                    contents[key].append(tokens[1])
                else:
                    if (key not in contents):
                        contents[key] = {}
                    contents[key][tokens[1]] = tokens[2]
            elif (key not in contents):
                contents[key] = ' '.join(tokens[1:])
            else:
                raise SyntaxError('file=%s (%d): duplicate keyword %s' % (
                    filename, linenum, key))
            linenum += 1
        fp.close()
        return contents
