# -*- coding: utf-8 -*-

import hashlib

import sha3
from sqlalchemy import Column, ForeignKey, UniqueConstraint, event
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql.expression import func
from sqlalchemy.types import Boolean, DateTime, Integer, Unicode, UnicodeText

from __init__ import Base, BaseMeta, Choice, UIDMixin
from pagination import ArticleContainer


class Group(UIDMixin, Base, ArticleContainer):
    name = Column(Unicode(255), nullable=False, default=u'', unique=True)
    admin_id = Column(Integer, ForeignKey('User.uid', ondelete='set null'),
                      nullable=True)
    main_page = Column(UnicodeText, nullable=True, default=None)
    last_updated_at = Column(DateTime, nullable=False, default=func.now(),
                             index=True)
    article_count = Column(Integer, nullable=False, default=0)
    is_public = Column(Boolean, nullable=False, default=False)
    _public_password = Column('public_password', Unicode(255), nullable=True,
                              default=None)

    admin = relationship('User', primaryjoin='Group.admin_id == User.uid',
                         backref='managable_groups')

    @property
    def boards(self):
        return list(set([m.board for m in self.menus]))

    @hybrid_property
    def public_password(self):
        return self._public_password

    @public_password.setter
    def set_public_password(self, value):
        self._public_password = self._make_password(value)

    def correct_password(self, value):
        return self.public_password == self._make_password(value)

    def _make_password(self, value):
        try:
            value = value.encode('utf-8')
        except:
            pass

        return hashlib.sha3_512(value).hexdigest().decode('utf-8')

    @property
    def anonymous_user(self):
        if self.is_public:
            return {
                'uid': self.uid,
                'username': self.sid,
                'state': 'group',
                'realname': self.name,
            }
        return None


class GroupMenu(BaseMeta):
    GROUP_MENU_TYPES = (u'board', u'link', u'text', u'indent', u'outdent', )
    __table_args__ = (
        UniqueConstraint('group_id', 'position'),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey('Group.uid', ondelete='cascade'),
                      nullable=True)
    menu_type = Column(Choice(GROUP_MENU_TYPES), nullable=False)
    board_uid = Column(Integer, ForeignKey('Board.uid', ondelete='cascade'),
                       nullable=True)
    url = Column(UnicodeText, nullable=False, default=u'')
    name = Column(Unicode(256), nullable=False, default=u'')
    position = Column(Integer, nullable=False, default=0, index=True)

    group = relationship('Group', backref=backref(
        'menus', order_by='GroupMenu.position'))
    board = relationship('Board')


@event.listens_for(GroupMenu, 'before_insert')
def set_position(mapper, connection, target):
    if not target.position:
        try:
            max_position = db.query(GroupMenu).filter_by(group=target.group).\
                order_by(GroupMenu.position.desc()).first()
            max_position = max_position.position
        except:
            max_position = 0

        target.position = max_position + 1
