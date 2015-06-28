# -*- coding: utf-8 -*-

from collections import OrderedDict
from datetime import datetime, timedelta
import hashlib
import random
import string

import sha3
from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy.types import Date, DateTime, Integer, Unicode
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.sql.expression import func

from __init__ import Base, BaseMeta, Choice, JSONEncodedDict, UIDMixin


class AccessibleGroup(BaseMeta):
    __table_args__ = (
        UniqueConstraint('user_id', 'group_id',
                         name='AccessibleGroup_user_id_group_id_key'),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('User.uid', ondelete='cascade'),
                     index=True)
    group_id = Column(Integer, ForeignKey('Group.uid', ondelete='cascade'),
                      index=True)

    user = relationship('User', primaryjoin='User.uid == \
                        AccessibleGroup.user_id')
    group = relationship('Group', primaryjoin='Group.uid == \
                         AccessibleGroup.group_id')


class User(UIDMixin, Base):
    CLASSES = OrderedDict([('bachelor', u'학사 재학'),
                           ('bechelor_degree', u'학사 졸업'),
                           ('master', u'석사 재학'),
                           ('master_degree', u'석사 졸업'),
                           ('phd', u'박사 재학'),
                           ('phd_degree', u'박사 졸업'),
                           ('major', u'복수전공'),
                           ('minor', u'부전공'),
                           ('professor', u'교수'),
                           ('staff', u'직원'),
                           ('others', u'기타'),
                           ('exchange', u'교환학생'),
                           ])
    PHONES = OrderedDict([('home', u'집'),
                          ('cell', u'휴대전화'),
                          ('office', u'사무실'),
                          ('lab', u'연구실'),
                          ('prof.room', u'교수실'),
                          ])
    username = Column(Unicode(255), unique=True)
    _password = Column('password', Unicode(512), default=u'')
    salt = Column(Unicode(256), nullable=False, default=u'')
    realname = Column(Unicode(255), nullable=False, default=u'', index=True)
    email = Column(Unicode(254), nullable=False, default=u'')
    phone = Column(Unicode(20), nullable=False, default=u'')
    birthday = Column(Date, nullable=True, default=None, index=True)
    bs_year = Column(Integer, nullable=True, default=None, index=True)
    ms_year = Column(Integer, nullable=True, default=None, index=True)
    phd_year = Column(Integer, nullable=True, default=None, index=True)
    info = Column(JSONEncodedDict, nullable=False, default={})
    classes = Column(Unicode(255), nullable=False, default=u'bachelor',
                     index=True)
    state = Column(Choice([u'pending', u'normal', u'admin']), nullable=False,
                   default=u'pending')
    photo_id = Column(Integer, ForeignKey('File.uid', ondelete='set null',
                                          use_alter=True,
                                          name='User_photo_id_fkey'),
                      nullable=True)

    photo = relationship('File', primaryjoin='User.photo_id == File.uid',
                         post_update=True)
    accessible_groups = relationship('Group',
                                     secondary=AccessibleGroup.__table__,
                                     primaryjoin='User.uid == \
                                     AccessibleGroup.user_id')

    def __init__(self, username, password, **kw):
        super(UIDMixin, self).__init__()
        super(Base, self).__init__()
        self.salt = reduce(lambda x, y: x + y,
                           [random.choice(string.printable)
                            for _ in range(256)]).decode('utf-8')
        self.username = self.sid = username
        self.password = password
        self.realname = kw['realname']
        self.email = kw['email']
        self.phone = kw['phone']
        self.birthday = kw['birthday']
        self.classes = kw['classes']
        self.state = kw['state']
        for degree in 'bs ms phd'.split(' '):
            if kw['%s_number' % degree]:
                try:
                    setattr(self, '%s_year' % degree,
                            int(kw['%s_number' % degree].split('-')[0]))
                except:
                    pass
        self.info = {}
        for info_field in ('bs_number', 'ms_number', 'phd_number', 'classes',
                           'graduate'):
            self.info[info_field] = kw[info_field]

    @hybrid_property
    def password(self):
        return self._password

    @password.setter
    def set_password(self, value):
        self._password = self._make_password(value)

    @property
    def recommended_uids(self):
        return [r.target_id for r in self.recommended]

    def _make_password(self, value):
        hash_value = self.__dict__['salt'] + value + self.__dict__['salt']
        return hashlib.sha3_512(hash_value.encode('utf-8')).hexdigest().\
            decode('utf-8')

    def correct_password(self, value):
        return self.password == self._make_password(value)

    @property
    def favorite_uids(self):
        return [b.target_id for b in self.favorites]

    @property
    def classes_str(self):
        try:
            return User.CLASSES[self.info['classes'][0]]
        except:
            return u''

    @hybrid_property
    def profile(self):
        return self.info.get('profile', u'')

    @profile.setter
    def set_profile(self, value):
        self.info['profile'] = value

    @hybrid_property
    def signature(self):
        return self.info.get('signature', u'')

    @signature.setter
    def set_signature(self, value):
        self.info['signature'] = value

    @property
    def unread_messages(self):
        return [m for m in self.received_messages if not m.is_read]


class FindPasswordKey(BaseMeta):
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('User.uid'), nullable=False)
    key = Column(Unicode(255), nullable=False, default=u'')
    created_at = Column(DateTime, nullable=False, default=func.now())

    user = relationship('User')

    @property
    def is_expired(self):
        return datetime.now() - self.created_at > timedelta(minutes=30)
