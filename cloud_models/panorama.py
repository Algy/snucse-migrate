# -*- coding: utf-8 -*-

from sqlalchemy import Column, ForeignKey, event, inspect
from sqlalchemy.types import Integer, DateTime, UnicodeText
from sqlalchemy.orm import relationship
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.expression import func

from __init__ import BaseMeta, Choice


class Panorama(BaseMeta):
    id = Column(Integer, primary_key=True)
    type = Column(Choice(['article', 'comment', 'tag', 'group']),
                  nullable=False, index=True)
    event = Column(Choice(['add', 'modify', 'move', 'remove', 'survey_start',
                           'survey_end', 'article', 'group', 'user', 'file',
                           'add_rel', 'remove_rel', 'add_menu', 'remove_menu',
                           'add_board', 'remove_board', 'new']
                          ), nullable=False, index=True)
    from_group_id = Column(Integer, ForeignKey('Group.uid',
                                               ondelete='set null'),
                           nullable=True)
    from_board_id = Column(Integer, ForeignKey('Board.uid',
                                               ondelete='set null'),
                           nullable=True)
    user_id = Column(Integer, ForeignKey('User.uid', ondelete='set null', ),
                     nullable=True)
    target_id = Column(Integer, ForeignKey('Base.uid', ondelete='set null'),
                       nullable=True)
    content = Column(UnicodeText, nullable=False, default=u'')
    created_at = Column(DateTime, nullable=False, default=func.now(),
                        index=True)

    from_group = relationship('Group', primaryjoin='Panorama.from_group_id == \
                              Group.uid')
    from_board = relationship('Board', primaryjoin='Panorama.from_board_id == \
                              Board.uid')
    user = relationship('User', primaryjoin='Panorama.user_id == User.uid')
    target = relationship('Base', primaryjoin='Panorama.target_id == Base.uid')



def add_tag_event(attached_tag, session):
    target = attached_tag.target
    tagged_to = target.__class__.__name__.lower()
    content = u'{0}님이 글 [{1}]에 [{2}] 태그를 다셨습니다.'.format(
        attached_tag.creator.realname if attached_tag.creator else u'익명',
        target.title, attached_tag.name) if tagged_to == 'article' else \
        u'{0}님이 [{1}]님의 프로필에 [{2}] 태그를 다셨습니다.'.format(
            attached_tag.creator.realname, target.realname,
            attached_tag.name) if tagged_to == 'user' else u''
    session.add(Panorama(type='tag', event=tagged_to, target_id=target.uid,
                         content=content))


def add_group_event(group, session):
    pass


def add_group_menu_event(group_menu, session):
    if group_menu.menu_type in ('board', 'link', 'text'):
        type_to_str = {'board': u'게시판', 'link': u'링크', 'text': u'텍스트'}
        content = u'소모임 메뉴({0}) [{1}]이 추가되었습니다.'.format(
            type_to_str[group_menu.menu_type], group_menu.name)
        session.add(Panorama(type='group', event='add_menu',
                             from_group_id=group_menu.group.uid,
                             target_id=group_menu.board.uid if group_menu.board
                             else group_menu.group.uid,
                             content=content))


def modify_article_event(article, session):
    article_inspect = inspect(article).attrs
    if len(article_inspect.get('view_count').history[1]) <= 0 or \
       len(article_inspect.get('recommend_count').history[1]) <= 0 or \
       len(article_inspect.get('comment_count').history[1]) <= 0 or \
       article_inspect.get('tags').history[0] is None or \
       len(article_inspect.get('tags').history[0]) + \
       len(article_inspect.get('tags').history[2]) > 0:
        # 이건 조회수나 추천/댓글 수가 가 올라간 경우이므로 고려할 필요가 없다.
        # 태그가 추가됐을 때도...
        return

    board_history = article_inspect.get('boards').history
    if board_history[0] and len(board_history[0]) > 0:
        for b in board_history[0]:
            content = u'{0}님의 글 [{1}]에 게시판이 추가되었습니다.'.format(
                article.author_name, article.title)
            session.add(Panorama(type='article', event='add_board',
                                 target_id=article.uid,
                                 from_group_id=b.group.uid,
                                 from_board_id=b.uid, content=content))
    elif board_history[2] and len(board_history[2]) > 0:
        for b in board_history[2]:
            content = u'{0}님의 글 [{1}]에 게시판이 삭제되었습니다.'.format(
                article.author_name, article.title)
            session.add(Panorama(type='article', event='remove_board',
                                 target_id=article.uid,
                                 from_group_id=b.group.uid,
                                 from_board_id=b.uid, content=content))

    if not (board_history[0] and len(board_history[0]) > 0 and
            not board_history[1] and not board_history[2]):
        # 글 자체의 수정/해당 글을 게시할 게시판이 추가/삭제될 때 불린다.
        # 즉, 처음 글을 쓸 때도 이 메서드는 불린다.
        # 처음 글 쓸 때 수정 로그가 남으면 이상하니까 적당히 처리해야.
        content = u'{0}님의 글 [{1}]이(가) 수정되었습니다.'.format(
            article.author_name, article.title)
        session.add(Panorama(type='article', event='modify',
                             target_id=article.uid, content=content))


def modify_tag_event(tag, session):
    # 여기 들어오는건 태그 연결/연결 삭제밖에 없을...걸?
    linked_tag, _, unlinked_tag = inspect(tag).attrs.get('related_tags')\
        .history

    if linked_tag and len(linked_tag) > 0:
        content = u'[{0}] 태그와 [{1}] 태그가 연결되었습니다.'.format(
            tag.name, linked_tag[0].name)
        session.add(Panorama(type='tag', event='add_rel', content=content))
    elif unlinked_tag and len(unlinked_tag) > 0:
        content = u'[{0}] 태그와 [{1}] 태그 연결이 끊어졌습니다.'.format(
            tag.name, unlinked_tag[0].name)
        session.add(Panorama(type='tag', event='remove_rel', content=content))


def delete_group_event(group, session):
    pass


def delete_group_menu_event(group_menu, session):
    if group_menu.menu_type in ('board', 'link', 'text'):
        type_to_str = {'board': u'게시판', 'link': u'링크', 'text': u'텍스트'}
        content = u'소모임 메뉴({0}) [{1}]이 삭제되었습니다.'.format(
            type_to_str[group_menu.menu_type], group_menu.name)
        session.add(Panorama(type='group', event='remove_menu',
                             from_group_id=group_menu.group.uid,
                             content=content))

