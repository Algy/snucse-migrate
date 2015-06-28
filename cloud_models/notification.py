# -*- coding: utf-8 -*-

import json
import re

from flask import url_for
from sqlalchemy import Column, ForeignKey, UniqueConstraint, event
from sqlalchemy.orm import joinedload, relationship
from sqlalchemy.orm.session import Session
from sqlalchemy.types import Integer, DateTime
from sqlalchemy.sql.expression import func
from sqlalchemy.inspection import inspect

from __init__ import Base, BaseMeta, Choice, JSONEncodedDict
from article import Article
from attachment import Comment
from board import Board
from favorite import Favorite
from user import User


class NotificationLog(BaseMeta):
    u'''
    유저에게 알림을 날린 로그.
    타입은 다음과 같은 것들이 있으며, 추가될 수 있다.
    comment: 내가 쓴 글이나 댓글, 그리고 내 프로필 페이지에 댓글이 달림
    tag: 내가 쓴 글이나 업로드한 사진, 또는 내 프로필 페이지에 태그가 달림
    recommend: 내가 쓴 글이나 댓글에 추천이 달림
    article: 내가 즐겨찾기 추가한 게시판이나 모임에 새 글이 올라옴
    mention: 글이나 댓글로 나, 혹은 내가 쓴 글/댓글을 언급함
    '''
    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(Choice(['comment', 'tag', 'recommend', 'article',
                          'mention', ]), nullable=False, index=True)
    sub_type = Column(Choice(['article', 'comment', 'commented_article',
                              'favorite', 'user', ]), nullable=False,
                      index=True)
    receiver_id = Column(Integer, ForeignKey('User.uid', ondelete='cascade'),
                         nullable=False)
    target_id = Column(Integer, ForeignKey('Base.uid', ondelete='cascade'),
                       nullable=False)
    '''
    senders 구성:
        list: list of dict:
            sender_id: number
            sender_realname: string
            content: string
            content_id: number. optional.
    '''
    senders = Column(JSONEncodedDict, nullable=False, default={})
    created_at = Column(DateTime, nullable=False, default=func.now())
    last_updated_at = Column(DateTime, nullable=False, default=func.now(),
                             onupdate=func.now(), index=True)

    receiver = relationship('User', primaryjoin='NotificationLog.receiver_id \
                            == User.uid', backref='noties')
    target = relationship('Base', primaryjoin='NotificationLog.target_id == \
                          Base.uid')

    @property
    def url(self):
        try:
            return url_for('main.go_uid',
                           uid=self.senders['list'][0]['content_id'])
        except KeyError:
            return url_for('main.go_uid', uid=self.target_id)

    @property
    def target_name(self):
        target = db.query(Base).get(self.target_id)
        return target.title if isinstance(target, Article) else \
            target.content if isinstance(target, Comment) else \
            target.realname if isinstance(target, User) else \
            target.group.name + ' - ' + target.name if isinstance(target, Board) else \
            target.name

    @property
    def jsonify(self):
        u'''
        알림을 redis로 바로 뿌릴 수 있는 형태의 json으로 리턴
        '''
        result = {'target_id': self.target_id,
                  'target_name': self.target_name,
                  'receiver_id': self.receiver_id,
                  'url': self.url,
                  'senders': [{'uid': s['sender_id'],
                               'realname': s['sender_realname'],
                               } for s in self.senders['list']],
                  'content': self.senders['list'][0]['content'],
                  'type': self.type,
                  'sub_type': self.sub_type,
                  }
        return json.dumps(result)



def new_comments(session, comment):
    target = comment.parent
    type = 'comment'
    result_noties = []
    applied_receivers = [comment.author.uid if comment.author else None, ]
    sender_info = {'sender_id': comment.author.uid if comment.author
                   else None,
                   'sender_realname': comment.author_name,
                   'content': comment.content,
                   'content_id': comment.uid}

    # 기존에 이미 댓글 알림이 간 적이 있는 유저들은 새 댓글 추가시 기존 알림을
    # 수정하기만 하면 된다
    pre_noties = session.query(NotificationLog).\
        filter_by(target=target, type='comment').\
        filter(NotificationLog.receiver != comment.author).all()
    for n in pre_noties:
        n.senders['list'] = [sender_info] + n.senders['list']
    session.commit()
    result_noties += pre_noties
    applied_receivers += [n.receiver.uid for n in pre_noties]

    # 댓글이 달린 글의 작성자에게 알리기
    sub_type = 'article'
    author = target.author if isinstance(target, Article) else target if \
        isinstance(target, User) else None
    if author and author.uid not in applied_receivers:
        make_comment_notification(type, sub_type, target, author, sender_info,
                                  result_noties, applied_receivers, session)

    # 댓댓글의 경우, 부모 댓글 작성자에게 알리기
    sub_type = 'comment'
    author = comment.parent_comment.author if comment.parent_comment \
        else None
    if author and author.uid not in applied_receivers:
        make_comment_notification(type, sub_type, target, author, sender_info,
                                  result_noties, applied_receivers, session)

    # 해당 글에 댓글 단 사람들에게 모두 알리기
    sub_type = 'commented_article'
    comments = session.query(Comment).filter_by(parent=target).\
        filter(~Comment.author_id.in_(applied_receivers)).all()
    for c in comments:
        if not c.author or c.author.uid in applied_receivers:
            continue
        make_comment_notification(type, sub_type, target, c.author,
                                  sender_info, result_noties,
                                  applied_receivers, session)

    return result_noties


def make_comment_notification(type, sub_type, target, receiver, sender_info,
                              result_noties, applied_receivers, session):
    noti = NotificationLog(type=type, sub_type=sub_type,
                           target_id=target.uid,
                           receiver_id=receiver.uid,
                           senders={'list': [sender_info], })
    result_noties.append(noti)
    applied_receivers.append(receiver.uid)
    session.add(noti)


def new_tags(session, attached_tag):
    target = attached_tag.target
    tag_name = attached_tag.name
    sender = attached_tag.creator
    sender_info = {'sender_id': sender.uid if sender else None,
                   'sender_realname': sender.realname if sender else None,
                   'content': tag_name}

    pre_noti = session.query(NotificationLog).\
        filter_by(type='tag', target=target).first()
    if pre_noti:
        pre_noti.senders['list'] = [sender_info] + pre_noti.senders['list']
        session.commit()
        return [pre_noti, ]
    else:
        sub_type = 'article'
        receiver = target if isinstance(target, User) else target.author
        if sender and receiver and sender.uid == receiver.uid:
            return []
        if receiver is None:
            return []
        noti = NotificationLog(type='tag', sub_type=sub_type,
                               target_id=target.uid, receiver_id=receiver.uid,
                               senders={'list': [sender_info, ]})
        session.add(noti)

    return [noti, ]


def new_recommends(session, recommend):
    target = recommend.target
    sender = recommend.recommender
    # 추천은 익명으로 할 수 없기 때문에 익명인지 따질 필요가 없다
    sender_info = {'sender_id': sender.uid, 'sender_realname': sender.realname,
                   'content': u''}

    pre_noti = session.query(NotificationLog).\
        filter_by(type='recommend', target=target).first()
    if pre_noti:
        pre_noti.senders['list'] = [sender_info] + pre_noti.senders['list']
        session.commit()
        return [pre_noti, ]
    else:
        sub_type = 'article' if isinstance(target, Article) else 'comment' if \
            isinstance(target, Comment) else None
        receiver = target if isinstance(target, User) else target.author
        if sender and receiver and sender.uid == receiver.uid:
            return []
        noti = NotificationLog(type='recommend', sub_type=sub_type,
                               target_id=target.uid, receiver_id=receiver.uid,
                               senders={'list': [sender_info, ]})
        session.add(noti)

    return [noti, ]


def new_article(session, article):
    # history는 (새로 추가된 것들, 바뀌지 않은 것들, 삭제된 것들)이 저장되어
    # 있다.
    history = inspect(article).attrs.get('boards').history
    if not history[0] or len(history[0]) <= 0:
        return []
    boards = history[0]

    board_ids = [b.uid for b in boards]
    applied_users = []
    result_noties = []
    sender_info = {'sender_id': article.author.uid if article.author else None,
                   'sender_realname': article.author.realname if
                   article.author else None,
                   'content': article.title,
                   'content_id': article.uid}
    group_ids = list(set([b.group.uid for b in boards if b.group]))

    favorites = [f for f in db.query(Favorite).options(joinedload('user')).
             filter(Favorite.target_id.in_(board_ids + group_ids)).
             order_by(Favorite.order).all()]

    for f in favorites:
        u = f.user
        if u.uid in applied_users or u.uid == article.author.uid:
            continue
        noti = NotificationLog(type='article', sub_type='favorite',
                               target_id=f.target_id, receiver_id=u.uid,
                               senders={'list': [sender_info]})
        result_noties.append(noti)
        applied_users.append(u.uid)
        session.add(noti)

    return result_noties


def new_mentions(session, obj):
    from attachment import find_mention_regex

    if not isinstance(obj, (Article, Comment)):
        return []
    mentioned_users = []
    content = obj.content
    uids = list(set(re.findall(find_mention_regex, content)))
    if len(uids) <= 0:
        return []
    sender_info = {'sender_id': obj.author.uid if obj.author else None,
                   'sender_realname': obj.author.realname if obj.author else
                   None,
                   'content': obj.content,
                   'content_id': obj.uid}

    mentions = sorted([m for m in session.query(Base).
                       filter(Base.uid.in_(uids)).all() if
                       isinstance(m, (User, Article, Comment))], key=
                      lambda x:
                      (['User', 'Article', 'Comment'].index(
                          x.__class__.__name__
                      ), x.uid))
    noties = []
    for m in mentions:
        mentioned_user = m.uid if isinstance(m, User) else m.author.uid if \
            m.author else None
        if not mentioned_user or mentioned_user in mentioned_users:
            continue
        mention_type = m.__class__.__name__.lower()
        target_id = obj.parent.uid if isinstance(obj, Comment) else obj.uid
        noti = NotificationLog(type='mention', sub_type=mention_type,
                               target_id=target_id, receiver_id=mentioned_user,
                               senders={'list': [sender_info]})

        mentioned_users.append(mentioned_user)
        noties.append(noti)
        session.add(noti)

    return noties


def delete_comment(session, comment):
    target = comment.parent

    # 댓글 알림 없애기
    noties = session.query(NotificationLog).filter_by(type='comment',
                                                      target=target).all()
    for noti in noties:
        noti.senders['list'] = [s for s in noti.senders['list']
                                if s['content_id'] != comment.uid]
        if len(noti.senders['list']) <= 0:
            session.delete(noti)

    # 멘션 알림 없애기
    delete_mentions(session, comment)


def delete_tag(session, tag):
    target = tag.target
    noties = session.query(NotificationLog).filter_by(type='tag',
                                                      target=target).all()

    for noti in noties:
        noti.senders['list'] = [s for s in noti.senders['list']
                                if s['content'] != tag.name]
        if len(noti.senders['list']) <= 0:
            session.delete(noti)
    session.commit()


def delete_recommend(session, recommend):
    target = recommend.target
    noties = session.query(NotificationLog).filter_by(type='recommend',
                                                      target=target).all()

    for noti in noties:
        noti.senders['list'] = [s for s in noti.senders['list']
                                if s['sender_id'] != recommend.recommender_id]
        if len(noti.senders['list']) <= 0:
            session.delete(noti)
    session.commit()


def delete_article(session, article):
    # 글 알림 없애기
    noties = session.query(NotificationLog).filter_by(type='article',
                                                      target=article)
    [session.delete(n) for n in noties]
    session.commit()

    # 멘션 알림 없애기
    delete_mentions(session, article)


def delete_mentions(session, obj):
    from attachment import find_mention_regex
    content = obj.content
    uids = list(set(re.findall(find_mention_regex, content)))
    mentions = sorted([m for m in session.query(Base).
                       filter(Base.uid.in_(uids)).all() if
                       isinstance(m, (User, Article, Comment))], key=
                      lambda x:
                      (['User', 'Article', 'Comment'].index(
                          x.__class__.__name__
                      ), x.uid))
    for m in mentions:
        mentioned_user = m if isinstance(m, User) else m.author if \
            m.author else None
        mention_type = m.__class__.__name__.lower()
        if not mentioned_user:
            continue

        noti = session.query(NotificationLog).\
            filter_by(type='mention', sub_type=mention_type,
                      receiver=mentioned_user, target=obj).all()
        if noti:
            session.delete(noti)
    session.commit()
