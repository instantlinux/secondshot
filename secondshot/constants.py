"""constants

Constant-value definitions for secondshot

created 17-aug-2018 by richb@instantlinux.net

license: lgpl-2.1
"""


class Constants(object):
    DBPASS_FILE = '/run/secrets/secondshot-db-password'
    DBFILE_PATH = '/metadata'
    DBOPTS_ALLOW = ['autoverify', 'hashtype', 'host', 'rsnapshot-conf',
                    'volume']
    DEFAULT_VOLUME = 'backup'
    MAX_INSERT = 2000
    OPTS_DEFAULTS = {
        'autoverify': 'yes',
        'dbhost': 'db00',
        'dbname': 'secondshot',
        'dbpass': None,
        'dbport': '3306',
        'dbtype': 'sqlite',
        'dbuser': 'bkp',
        'db-url': None,
        'hashtype': 'md5',
        'rsnapshot-conf': '/etc/backup-daily.conf'}
    SNAPSHOT_ROOT = '/backups'
    SYNC_PATH = '.sync'
