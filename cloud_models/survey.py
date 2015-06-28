# -*- coding: utf-8 -*-

from datetime import datetime
import json

from sqlalchemy import Column, ForeignKey
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import backref, relationship
from sqlalchemy.sql.expression import func
from sqlalchemy.types import Boolean, DateTime, Integer, Unicode, UnicodeText

from __init__ import BaseMeta, Choice


class Survey(BaseMeta):
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Unicode(255), nullable=False, default=u'')
    due_date = Column(DateTime, nullable=False, default=None)
    parent_id = Column(Integer, ForeignKey('Article.uid', ondelete='cascade'),
                       nullable=True)
    owner_id = Column(Integer, ForeignKey('User.uid', ondelete='set null'),
                      nullable=True)
    is_anonymous = Column(Boolean, nullable=False, default=False)
    permission_type = Column(Choice(['all', 'select', 'except', 'firstcome']),
                             nullable=False, default='all')
    permission_value = Column(Unicode(100), nullable=False, default=u'')
    expose_level = Column(Integer, nullable=False, default=0)
    min_vote_num = Column(Integer, nullable=True, default=None)
    _answered_user = Column('answered_user', UnicodeText, nullable=False,
                            default=u'[]')
    created_at = Column(DateTime, nullable=False, default=func.now())

    parent = relationship('Article', backref=backref('survey', uselist=False))
    owner = relationship('User')
    questions = relationship('SurveyQuestion', order_by='SurveyQuestion.id')

    @hybrid_property
    def answered_user(self):
        return json.loads(self._answered_user)

    @answered_user.setter
    def set_answered_user(self, value):
        assert isinstance(value, (list, tuple)) and \
            all(isinstance(n, (int, long)) for n in value)
        self._answered_user = json.dumps(value)

    @property
    def parsed_permission_value(self):
        if self.permission_type in ('select', 'except'):
            return [int(year) for year in self.permission_value.split(',')]
        elif self.permission_type == 'firstcome':
            return int(self.permission_value)
        return None

    @property
    def is_finished(self):
        return datetime.now() >= self.due_date or \
            (self.permission_type == 'firstcome' and
             len(self.answered_user) >= self.parsed_permission_value)

    def votable(self, user):
        return not self.is_finished and user.uid not in self.answered_user and\
            (self.permission_type == 'all' or
             (self.permission_type == 'select' and
              user.bs_year in self.parsed_permission_value) or
             (self.permission_type == 'except' and
              user.bs_year not in self.parsed_permission_value) or
             self.permission_type == 'firstcome'
             )

    def visible(self, user):
        return self.is_finished or \
            self.expose_level == 0 or \
            self.expose_level == 1 and user.uid in self.answered_user or \
            self.expose_level == 2 and datetime.now() >= self.due_date or \
            (self.expose_level == 3 and
             len(self.answered_user) >= self.min_vote_num)

    @property
    def answers(self):
        if getattr(self, '_answers', None) is not None:
            return self._answers

        result = []
        percentage = (1. / len(self.answered_user)) * 100 \
            if len(self.answered_user) > 0 else 0

        for i, question in enumerate(self.questions):
            result.append([])
            for _ in range(len(question.examples)):
                result[i].append({
                    'users': [],
                    'percentage': 0,
                })

        answers = db.query(SurveyAnswer).filter(
            SurveyAnswer.survey_question_id.in_(
                [q.id for q in self.questions]))
        for answer in answers:
            result[answer.survey_question.order][answer.answer]['users'].\
                append(answer.user)
            result[answer.survey_question.order][answer.answer]['percentage'] \
                += percentage

        self._answers = result
        return result


class SurveyQuestion(BaseMeta):
    id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(UnicodeText, nullable=False, default=u'')
    min_answers = Column(Integer, nullable=False, default=1)
    max_answers = Column(Integer, nullable=False, default=1)
    _examples = Column('examples', UnicodeText, nullable=False, default=u'[]')
    survey_id = Column(Integer, ForeignKey('Survey.id', ondelete='cascade'),
                       nullable=False, index=True)
    order = Column(Integer, nullable=False, index=True)

    survey = relationship('Survey')
    answers = relationship('SurveyAnswer')

    @property
    def allow_one_answer(self):
        return self.min_answers == 1 and self.max_answers == 1

    @hybrid_property
    def examples(self):
        return json.loads(self._examples)

    @examples.setter
    def set_examples(self, value):
        assert isinstance(value, (list, tuple)) and \
            all(isinstance(n, basestring) for n in value)
        self._examples = json.dumps(value)


class SurveyAnswer(BaseMeta):
    id = Column(Integer, primary_key=True, autoincrement=True)
    survey_question_id = Column(Integer, ForeignKey('SurveyQuestion.id',
                                                    ondelete='cascade'),
                                nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('User.uid', ondelete='set null'),
                     nullable=True, index=True)
    answer = Column(Integer, nullable=False, default=1, index=True)

    survey_question = relationship('SurveyQuestion')
    user = relationship('User')
