"""models

Database model definitions for SQLalchemy

created 28-jul-2018 by richb@instantlinux.net

license: lgpl-2.1
"""

# coding: utf-8
from sqlalchemy import BIGINT, BOOLEAN, Column, Enum, Float, ForeignKey, \
     INTEGER, Index, String, TIMESTAMP, text, VARBINARY
from sqlalchemy import func
from sqlalchemy.dialects import sqlite
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
metadata = Base.metadata
BigIntId = BIGINT().with_variant(sqlite.INTEGER(), 'sqlite')


class ConfigTable(Base):
    __tablename__ = 'config'
    __table_args__ = (
        Index('index1', 'keyword', 'host_id', unique=True),
    )

    id = Column(INTEGER, primary_key=True, unique=True,
                autoincrement=True)
    keyword = Column(String(32), nullable=False)
    value = Column(String(1023), nullable=True)
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())
    host_id = Column(ForeignKey(u'hosts.id'), nullable=False, index=True)

    host = relationship('Host')


class Host(Base):
    __tablename__ = 'hosts'

    id = Column(INTEGER, primary_key=True, unique=True,
                autoincrement=True)
    hostname = Column(String(45), nullable=False, unique=True)
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())


class File(Base):
    __tablename__ = 'files'
    __table_args__ = (
        Index('index3', 'filename', 'path', 'host_id', 'mode', 'size', 'mtime',
              'uid', 'gid', unique=True),
    )

    id = Column(BigIntId, primary_key=True, nullable=False, unique=True,
                autoincrement=True)
    path = Column(String(1023), nullable=False)
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
    shasum = Column(VARBINARY(64))
    first_backup = Column(TIMESTAMP, nullable=False, server_default=func.now())
    last_backup = Column(TIMESTAMP)
    # host_id = Column(ForeignKey(u'hosts.id'), primary_key=True,
    #                 nullable=False, index=True)
    host_id = Column(ForeignKey(u'hosts.id'), nullable=False, index=True)

    host = relationship('Host')


class Saveset(Base):
    __tablename__ = 'savesets'

    id = Column(INTEGER, primary_key=True, nullable=False, unique=True,
                autoincrement=True)
    saveset = Column(String(45), nullable=False, unique=True)
    location = Column(String(32))
    files = Column(BIGINT)
    size = Column(BIGINT)
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())
    finished = Column(TIMESTAMP, index=True)
    # host_id = Column(ForeignKey(u'hosts.id'), primary_key=True,
    #                  nullable=False, index=True)
    # backup_host_id = Column(ForeignKey(u'hosts.id'), primary_key=True,
    #                         nullable=False, index=True)
    host_id = Column(ForeignKey(u'hosts.id'), nullable=False, index=True)
    backup_host_id = Column(ForeignKey(u'hosts.id'), nullable=False,
                            index=True)

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
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())
    removable = Column(BOOLEAN, nullable=False, server_default=text("0"))
    mounted = Column(BOOLEAN, nullable=False, server_default=text("1"))
    # host_id = Column(ForeignKey(u'hosts.id'), primary_key=True,
    #                  nullable=False, index=True, server_default=text("0"))
    host_id = Column(ForeignKey(u'hosts.id'), nullable=False,
                     index=True, server_default=text("0"))

    host = relationship('Host')


class AlembicVersion(Base):
    __tablename__ = 'alembic_version'

    version_num = Column(String(32), primary_key=True, nullable=False)
