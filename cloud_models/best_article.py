# -*- coding: utf-8 -*-

import json

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.types import Integer, UnicodeText

from __init__ import BaseMeta
from article import Article


class BestArticle(BaseMeta):
    __table_args__ = (
        UniqueConstraint('year', 'month', 'week',
                         name='BestArticle_year_month_week_key'),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, index=True, nullable=False)
    month = Column(Integer, index=True, nullable=True)
    week = Column(Integer, index=True, nullable=True)
    _articles = Column('articles', UnicodeText, nullable=False, default=u'[]')

    @hybrid_property
    def articles(self):
        values = json.loads(self._articles)
        query_result = {a.uid: a for a in
                        db.query(Article).filter(
                            Article.uid.in_(v[0] for v in values))}

        return [(query_result.get(v[0], None), v[1]) for v in values]

    @articles.setter
    def set_articles(self, articles):
        # 추천수 역순으로 정렬된 글의 리스트 등이 들어온다고 가정한다.
        if not isinstance(articles, (list, tuple)):
            raise Exception
        if not all(len(x) == 2 and
                   isinstance(x[0], Article) and
                   isinstance(x[1], (int, long)) for x in articles):
            raise Exception

        self._articles = json.dumps([(x[0].uid, x[1]) for x in articles]).\
            decode('utf-8')
