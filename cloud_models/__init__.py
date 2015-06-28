# -*- coding: utf-8 -*-

import json

from sqlalchemy import Column, ForeignKey, types
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.ext.mutable import Mutable
from sqlalchemy.types import TypeDecorator

__all__ = [
    'user',
    'article',
    'best_article',
    'board',
    'attachment',
    'favorite',
    'message',
    'notification',
    'panorama',
    'survey',
]


class Choice(TypeDecorator):
    u'''
    choice로 들어온 list(or tuple) 중에 하나를 선택할 수 있다.
    example:
    >>> class People(Base):
    >>>     ...
    >>>     gender = Column(ChoiceType(choice=('male', 'female')),
    >>>                     default='male')
    >>>     ...
    >>> males = db.query(People).filter_by(gender='male')

    비슷한 기능을 하려면 ENUM 타입을 쓸 수도 있지만,
    ENUM은 Table Schema에 값이 고정되기 때문에 넣을 값이 유연해야 한다면
    이 타입을 쓰는 것이 좋을 것이다.
    '''
    impl = types.Integer

    def __init__(self, choices, **kw):
        assert isinstance(choices, (tuple, list))
        self.choices = choices
        super(Choice, self).__init__(**kw)

    def process_bind_param(self, value, dialect):
        return [k for k, v in enumerate(self.choices) if v == value][0]

    def process_result_value(self, value, dialect):
        return self.choices[value]


class JSONEncodedDict(TypeDecorator):
    u'''
    Text 타입의 확장으로, Python 내부에서 dict 처럼 쓸 수 있게 하는 타입.
    실제 테이블에선 JSON으로 저장된다.
    example:
    >>> class People(Base):
    >>>     ...
    >>>     body_info = Column(JSONEncodedDict,
    >>>                        default={'tall': 180, 'weight': 70})
    >>> ...
    >>> winner1 = People(body_info={'tall': 181, 'weight': 65})
    >>> print winner1.body_info['tall']  # 181
    >>> db.add(winner1)
    >>> db.commit()

    밑에 있는 MutationDict 클래스는 JSONEncodedDict 타입을 python에서 dict처럼
    쓸 수 있게 하기 위해 정의한 것.
    '''
    impl = types.UnicodeText

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps(value).decode('utf-8')

    def process_result_value(self, value, dialect):
        if not value:
            return None
        return json.loads(value)


class MutationDict(Mutable, dict):
    @classmethod
    def coerce(cls, key, value):
        if not isinstance(value, MutationDict):
            if isinstance(value, dict):
                return MutationDict(value)

            # this call will raise ValueError
            return Mutable.coerce(key, value)
        else:
            return value

    def __setitem__(self, key, value):
        dict.__setitem__(self, key, value)
        self.changed()

    def __delitem__(self, key):
        dict.__delitem__(self, key)
        self.changed()

    def update(self, E, **F):
        dict.update(self, E, **F)
        self.changed()


MutationDict.associate_with(JSONEncodedDict)


class BaseMixin(object):
    @declared_attr
    def __tablename__(cls):
        return cls.__name__

    def __repr__(self):
        try:
            pk = self.__mapper__.primary_key[0].name
            return u'<%s %s: %s>' % (self.__class__.__name__, pk,
                                     getattr(self, pk))
        except IndexError:
            return u'<%s primarykey: unknown>' % self.__class__.__name__


BaseMeta = declarative_base(cls=BaseMixin)


class UIDMixin(object):
    u'''
    UID를 가지는 객체는 이 클래스를 상속하거나, 혹은 직접 uid를 foreign key로
    선언해 줘야 한다.
    상속 순서에 유의할 것. UIDMixin을 먼저 상속하고, 그 다음 Base를 상속해야
    한다.
    http://docs.sqlalchemy.org/en/rel_0_8/orm/extensions/declarative.html\
#mixing-in-columns

    >>> class User(UIDMinin, Base):
    >>>     name = Column(types.Unicode(50))
    >>>
    >>> user = User(name=u'user1')
    >>> db.add(user)
    >>> db.commit()
    >>> uid = user.uid  # some uid
    >>> print db.query(Base).get(uid).discriminator  # User
    '''
    @declared_attr
    def uid(cls):
        return Column(ForeignKey('Base.uid'), primary_key=True)


class PolymorphicMixin(object):
    @declared_attr
    def __mapper_args__(cls):
        ret = {'polymorphic_identity': unicode(cls.__name__)}
        if cls.__name__ == 'Base' and 'discriminator' in cls.__dict__:
            ret['polymorphic_on'] = cls.discriminator
        return ret


class Base(BaseMeta, PolymorphicMixin):
    u'''
    UID를 가지는 모든 요소의 부모 클래스.
    http://docs.sqlalchemy.org/en/rel_0_8/orm/inheritance.html
    '''

    uid = Column(types.Integer, primary_key=True)
    sid = Column(types.Unicode(255), unique=True, nullable=True)
    discriminator = Column(types.Unicode(20))
    comment_count = Column(types.Integer, nullable=False, default=0)
    recommend_count = Column(types.Integer, nullable=False, default=0)

    @property
    def recommenders(self):
        return [r.recommender for r in self.recommends]

    @property
    def best_comments(self):
        return sorted([c for c in self.comments if c.recommend_count >= 5][:3],
                      key=lambda x: x.recommend_count, reverse=True)
