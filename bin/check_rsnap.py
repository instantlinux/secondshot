#!/usr/bin/python2
# $Id: check_rsnap.py,v 1.3 2013/03/31 16:46:46 root Exp $
#  check_rsnap.py
#
#  Copyright 2013 Rich Braun <richb@instantlinux.net>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.

import sys
import time
import argparse
import MySQLdb

def argument_parser():
    parser = argparse.ArgumentParser(description='Check db for rsnap backups')
    parser.add_argument('-H',
        help = 'host to query (Default: all)',
        dest = 'host',
        type = str,
        default = 'all'
        )
    parser.add_argument('-w',
        help = 'WARNING if number of backups too low (Default: 1)',
        dest = 'warning',
        type = int,
        default = 1
        )
    parser.add_argument('-c',
        help = 'CRITICAL if number of backups too low (Default: 1)',
        dest = 'critical',
        type = int,
        default = 1
        )
    parser.add_argument('-f',
        help = 'WARNING if number of files too low (Default: 1000)',
        dest = 'file_warning',
        type = int,
        default = 1000
        )
    parser.add_argument('-i',
        help = 'backup interval, in hours (Default: 24)',
        dest = 'interval',
        type = int,
        default = '24'
        )
    parser.add_argument('-d',
        help = 'database host (Default: localhost)',
        dest = 'dbhost',
        type = str,
        default = 'localhost'
        )
    parser.add_argument('-P',
        help = 'database port (Default: 3306)',
        dest = 'dbport',
        type = int,
        default = '3306'
        )
    parser.add_argument('-n',
        help = 'name of database (Default: rsnap)',
        dest = 'dbname',
        type = str,
        default = 'rsnap'
        )
    parser.add_argument('-u',
        help = 'database user (Default: nagmon)',
        dest = 'dbuser',
        type = str,
        default = 'nagmon'
        )
    parser.add_argument('-p',
		    help = 'database password',
        dest = 'dbpass',
        type = str
        )
    return parser.parse_args()

def main():
    args = argument_parser()
    start_time = time.time()
    db = MySQLdb.connect(host=args.dbhost, port=args.dbport, user=args.dbuser, passwd=args.dbpass, db=args.dbname)
    cur = db.cursor()

    # Look for recent backups
    q = 'SELECT COUNT(*) FROM savesets WHERE finished > (NOW() - INTERVAL ' + str(args.interval) + ' HOUR)'
    if args.host != 'all':
        q = q + ' AND host_id=(SELECT id FROM hosts WHERE hostname="' + args.host + '" LIMIT 1)'
    cur.execute(q)
    row = cur.fetchone()
    num_backups = row[0]

    # Count files in backups
    q = 'SELECT COUNT(*) FROM backups JOIN savesets ON savesets.id=backups.saveset_id JOIN hosts on hosts.id=savesets.host_id \
         WHERE finished > (now() - INTERVAL ' + str(args.interval) + ' HOUR)'
    if args.host != 'all':
        q = q + ' AND hostname="' + args.host + '"'
    cur.execute(q)
    row = cur.fetchone()
    num_files = row[0]

    rsnap_stat = 'OK: rsnap'
    exit_value = 0
    if num_backups < args.critical:
        rsnap_stat = 'CRITICAL: rsnap'
	exit_value = 2
    elif num_backups < args.warning:
        rsnap_stat = 'WARNING: rsnap'
	exit_value = 1
    elif num_files < args.file_warning:
        rsnap_stat = 'WARNING: rsnap'
        exit_value = 1
    sys.stdout.write(rsnap_stat + " backups:" + str(num_backups) + " files:" + str(num_files) + "\n")
    sys.exit((exit_value))

if __name__ == '__main__':
    main()
    sys.stdout.write("Something really bad happened!")
    sys.exit((3))
