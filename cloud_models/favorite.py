# -*- coding: utf-8 -*-

from sqlalchemy import Column, ForeignKey, UniqueConstraint, event
from sqlalchemy.orm import backref, relationship
from sqlalchemy.types import Integer, Unicode

from __init__ import BaseMeta
from article import Article
from attachment import File
from board import Board
from group import Group
from user import User


class Favorite(BaseMeta):
    __table_args__ = (
        UniqueConstraint('user_id', 'target_id', ),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('User.uid', ondelete='cascade'),
                     nullable=False, index=True)
    target_id = Column(Integer, ForeignKey('Base.uid', ondelete='cascade'),
                       nullable=True, index=True)
    name = Column(Unicode(255), nullable=False, default=u'')
    order = Column(Integer, nullable=False, default=0)

    user = relationship('User', primaryjoin='Favorite.user_id == User.uid',
                        backref=backref('favorites',
                                        order_by='Favorite.order'))

    target = relationship('Base', primaryjoin='Favorite.target_id == Base.uid',
                          uselist=False)


@event.listens_for(Favorite, 'before_insert')
def set_order(mapper, connection, target):
    try:
        max_value = max([f.order for f in target.user.favorites]) + 1
    except:
        max_value = 0
    target.order = max_value


@event.listens_for(Favorite, 'before_insert')
def set_default_name(mapper, connection, target):
    if isinstance(target.target, Article):
        target.name = target.target.title[:255]
    elif isinstance(target.target, User):
        target.name = target.target.realname
    elif isinstance(target.target, (Board, Group)):
        target.name = target.target.name[:255]
    elif isinstance(target.target, File):
        target.name = target.target.upload_filename
    else:
        pass  # 이 외의 경우는 나중에 생각하자.
