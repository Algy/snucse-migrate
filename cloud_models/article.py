# -*- coding: utf-8 -*-

from collections import OrderedDict
from datetime import datetime, timedelta
import re
from xml.sax.saxutils import escape

from flask import url_for
from sqlalchemy import Column, ForeignKey, event
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import relationship
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.expression import func
from sqlalchemy.types import Boolean, DateTime, Integer, UnicodeText

from __init__ import Base, Choice, UIDMixin, JSONEncodedDict
from anonymity import Anonymity
from user import User


_find_file_re = re.compile('(\[\?)(.+?)(\?\])')


class Article(UIDMixin, Base, Anonymity):
    RENDER_TYPES = ('html<br />', 'html', 'text')

    uid = Column(Integer, ForeignKey('Base.uid'), primary_key=True)
    is_notice = Column(Boolean, nullable=False, default=False, index=True)
    title = Column(UnicodeText, nullable=False, default=u'')
    _content = Column('content', UnicodeText, nullable=False, default=u'')
    render_type = Column(Choice(RENDER_TYPES), nullable=False,
                         default='html<br />')
    author_id = Column(Integer, ForeignKey('User.uid'), nullable=True,
                       default=None)
    anonymous = Column(JSONEncodedDict, nullable=True, default=None)
    view_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=func.now())
    parent_article_id = Column(Integer, ForeignKey('Article.uid',
                                                   ondelete='set null'),
                               nullable=True, index=True)
    ancestor_article_id = Column(Integer, ForeignKey('Article.uid',
                                                     ondelete='set null'),
                                 nullable=True, index=True)

    author = relationship('User', primaryjoin=(author_id == User.uid),
                          backref='articles')

    boards = relationship('Board', secondary='BoardAndArticle',
                          primaryjoin=
                          'Article.uid == BoardAndArticle.c.article_id')
    parent_article = relationship('Article', primaryjoin='Article.\
                                  parent_article_id == Article.uid',
                                  remote_side=[uid],
                                  backref='child_articles',
                                  post_update=True)
    ancestor_article = relationship('Article', primaryjoin='Article.\
                                    ancestor_article_id == Article.uid',
                                    remote_side=[uid],
                                    backref='descendant_articles',
                                    post_update=True)

    @hybrid_property
    def content(self):
        if self.render_type == 'html<br />':
            return self._content.replace('\n', '<br />\n')
        elif self.render_type == 'html':
            return self._content
        elif self.render_type == 'text':
            return escape(self._content).replace('\n', '<br />\n')

    @content.setter
    def set_content(self, value):
        self._content = value

    @property
    def author_uid(self):
        return self.author.uid if self.author else None

    @property
    def author_name(self):
        return self.author.realname if self.author else \
            self.anonymous_name

    @property
    def is_new(self):
        return datetime.now() - self.created_at <= timedelta(hours=24)

    @property
    def content_for_read(self):
        # 글 읽기 페이지에선 멘션을 변환하고, 첨부파일 링크해 놓은 걸 변환해야
        # 하는 등 여러 작업이 필요하다. 그 작업을 여기서 처리한다.

        # TODO: 멘션 변환은 지금 글과 댓글에서 모두 쓰고 있고, jinja 필터로
        # 들어있다. 변환하는 함수를 따로 만들고, 필터에선 그 함수를 부르는
        # 식으로 변경해야 할 듯.
        file_list = {f.upload_filename: f.uid for f in self.files}

        def replace_filename_func(match):
            filename = match.group(2)
            if filename not in file_list:
                return match.group()
            return url_for('main.go_uid', uid=file_list[filename])

        content = _find_file_re.sub(replace_filename_func, self.content)

        return content

    @property
    def in_album_board(self):
        return any([b.board_type == 'album' for b in self.boards])

    @property
    def image_files(self):
        return [f for f in self.files if f.mime.startswith('image')]

    def thumbnail_image(self, scale=None, width=0, height=0):
        images = [f for f in self.files if f.mime.startswith('image')]
        if len(images) > 0:
            if scale is not None:
                return url_for('main.thumbnail', uid=images[0].uid,
                               scale=scale)
            else:
                return url_for('main.thumbnail', uid=images[0].uid,
                               width=width, height=height)
        return None
