# -*- coding: utf-8 -*-

from collections import OrderedDict

from sqlalchemy import Column, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.types import Boolean, DateTime, Integer, Unicode, UnicodeText

from __init__ import Base, BaseMeta, UIDMixin


SCOPES = OrderedDict([
    ('basic_info', u'기본 정보'),
    ('advanced_info', u'상세 정보'),
    ('boards', u'게시판 목록'),
    ('articles', u'글 목록'),
    ('read', u'글 가져오기'),
    ('write_comment', u'댓글 쓰기'),
    ('write', u'글쓰기'),
])


class Client(UIDMixin, Base):
    name = Column(Unicode(255))
    description = Column(UnicodeText)
    creator_id = Column(Integer, ForeignKey('User.uid', ondelete='cascade'))
    is_confidential = Column(Boolean, default=False)
    client_secret = Column(Unicode(55), unique=True, index=True,
                           nullable=False)
    homepage = Column(Unicode(255), default=u'')
    photo_id = Column(Integer, ForeignKey('File.uid'), nullable=True)
    _redirect_uris = Column(UnicodeText)
    _default_scopes = Column(UnicodeText)

    creator = relationship('User', primaryjoin='Client.creator_id == User.uid')
    photo = relationship('File', primaryjoin='Client.photo_id == File.uid')

    @property
    def client_id(self):
        return unicode(self.uid)

    @property
    def client_type(self):
        if self.is_confidential:
            return 'confidential'
        return 'public'

    @property
    def redirect_uris(self):
        if self._redirect_uris:
            return self._redirect_uris.split()
        return []

    @property
    def default_redirect_uri(self):
        return self.redirect_uris[0]

    @property
    def default_scopes(self):
        if self._default_scopes:
            return self._default_scopes.split()
        return []


class Grant(BaseMeta):
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('User.uid', ondelete='cascade'))
    client_id = Column(Integer, ForeignKey('Client.uid'),
                       nullable=False)
    code = Column(Unicode(255), index=True, nullable=False)
    redirect_uri = Column(Unicode(255))
    expires = Column(DateTime)
    _scopes = Column(UnicodeText)

    user = relationship('User')
    client = relationship('Client')

    def delete(self):
        db.delete(self)
        db.commit()
        return self

    @property
    def scopes(self):
        if self._scopes:
            return self._scopes.split()
        return []


class Token(BaseMeta):
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('Client.uid'),
                       nullable=False)
    user_id = Column(Integer, ForeignKey('User.uid'))
    token_type = Column(Unicode(40))  # currently only bearer is supported
    access_token = Column(Unicode(255), unique=True)
    refresh_token = Column(Unicode(255), unique=True)
    expires = Column(DateTime)
    _scopes = Column(UnicodeText)

    client = relationship('Client')
    user = relationship('User')

    def delete(self):
        db.delete(self)
        db.commit()
        return self

    @property
    def scopes(self):
        if self._scopes:
            return self._scopes.split()
        return []
