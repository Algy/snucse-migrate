# -*- coding: utf-8 -*-

import base64
from datetime import datetime
import hashlib
import sha3

from Crypto.Cipher import AES
from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.types import DateTime, Integer, UnicodeText, Unicode
from sqlalchemy.sql.expression import func

from __init__ import BaseMeta


# 암호화 알고리즘 출처: https://gist.github.com/sekondus/4322469
_BLOCK_SIZE = 32
_PADDING = '|'
_set_padding = lambda s: s + (_BLOCK_SIZE - len(s) % _BLOCK_SIZE) * _PADDING
_encode_AES = lambda c, s: base64.b64encode(c.encrypt(_set_padding(s)))
_decode_AES = lambda c, e: c.decrypt(base64.b64decode(e)).rstrip(_PADDING)


class MessageThread(BaseMeta):
    __table_args__ = (
        UniqueConstraint('user1_id', 'user2_id'),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    user1_id = Column(Integer, ForeignKey('User.uid', ondelete='set null'),
                      nullable=True, index=True)
    user2_id = Column(Integer, ForeignKey('User.uid', ondelete='set null'),
                      nullable=True, index=True)
    last_updated_at = Column(DateTime, nullable=False, default=func.now(),
                             index=True)
    _last_content = Column('last_content', UnicodeText, nullable=False,
                           default=u'')

    user1 = relationship('User', primaryjoin='MessageThread.user1_id == \
                         User.uid')
    user2 = relationship('User', primaryjoin='MessageThread.user2_id == \
                         User.uid')

    messages = relationship('Message', order_by='Message.sent_at.asc()')

    @hybrid_property
    def last_content(self):
        return _decode_AES(self._cipher_for_content,
                           self._last_content.encode('utf-8')).decode('utf-8')

    @last_content.setter
    def set_last_content(self, value):
        self._last_content = _encode_AES(self._cipher_for_content,
                                         value.encode('utf-8')).decode('utf-8')

    @property
    def _cipher_for_content(self):
        try:
            key = str(self.user1_id * 433024223 ^ self.user2_id * 837428374)
        except TypeError:
            key = str(self.user1.uid * 433024223 ^ self.user2.uid * 837428374)
        return AES.new(hashlib.sha3_512(key).hexdigest()[:_BLOCK_SIZE])

    @classmethod
    def get(cls, user):
        threads = db.query(cls).filter((cls.user1 == user) |
                                       (cls.user2 == user)).\
            order_by(MessageThread.last_updated_at.desc()).all()
        users = [(t.user1 if t.user1 != user else t.user2) for t in threads]

        return users, threads

    @classmethod
    def get_or_create(cls, user1, user2):
        created = False
        thread = db.query(cls).filter(
            ((cls.user1 == user1) & (cls.user2 == user2)) |
            ((cls.user1 == user2) & (cls.user2 == user1))).first()
        if not thread:
            thread = cls(user1=user1, user2=user2)
            created = True

        return thread, created


class Message(BaseMeta):
    id = Column(Integer, primary_key=True, autoincrement=True)
    sender_id = Column(Integer, ForeignKey('User.uid', ondelete='cascade'),
                       nullable=True, index=True)
    sender_username = Column(Unicode(255), nullable=False, default=u'')
    sender_realname = Column(Unicode(255), nullable=False, default=u'')
    receiver_id = Column(Integer, ForeignKey('User.uid', ondelete='cascade'),
                         nullable=True, index=True)
    receiver_username = Column(Unicode(255), nullable=False, default=u'')
    receiver_realname = Column(Unicode(255), nullable=False, default=u'')
    _content = Column('content', UnicodeText, nullable=False, default=u'')
    sent_at = Column(DateTime, nullable=False, default=func.now(), index=True)
    read_at = Column(DateTime, nullable=True, default=None)
    thread_id = Column(Integer, ForeignKey('MessageThread.id',
                                           ondelete='cascade'), nullable=False)

    sender = relationship('User', primaryjoin='Message.sender_id == User.uid',
                          backref='sent_messages')
    receiver = relationship('User', primaryjoin='Message.receiver_id == \
                            User.uid', backref='received_messages')
    thread = relationship('MessageThread')

    def __init__(self, sender, receiver, content, thread):
        self.sender = sender
        self.sender_username = sender.username
        self.sender_realname = sender.realname
        self.receiver = receiver
        self.receiver_username = receiver.username
        self.receiver_realname = receiver.realname
        self.content = content
        self.thread = thread

    @hybrid_property
    def content(self):
        return _decode_AES(self._cipher_for_content,
                           self._content.encode('utf-8')).decode('utf-8')

    @content.setter
    def set_content(self, value):
        self._content = _encode_AES(self._cipher_for_content,
                                    value.encode('utf-8')).decode('utf-8')

    @property
    def is_read(self):
        return self.read_at is not None

    @property
    def send_to_me(self):
        return self.receiver_id == self.sender_id

    @property
    def _cipher_for_content(self):
        key = (self.sender_username + self.receiver_realname).encode('utf-8')
        return AES.new(hashlib.sha3_512(key).hexdigest()[:_BLOCK_SIZE])

    def set_read(self):
        if self.read_at is None:
            self.read_at = datetime.now()
