# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from glob import glob
import hashlib
import json
import os
import random
import re
import string

from flask import g, url_for
from sqlalchemy import Column, ForeignKey, Table, UniqueConstraint, event, \
    select
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import backref, relationship
from sqlalchemy.orm.session import Session
from sqlalchemy.types import DateTime, Integer, Unicode, UnicodeText
from sqlalchemy.sql.expression import func

from __init__ import Base, BaseMeta, Choice, JSONEncodedDict, UIDMixin
from anonymity import Anonymity
from article import Article
from user import User


class Comment(UIDMixin, Base, Anonymity):
    uid = Column(Integer, ForeignKey('Base.uid'), primary_key=True)
    author_id = Column(Integer, ForeignKey('User.uid'), nullable=True)
    anonymous = Column(JSONEncodedDict, nullable=True, default=None)
    parent_id = Column(Integer, ForeignKey('Base.uid', ondelete='cascade'),
                       nullable=False)
    parent_comment_id = Column(Integer, ForeignKey('Comment.uid'),
                               nullable=True, default=None)
    display_order = Column(Integer, nullable=False, default=0, index=True)
    reply_display_order = Column(Integer, nullable=True, default=None,
                                 index=True)
    content = Column(UnicodeText, nullable=False, default=u'')
    created_at = Column(DateTime, nullable=False, default=func.now())

    author = relationship('User', primaryjoin=(User.uid == author_id))
    parent = relationship('Base', primaryjoin=(Base.uid == parent_id),
                          backref=backref('comments', order_by=
                                          (display_order, reply_display_order),
                                          passive_deletes=True)
                          )
    parent_comment = relationship('Comment', primaryjoin=
                                  'Comment.uid == Comment.parent_comment_id',
                                  remote_side=[uid])

    @declared_attr
    def __mapper_args__(cls):
        return {
            'polymorphic_identity': unicode(cls.__name__),
            'inherit_condition': (cls.uid == Base.uid),
        }

    @property
    def author_name(self):
        return self.author.realname if self.author else self.anonymous_name

    @property
    def author_thumbnail_url(self):
        if self.author and self.author.photo:
            return url_for('main.thumbnail', uid=self.author.photo.uid,
                           width=50, height=50)
        return u'http://placehold.it/50x50'

    @property
    def deletable(self):
        return ((self.parent_comment is None and self.comment_count <= 0) or
             (self.parent_comment is not None and
              datetime.now() - self.created_at <= timedelta(hours=24)
              )
             )

class Recommend(BaseMeta):
    __table_args__ = (
        UniqueConstraint('recommender_id', 'target_id'),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    recommender_id = Column(Integer, ForeignKey('User.uid',
                                                ondelete='cascade'),
                            nullable=False)
    target_id = Column(Integer, ForeignKey('Base.uid', ondelete='cascade'),
                       nullable=False)
    created_at = Column(DateTime, nullable=False, default=func.now())

    recommender = relationship('User', primaryjoin=
                               (User.uid == recommender_id),
                               backref=backref('recommended',
                                               cascade='all, delete, \
                                               delete-orphan'))
    target = relationship('Base', backref=backref('recommends',
                                                  cascade='all, delete, \
                                                  delete-orphan'))


RelatedTag = Table(
    'RelatedTag', BaseMeta.metadata,
    Column('id', Integer, primary_key=True),
    Column('tag_1_id', Integer, ForeignKey('Tag.id'), primary_key=True,
           nullable=False),
    Column('tag_2_id', Integer, ForeignKey('Tag.id'), primary_key=True,
           nullable=False),
    Column('related_by_id', Integer, ForeignKey('User.uid')),
    Column('related_at', DateTime, default=func.now())
)


class Tag(BaseMeta):
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Unicode(255), unique=True, nullable=False, default=u'')
    creator_id = Column(Integer, ForeignKey('User.uid'), nullable=True,
                        default=None)

    creator = relationship('User')
    related_tags = relationship('Tag', secondary=RelatedTag,
                                primaryjoin=(id == RelatedTag.c.tag_1_id),
                                secondaryjoin=(id == RelatedTag.c.tag_2_id)
                                )

related_tags_union = select([
    RelatedTag.c.tag_1_id,
    RelatedTag.c.tag_2_id,
]).union(select([
    RelatedTag.c.tag_2_id,
    RelatedTag.c.tag_1_id,
])).alias()

Tag.all_related_tags = relationship(
    'Tag', secondary=related_tags_union,
    primaryjoin=(Tag.id == related_tags_union.c.tag_1_id),
    secondaryjoin=(Tag.id == related_tags_union.c.tag_2_id),
    viewonly=True
)


class AttachedTag(BaseMeta):
    __table_args__ = (
        UniqueConstraint('target_id', 'tag_id'),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    tag_id = Column(Integer, ForeignKey('Tag.id'), nullable=False)
    target_id = Column(Integer, ForeignKey('Base.uid', ondelete='cascade'),
                       nullable=False)
    creator_id = Column(Integer, ForeignKey('User.uid'), nullable=True,
                        default=None)
    created_at = Column(DateTime, nullable=False, default=func.now())
    area = Column(JSONEncodedDict, nullable=True, default=None)

    tag = relationship('Tag', backref='attached_list')
    target = relationship('Base', backref=backref(
        'tags', order_by=tag_id, cascade='all, delete, delete-orphan'))
    creator = relationship('User', primaryjoin=(creator_id == User.uid))

    @property
    def name(self):
        return self.tag.name


class Mention(BaseMeta):
    u'''
    멘션은 글 또는 댓글에서만 할 수 있다.
    [[uid]]로 할 수 있고, 당연히 uid가 달린 것들만 멘션할 수 있다.
    글 제목에서는 멘션할 수 없다.
    멘션하면 멘션 당한 유저에게 알림이 가야 한다.
    알림은 "A 유저가 B 유저를 멘션했습니다" 또는
    "A 유저가 B유저의 글/댓글 C를 멘션했습니다" 정도가 될 것이다.
    '''
    __table_args__ = (
        UniqueConstraint('mentioning_id', 'target_id'),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    mentioning_user_id = Column(Integer,
                                ForeignKey('User.uid', ondelete='cascade'),
                                nullable=True, index=True)
    mentioning_id = Column(Integer, ForeignKey('Base.uid', ondelete='cascade'),
                           nullable=False, index=True)
    target_id = Column(Integer, ForeignKey('Base.uid', ondelete='cascade'),
                       nullable=False, index=True)
    target_user_id = Column(Integer,
                            ForeignKey('User.uid', ondelete='cascade'),
                            nullable=True, index=True)
    target_type = Column(Choice(['User', 'Article', 'Comment']),
                         nullable=False, index=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    mentioning_user = relationship('User', primaryjoin='User.uid == \
                                   Mention.mentioning_user_id')
    mentioning = relationship('Base', primaryjoin='Base.uid == \
                              Mention.mentioning_id', backref=
                              backref('mentions', passive_deletes=True))
    target = relationship('Base', primaryjoin='Base.uid == Mention.target_id')
    target_user = relationship('User', primaryjoin='User.uid == \
                               Mention.target_user_id')


find_mention_regex = re.compile('(?<=\[\[)([0-9]+)(?=\]\])')



class File(UIDMixin, Base):
    uid = Column(Integer, ForeignKey('Base.uid'), primary_key=True)
    # filename은 실제로 파일이 저장된 경로를 의미하고, upload_filename은 유저가
    # 파일을 올렸을 때 해당 파일의 실제 이름을 의미한다. 이는 이름이 중복된
    # 파일일 경우 덮어쓸 가능성이 있기 때문에 실제 서버엔 파일 이름이 해시되어
    # 저장되는 것.
    filename = Column(UnicodeText, nullable=False, default=u'')
    upload_filename = Column(UnicodeText, nullable=False, default=u'')
    mime = Column(Unicode(255), nullable=False, default=u'')
    filesize = Column(Integer, nullable=False, default=0)
    parent_id = Column(Integer, ForeignKey('Base.uid', ondelete='cascade'),
                       nullable=False, index=True)
    author_id = Column(Integer, ForeignKey('User.uid', ondelete='set null'),
                       nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now())

    author = relationship('User', primaryjoin=(User.uid == author_id))
    parent = relationship('Base', primaryjoin=(Base.uid == parent_id),
                          backref=backref(
                              'files', cascade='all, delete, delete-orphan'))

    @property
    def is_image(self):
        return self.mime.startswith('image')

    @declared_attr
    def __mapper_args__(cls):
        return {
            'polymorphic_identity': unicode(cls.__name__),
            'inherit_condition': (cls.uid == Base.uid),
        }
