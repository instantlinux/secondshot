## secondshot

[![](https://images.microbadger.com/badges/version/instantlinux/secondshot.svg)](https://microbadger.com/images/instantlinux/secondshot "Version badge") [![](https://images.microbadger.com/badges/image/instantlinux/secondshot.svg)](https://microbadger.com/images/instantlinux/secondshot "Image badge") [![](https://images.microbadger.com/badges/commit/instantlinux/secondshot.svg)](https://microbadger.com/images/instantlinux/secondshot "Commit badge")

This is a command-line tool and library for managing filesystem backups on a local network. Each incremental backup is made available according to rotation rules defined in [this 2004 article](http://www.mikerubel.org/computers/rsync_snapshots/) by Mike Rubel.

Reliability and simplicity of this are inherently provided by rsnapshot and rsync, which are used without modification. What this tool adds is storage of metadata in a local SQL database, along with functions to store and verify checksums for files in each saveset.

The underlying rsync file transfer requires root permissions on both the source and destination. To improve security, a perl script called [rrsync](https://www.samba.org/ftp/unpacked/rsync/support/rrsync) is provided; see [Guy Rutenberg's explanation](https://www.guyrutenberg.com/2014/01/14/restricting-ssh-access-to-rsync).

Example crontab and configuration files can be found here under bin/ and etc/.

This tool is distributed as both a Python package at pypi.org, and as a Docker image at dockerhub.com. Use whichever distro is convenient for you.

### Understanding Rotation

Perhaps the easiest way to visualize how savesets are rotated is to look at the top-level directory of stored savesets; here's an example from the author's system for the rotation sequence hourly / daysago / weeksago / monthsago / semiannually:
```
drwxr-xr-x 6 root care 4096 Aug 25 10:36 daysago.0
drwxr-xr-x 6 root care 4096 Aug 24 10:33 daysago.1
drwxr-xr-x 6 root care 4096 Aug 23 10:34 daysago.2
drwxr-xr-x 6 root care 4096 Aug 22 10:34 daysago.3
drwxr-xr-x 6 root care 4096 Aug 21 10:33 daysago.4
drwxr-xr-x 6 root care 4096 Aug 20 10:33 daysago.5
drwxr-xr-x 6 root care 4096 Aug 26 02:35 hourly.0
drwxr-xr-x 6 root care 4096 Aug 25 17:37 hourly.1
drwxr-xr-x 6 root care 4096 Jul  1 09:38 monthsago.0
drwxr-xr-x 6 root care 4096 Jun  4 09:36 monthsago.1
drwxr-xr-x 6 root care 4096 May 28  2018 monthsago.2
drwxr-xr-x 6 root care 4096 Apr 31  2018 monthsago.3
drwxr-xr-x 6 root care 4096 Mar  3  2018 monthsago.4
drwxr-xr-x 6 root care 4096 Feb 27  2018 monthsago.5
drwxr-xr-x 5 root care 4096 Jan 30  2018 semiannually.0
drwxr-xr-x 4 root care 4096 Aug 28  2017 semiannually.1
drwxr-xr-x 6 root care 4096 Aug 19 10:33 weeksago.0
drwxr-xr-x 6 root care 4096 Aug 12 09:49 weeksago.1
drwxr-xr-x 6 root care 4096 Aug  5 09:52 weeksago.2
drwxr-xr-x 6 root care 4096 Jul 30 09:49 weeksago.3
```
Under each of these locations are complete rsync'ed directories for each backed up host, which you can restore by any file-management tool you're familiar with. Your target volume needs to be formatted with enough storage and inodes to handle the retention schedule you define. Files that haven't changed between defined intervals are hard-linked to save space.

### Docker Image

Find the docker-compose.yml example ([here](https://raw.githubusercontent.com/instantlinux/secondshot/tree/master/docker-compose.yml):
* If you have an existing database, create a database and add settings for docker-compose; otherwise leave those out to automatically generate data with sqlite
* Define mount points for persistent data
* Generate a 4096-bit rsa key, add its id_rsa.pem to your secrets store

#### Variables

The docker image can be customized with these environment variables:

Variable | Default | Description
-------- | ------- | -----------
CRON_MINUTE | 30 | cron schedule (minutes past hour)
CRON_HOUR | 0,8,16 | cron schedule (hours)
DBHOST | db00 | db host
DBNAME | secondshot |db name
DBPORT | 3306 | db port
DBUSER | bkp | db username
DBTYPE | sqlite | db type, such as mysql+pymysql
TZ | UTC | time zone

#### Secrets
Name | Description
---- | -----------
secondshot-db-password | SQL database password
secondshot-rsync-sshkey | ssh private key for rsync

### What You Won't Find

To keep this tool simple, there are a few things that it explicitly does _not_ do:

* Restore: the target is a regular filesystem from which you can perform restores without special tools
* No at-rest encryption; if you want that, format the target using LUKS or another full-disk encryption tool
* Cloud storage like S3 or B2, which don't provide POSIX filesystem semantics
* Block-level de-duplication; you will want another tool to backup large files that require it

[![](https://images.microbadger.com/badges/license/instantlinux/secondshot.svg)](https://microbadger.com/images/instantlinux/secondshot "License badge")
