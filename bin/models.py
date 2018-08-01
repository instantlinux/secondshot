# coding: utf-8
from sqlalchemy import BIGINT, CHAR, Column, Enum, Float, ForeignKey, INTEGER, \
     Index, String, TIMESTAMP, text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.mysql.types import TINYINT
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
metadata = Base.metadata


class Host(Base):
    __tablename__ = 'hosts'

    id = Column(INTEGER, primary_key=True, unique=True,
                autoincrement=True)
    hostname = Column(String(45), nullable=False, unique=True)
    created = Column(TIMESTAMP, nullable=False,
                     server_default=text("current_timestamp()"))


class File(Base):
    __tablename__ = 'files'
    __table_args__ = (
        Index('index3', 'filename', 'path', 'host_id', 'mode', 'size', 'mtime',
              'uid', 'gid', unique=True),
    )

    id = Column(INTEGER, primary_key=True, nullable=False, unique=True,
                autoincrement=True)
    path = Column(String(255), nullable=False)
    filename = Column(String(255), nullable=False)
    owner = Column(String(48))
    grp = Column(String(48))
    uid = Column(INTEGER, nullable=False)
    gid = Column(INTEGER, nullable=False)
    mode = Column(INTEGER, nullable=False)
    size = Column(BIGINT, nullable=False)
    ctime = Column(TIMESTAMP)
    mtime = Column(TIMESTAMP)
    type = Column(Enum(u'c', u'd', u'f', u'l', u's'), nullable=False)
    links = Column(INTEGER, nullable=False, server_default=text("1"))
    sparseness = Column(Float, nullable=False, server_default=text("1"))
    sha256sum = Column(CHAR(64))
    first_backup = Column(TIMESTAMP, nullable=False,
                          server_default=text("current_timestamp()"))
    last_backup = Column(TIMESTAMP)
    host_id = Column(ForeignKey(u'hosts.id'), primary_key=True, nullable=False,
                     index=True)

    host = relationship('Host')


class Saveset(Base):
    __tablename__ = 'savesets'

    id = Column(INTEGER, primary_key=True, nullable=False, unique=True,
                autoincrement=True)
    saveset = Column(String(45), nullable=False, unique=True)
    location = Column(String(32))
    created = Column(TIMESTAMP, nullable=False,
                     server_default=text("current_timestamp()"))
    finished = Column(TIMESTAMP, index=True)
    host_id = Column(ForeignKey(u'hosts.id'), primary_key=True, nullable=False,
                     index=True)
    backup_host_id = Column(ForeignKey(u'hosts.id'), primary_key=True,
                            nullable=False, index=True)

    backup_host = relationship(
        'Host', primaryjoin='Saveset.backup_host_id == Host.id')
    host = relationship('Host', primaryjoin='Saveset.host_id == Host.id')


class Volume(Base):
    __tablename__ = 'volumes'

    id = Column(INTEGER, primary_key=True, nullable=False, unique=True,
                autoincrement=True)
    volume = Column(String(45), nullable=False, unique=True)
    path = Column(String(255), nullable=False)
    size = Column(BIGINT)
    created = Column(TIMESTAMP, nullable=False,
                     server_default=text("current_timestamp()"))
    removable = Column(TINYINT(1), nullable=False, server_default=text("0"))
    mounted = Column(TINYINT(1), nullable=False, server_default=text("1"))
    host_id = Column(ForeignKey(u'hosts.id'), primary_key=True, nullable=False,
                     index=True, server_default=text("0"))

    host = relationship('Host')


class Backup(Base):
    __tablename__ = 'backups'

    id = Column(INTEGER, primary_key=True, nullable=False, unique=True,
                autoincrement=True)
    saveset_id = Column(ForeignKey(u'savesets.id'), primary_key=True,
                        nullable=False, index=True)
    volume_id = Column(ForeignKey(u'volumes.id'), primary_key=True,
                       nullable=False, index=True)
    file_id = Column(ForeignKey(u'files.id'), primary_key=True, nullable=False,
                     index=True)

    file = relationship('File')
    saveset = relationship('Saveset')
    volume = relationship('Volume')