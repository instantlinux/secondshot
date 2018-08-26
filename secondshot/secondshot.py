#!/usr/bin/env python
"""Linux-based backup utility with integrity-verification

created 28-jul-2018 by richb@instantlinux.net

Usage:
  secondshot [--action=ACTION] [--dbhost=HOST] [--dbuser=USER] [--dbpass=PASS]
           [--dbname=DB] [--dbport=PORT] [--dbtype=TYPE] [--db-url=URL]
           [--backup-host=HOST] [--host=HOST]... [--logfile=FILE]
           [--list-hosts] [--list-savesets] [--list-volumes]
           [--filter=STR] [--format=FORMAT] [--hashtype=ALGORITHM]
           [--rsnapshot-conf=FILE] [--autoverify=BOOL] [--sequence=VALUES]
           [--volume=VOL] [--log-level=STR] [--version] [-v]...
  secondshot --action=start --host=HOST --volume=VOL [--autoverify=BOOL]
           [--log-level=STR] [-v]...
  secondshot --action=rotate --interval=INTERVAL [--logfile=FILE]
           [--log-level=STR] [--rsnapshot-conf=FILE] [-v]...
  secondshot --verify=SAVESET... [--format=FORMAT] [--hashtype=ALG]
           [--logfile=FILE] [--log-level=STR] [--rsnapshot-conf=FILE] [-v]...
  secondshot --action=schema-update [-v]...
  secondshot (-h | --help)

Options:
  --action=ACTION       Action to take (archive, rotate, start)
  --backup-host=HOST    Hostname taking the backup (default hostname -s)
  --dbhost=HOST         DB host (default: db00)
  --dbname=DB           DB name (default: secondshot)
  --dbport=PORT         DB port (default: 3306)
  --dbuser=USER         DB user (default: bkp)
  --dbpass=PASS         DB password (default env variable DBPASS)
  --dbtype=TYPE         DB type, e.g. mysql+pymysql (default: sqlite)
  --db-url=URL          Full URL (alternative to above DB specifiers)
  --host=HOST           Source host(s) to back up
  --interval=INTERVAL   Rotation interval: e.g. hourly, daysago
  --list-hosts          List hosts
  --list-savesets       List savesets
  --list-volumes        List volumes
  --filter=STR          Filter to limit listing [default: *]
  --format=FORMAT       Format (text or json) [default: text]
  --logfile=FILE        Logging destination [default: /var/log/secondshot]
  --log-level=STR       Syslog level debug/info/warn/none [default: info]
  --rsnapshot-conf=FILE Path of rsnapshot's config file
                        (default: /etc/backup-daily.conf)
  --sequence=VALUES     Sequence of retention intervals
                        [default: hourly,daysago,weeksago,monthsago,\
semiannually,yearsago]
  --autoverify=BOOL     Verify each just-created saveset (default: yes)
  --hashtype=ALGORITHM  Hash algorithm md5, sha256, sha512 (default: md5)
  --verify=SAVESET      Verify checksums of stored files
  --version             Display software version
  --volume=VOLUME       Volume for storing saveset
  -v --verbose          Verbose output
  -h --help             List options

license: lgpl-2.1
"""

import docopt
import json
import sys

if (sys.version_info.major == 2):
    from actions import Actions
    from config import Config
    from syslogger import Syslog
    from _version import __version__
else:
    # Python 3 requires explicit relative-path syntax
    from .actions import Actions
    from .config import Config
    from .syslogger import Syslog
    from ._version import __version__


def main():
    opts = Config().docopt_convert(docopt.docopt(__doc__))
    Syslog.logger = Syslog(opts)
    obj = Actions(opts)

    result = {}
    status = 'ok'

    if (opts['list-hosts']):
        result = obj.list_hosts()
    elif (opts['list-savesets']):
        result = obj.list_savesets()
    elif (opts['list-volumes']):
        result = obj.list_volumes()
    elif (opts['verify']):
        result = obj.verify(opts['verify'])
    elif (opts['version']):
        result = dict(version=[dict(name='secondshot %s' % __version__)])
    elif (opts['action'] == 'start'):
        result = obj.start(obj.hosts, obj.volume)
        status = result['start']['status']
    elif (opts['action'] == 'rotate'):
        result = obj.rotate(opts['interval'])
    elif (opts['action'] == 'schema-update'):
        result = obj.schema_update()
        status = result['status']
    else:
        sys.exit('Unknown action: %s' % opts['action'])

    if (opts['format'] == 'json'):
        sys.stdout.write(json.dumps(result) + '\n')
    elif (opts['format'] == 'text' and result and next(iter(result.keys())) in
          ['hosts', 'savesets', 'schema-update', 'version', 'volumes']):
        for item in result[next(iter(result.keys()))]:
            sys.stdout.write(item['name'] + '\n')
    if (status != 'ok'):
        exit(1)


if __name__ == '__main__':
    main()
