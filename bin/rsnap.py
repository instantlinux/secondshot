#!/usr/bin/env python
"""Rsnap backup utility

create 28-jul-2018 by richb@instantlinux.net

Usage:
  rsnap.py [--action=ACTION] [--dbhost=HOST] [--dbuser=USER] [--dbpass=PASS]
           [--dbname=DB] [--dbport=PORT]
           [--backup-host=HOST] [--host=HOST] [--snapshot-root=PATH] [-v]...
  rsnap.py (-h | --help)

Options:
  --action        Action to take (archive, calc-sums, inject, rotate, start)
  --backup-host   Hostname taking the backup
  --dbhost        DB host [default: db00]
  --dbpass        DB password
  --dbname        DB name [default: rsnap]
  --dbport        DB port [default: 18306]
  --dbuser        DB user [default: rsnap]
  --host          Source host to back up
  --snapshot-root Top-level directory to hold snapshots
  -v --verbose    Verbose output
  -h --help       List options
"""

import docopt
import os.path
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session,sessionmaker

import models


class RsnapShot(object):
    def __init__(self, opts):
        self.engine = create_engine(
            'mysql+pymysql://%(user)s:%(password)s@%(endpoint)s/%(database)s'
            % {
                'user': opts.dbuser,
                'password': opts.dbpass | os.environ['DBPASS'],
                'endpoint': '%s:%d' % (opts.dbhost, int(opts.dbport)),
                'database': opts.dbname
            })
        self.session = scoped_session(sessionmaker())

    def archive(self):
        """Create backup archives"""
        raise NotImplementedError


    def calc_sums(self):
        """Calculate checksums"""
        raise NotImplementedError


    def inject(self):
        """Inject pathnames from filesystem into database"""
        raise NotImplementedError


    def start(self):
        """Set up new saveset entry in database"""
        raise NotImplementedError


    def list_archives(self):
        """List archives"""
        savesets = self.session.query(Saveset)
        for saveset in savesets:
            print saveset.saveset


def main():
    opts = docopt.docopt(__doc__)
    obj = RsnapShot(opts)

if __name__ == '__main__':
    main()
