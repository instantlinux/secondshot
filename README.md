## secondshot

[![](https://images.microbadger.com/badges/version/instantlinux/secondshot.svg)](https://microbadger.com/images/instantlinux/secondshot "Version badge") [![](https://images.microbadger.com/badges/image/instantlinux/secondshot.svg)](https://microbadger.com/images/instantlinux/secondshot "Image badge") [![](https://images.microbadger.com/badges/commit/instantlinux/secondshot.svg)](https://microbadger.com/images/instantlinux/secondshot "Commit badge")

This is a command-line tool and library for managing filesystem backups on a local network. Each incremental backup is made available according to rotation rules defined in [this 2004 article](http://www.mikerubel.org/computers/rsync_snapshots/) by Mike Rubel.

Reliability and simplicity of this are inherently provided by rsnapshot and rsync, which are used without modification. What this tool adds is storage of metadata in a local SQL database, along with functions to store and verify checksums for files in each saveset.

The underlying rsync file transfer requires root permissions on both the source and destination. To improve security, a perl script called [rrsync](https://www.samba.org/ftp/unpacked/rsync/support/rrsync) is provided; see [Guy Rutenberg's explanation](https://www.guyrutenberg.com/2014/01/14/restricting-ssh-access-to-rsync).

Example crontab and configuration files can be found here under etc/ and cron/.

This tool is distributed as both a Python package at pypi.org, and as a Docker image at dockerhub.com. Use whichever distro is convenient for you.

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

[![](https://images.microbadger.com/badges/license/instantlinux/secondshot.svg)](https://microbadger.com/images/instantlinux/secondshot "License badge")
