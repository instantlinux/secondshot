-- MySQL dump 10.13  Distrib 5.6.17, for Linux (x86_64)
--
-- Host: db00    Database: rsnap
-- ------------------------------------------------------
-- Server version	5.5.5-10.3.7-MariaDB-1:10.3.7+maria~stretch-log

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `backups`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `backups` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `saveset_id` int(10) unsigned NOT NULL,
  `volume_id` int(10) unsigned NOT NULL,
  `file_id` int(10) unsigned NOT NULL,
  PRIMARY KEY (`id`,`saveset_id`,`volume_id`,`file_id`),
  UNIQUE KEY `id_UNIQUE` (`id`),
  KEY `fk_backups_files` (`file_id`),
  KEY `fk_backups_savesets1` (`saveset_id`),
  KEY `fk_backups_volumes1` (`volume_id`),
  KEY `saveset_id` (`saveset_id`),
  CONSTRAINT `fk_backups_files` FOREIGN KEY (`file_id`) REFERENCES `files` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION,
  CONSTRAINT `fk_backups_savesets1` FOREIGN KEY (`saveset_id`) REFERENCES `savesets` (`id`) ON DELETE CASCADE ON UPDATE NO ACTION,
  CONSTRAINT `fk_backups_volumes1` FOREIGN KEY (`volume_id`) REFERENCES `volumes` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=1702322795 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `files`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `files` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `path` varchar(512) DEFAULT NULL,
  `filename` varchar(255) NOT NULL,
  `owner` varchar(48) DEFAULT NULL,
  `grp` varchar(48) DEFAULT NULL,
  `uid` int(10) unsigned NOT NULL,
  `gid` int(10) unsigned NOT NULL,
  `mode` int(10) unsigned NOT NULL,
  `size` bigint(19) unsigned NOT NULL,
  `ctime` timestamp NULL DEFAULT NULL,
  `mtime` timestamp NULL DEFAULT NULL,
  `type` enum('c','d','f','l','s') NOT NULL,
  `links` int(10) unsigned NOT NULL DEFAULT 1,
  `shasum` varbinary(64) DEFAULT NULL,
  `sparseness` float NOT NULL DEFAULT 1,
  `first_backup` timestamp NOT NULL DEFAULT current_timestamp(),
  `last_backup` timestamp NULL DEFAULT NULL,
  `host_id` int(10) unsigned NOT NULL,
  PRIMARY KEY (`id`,`host_id`),
  UNIQUE KEY `id_UNIQUE` (`id`),
  UNIQUE KEY `index3` (`filename`,`path`,`host_id`,`mode`,`size`,`mtime`,`uid`,`gid`),
  KEY `fk_files_hosts1` (`host_id`),
  CONSTRAINT `fk_files_hosts1` FOREIGN KEY (`host_id`) REFERENCES `hosts` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=1701159875 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `hosts`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `hosts` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `hostname` varchar(45) NOT NULL,
  `created` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `id_UNIQUE` (`id`),
  UNIQUE KEY `hostname_UNIQUE` (`hostname`)
) ENGINE=InnoDB AUTO_INCREMENT=30 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `savesets`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `savesets` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `saveset` varchar(45) NOT NULL,
  `location` varchar(32) DEFAULT NULL,
  `created` timestamp NOT NULL DEFAULT current_timestamp(),
  `finished` timestamp NULL DEFAULT NULL,
  `host_id` int(10) unsigned NOT NULL,
  `backup_host_id` int(10) unsigned NOT NULL,
  PRIMARY KEY (`id`,`host_id`,`backup_host_id`),
  UNIQUE KEY `saveset_UNIQUE` (`saveset`),
  UNIQUE KEY `id_UNIQUE` (`id`),
  KEY `fk_savesets_hosts1` (`host_id`),
  KEY `fk_savesets_hosts2` (`backup_host_id`),
  KEY `finished` (`finished`),
  CONSTRAINT `fk_savesets_hosts1` FOREIGN KEY (`host_id`) REFERENCES `hosts` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION,
  CONSTRAINT `fk_savesets_hosts2` FOREIGN KEY (`backup_host_id`) REFERENCES `hosts` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=22834 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `volumes`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `volumes` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `volume` varchar(45) NOT NULL,
  `path` varchar(255) NOT NULL,
  `size` bigint(19) unsigned DEFAULT NULL,
  `created` timestamp NOT NULL DEFAULT current_timestamp(),
  `removable` tinyint(1) NOT NULL DEFAULT 0,
  `mounted` tinyint(1) NOT NULL DEFAULT 1,
  `host_id` int(10) unsigned NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`,`host_id`),
  UNIQUE KEY `id_UNIQUE` (`id`),
  UNIQUE KEY `volume_UNIQUE` (`volume`),
  KEY `fk_volumes_hosts1` (`host_id`),
  CONSTRAINT `fk_volumes_hosts1` FOREIGN KEY (`host_id`) REFERENCES `hosts` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=43 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2018-08-09 14:32:16
