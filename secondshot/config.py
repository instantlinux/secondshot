"""config

Configuration-file parsing

created 11-aug-2018 by richb@instantlinux.net

license: lgpl-2.1
"""

import sys

if (sys.version_info.major == 2):
    from models import ConfigTable, Host
else:
    from .models import ConfigTable, Host


class ReadConfig(object):

    def rsnapshot_cfg(self, filename):
        """Parse the rsnapshot config file into a dictionary
        Keywords in this config file can have up to two parameters;
        for those which allow multiple statements of the same keyword,
        return a 2-level sub-dictionary or a single-level list

        Args:
            filename (str): name of config file
        Returns:
            dict:  parsed contents
        Raises:
            SyntaxError: if unexpected syntax
        """

        # Keywords that can have multiple settings in rsnapshot.conf
        self.rsnap_multiple = ['backup', 'backup_script', 'exclude',
                               'include', 'include_conf', 'interval',
                               'retain']
        self.rsnap_filename = filename

        contents = {}
        fp = open(filename, 'r')
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

    @staticmethod
    def docopt_convert(opts):
        """Convert from dash-dash keyword to just keyword

        Args:
            opts (dict): options dictionary
        Returns:
            result (dict):  command-line options dict, with updated keys
        """

        return {key.strip('-'): value for (key, value) in opts.items()}

    def get_config_from_db(self, db_session, hostname):
        """Read host-specific from config table

        Args:
            db_session (obj): sqlalchemy session
        Returns:
            result (dict):  key/value pairs found in database
        """

        result = {}
        for record in db_session.query(ConfigTable).join(
                ConfigTable.host).filter(Host.hostname == hostname):
            if (record.keyword == 'host'):
                result[record.keyword] = record.value.split(',')
            else:
                result[record.keyword] = record.value
        return result

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
                        'autoverify=% invalid boolean value' % value)

            if (keyword not in valid_choices):
                raise ValueError(
                    'keyword=%s unrecognized option setting' % keyword)
