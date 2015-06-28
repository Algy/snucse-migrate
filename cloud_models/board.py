# -*- coding: utf-8 -*-

from datetime import datetime, timedelta

from sqlalchemy import Column, ForeignKey, Table, UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.sql.expression import func
from sqlalchemy.types import DateTime, Integer, Unicode

from __init__ import Base, BaseMeta, Choice, UIDMixin
from group import Group
from group import GroupMenu
from pagination import ArticleContainer


BoardAndArticle = Table(
    'BoardAndArticle', BaseMeta.metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('board_id', Integer, ForeignKey('Board.uid', ondelete='cascade'),
           nullable=False),
    Column('article_id', Integer,
           ForeignKey('Article.uid', ondelete='cascade'), nullable=False),
    UniqueConstraint('board_id', 'article_id'),
)


class Board(UIDMixin, Base, ArticleContainer):
    types = ('normal', 'album', 'forum', )
    types_str = (
        ('normal', u'일반게시판'),
        ('album', u'사진게시판'),
        ('forum', u'포럼게시판'),
    )
    name = Column(Unicode(256), nullable=False)
    board_type = Column('type', Choice(types),
                        nullable=False, default='normal')
    last_updated_at = Column(DateTime, nullable=False, default=func.now())
    admin_id = Column(Integer, ForeignKey('User.uid', ondelete='set null'),
                      nullable=True, default=None)

    _admin = relationship('User', backref='managable_boards', primaryjoin=
                          'Board.admin_id == User.uid')
    article_count = Column(Integer, nullable=False, default=0)
    articles = relationship('Article', secondary='BoardAndArticle',
                            primaryjoin='Board.uid == \
                            BoardAndArticle.c.board_id',
                            order_by='Article.uid.desc()')

    group = relationship('Group', secondary=GroupMenu.__table__,
                         primaryjoin='Board.uid == GroupMenu.board_uid',
                         uselist=False)

    @property
    def has_new_article(self):
        return datetime.now() - self.last_updated_at < timedelta(hours=24)

    @property
    def type_str(self):
        return dict(Board.types_str)[self.board_type]

    def get_group(self, session=None):
        from group import GroupMenu
        if session is None:
            session = db
        menu = session.query(GroupMenu).filter_by(board=self).first()
        if menu:
            return menu.group
        return None

    @hybrid_property
    def admin(self):
        if self._admin:
            return self._admin
        if self.group and self.group.admin:
            return self.group.admin
        return None

    @admin.setter
    def set_admin(self, value):
        self._admin = value

    def is_admin(self, user):
        return self.admin == user or self.group.admin == user

    @classmethod
    def from_group(cls, groups):
        if isinstance(groups, (list, tuple)) and not \
           any([not isinstance(e, Group) for e in groups]):
            return db.query(cls).filter(cls.group.has(
                Group.uid.in_([group.uid for group in groups])))
        elif isinstance(groups, Group):
            return groups.boards
        return []
