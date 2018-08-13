## secondshot

[![](https://images.microbadger.com/badges/version/instantlinux/secondshot.svg)](https://microbadger.com/images/instantlinux/secondshot "Version badge") [![](https://images.microbadger.com/badges/image/instantlinux/secondshot.svg)](https://microbadger.com/images/instantlinux/secondshot "Image badge") [![](https://images.microbadger.com/badges/commit/instantlinux/secondshot.svg)](https://microbadger.com/images/instantlinux/secondshot "Commit badge")

This is a command-line tool and library for managing filesystem backups on a local network. Each incremental backup is made available according to rotation rules defined in [this 2004 article](http://www.mikerubel.org/computers/rsync_snapshots/) by Mike Rubel.

Reliability and simplicity of this are inherently provided by rsnapshot and rsync, which are used without modification. What this tool adds is storage of metadata in a local SQL database, along with functions to store and verify checksums for files in each saveset.

Example crontab and configuration files can be found here under etc/ and cron/.

[![](https://images.microbadger.com/badges/license/instantlinux/secondshot.svg)](https://microbadger.com/images/instantlinux/secondshot "License badge")
