#!/usr/bin/env python
import migfuns

from confidential import POSTGRESQL_PASSWORD
from postprocessing import fixup_ancestor_article_id, \
                           fixup_article_count_of_cafe, \
                           test_parent_article_id, \
                           fixup_user_photo_id, \
                           fixup_comment_count
from migrate import Migrater
from cloud_models import Base
from cloud_models.user import User
from cloud_models.attachment import File, Comment, Tag, RelatedTag, AttachedTag
from cloud_models.board import Board, BoardAndArticle, GroupMenu
from cloud_models.best_article import BestArticle
from cloud_models.article import Article
from cloud_models.survey import Survey, SurveyQuestion, SurveyAnswer
from cloud_models.group import Group, GroupMenu
from cloud_models.favorite import Favorite
from cloud_models.panorama import Panorama
from cloud_models.message import MessageThread, Message
from cloud_models.api import Client, Grant, Token

def move_table(migrater, gatherer, converter, tables=[]):
    for tbl in tables:
        migrater.ensure_table(tbl)
    if not dry_move:
        migrater.migrate(gatherer, converter)

def move_user(migrater):
    move_table(migrater, migfuns.user_gatherer, migfuns.user_converter, [Base, User])

def move_article(migrater):
    move_table(migrater, migfuns.article_gatherer, migfuns.article_converter, [Base, Article, BoardAndArticle])

def move_comment(migrater):
    move_table(migrater, migfuns.make_bounded_comment_gatherer(COMMENT_LOWER_BOUND), migfuns.comment_converter, [Base, Comment])

def move_board(migrater):
    move_table(migrater, migfuns.board_gatherer, migfuns.board_converter, [Base, Board, GroupMenu])

def move_best_article(migrater):
    move_table(migrater, migfuns.best_article_gatherer, migfuns.best_article_converter, [Base, BestArticle])

def move_tag(migrater):
    move_table(migrater, migfuns.tag_gatherer, migfuns.tag_converter, [Base, Tag])

def move_related_tag(migrater):
    move_table(migrater, migfuns.related_tag_gatherer, migfuns.related_tag_converter, [Base, RelatedTag])

def move_attached_tag(migrater):
    move_table(migrater, migfuns.attached_tag_gatherer, migfuns.attached_tag_converter, [Base, AttachedTag])

def move_file(migrater):
    move_table(migrater, migfuns.file_gatherer, migfuns.file_converter, [Base, File])

def move_survey(migrater):
    move_table(migrater, migfuns.survey_gatherer, migfuns.survey_converter, [Base, Survey])

def move_survey_question(migrater):
    move_table(migrater, migfuns.survey_question_gatherer, migfuns.survey_question_converter, [Base, SurveyQuestion, SurveyAnswer])

def move_favorite(migrater):
    move_table(migrater, migfuns.favorite_gatherer, migfuns.favorite_converter, [Base, Favorite])

def move_panorama(migrater):
    move_table(migrater, migfuns.panorama_gatherer, migfuns.panorama_converter, [Base, Panorama])

def move_message(migrater):
    move_table(migrater, migfuns.message_gatherer, migfuns.message_converter, [Base, Message, MessageThread])

def move_group(migrater):
    move_table(migrater, migfuns.group_gatherer, migfuns.group_converter, [Base, Group])

def move_group_menu(migrater):
    move_table(migrater, migfuns.group_menu_gatherer, migfuns.group_menu_converter, [Base, GroupMenu])


COMMENT_LOWER_BOUND = 0
dry_move = False
if __name__ == "__main__":
    migrater = Migrater('postgresql://snucse:%s@127.0.0.1:5432/snucse_test'%POSTGRE_PASSWORD)
    migrater.start()

    for tbl in [Client, Grant, Token]:
        migrater.ensure_table(tbl)

    dry_move = True

    move_user(migrater)
    move_tag(migrater)
    move_board(migrater)
    move_article(migrater)
    move_group(migrater)
    move_group_menu(migrater)
    move_related_tag(migrater)
    move_survey(migrater)
    move_survey_question(migrater)
    move_message(migrater)
    move_file(migrater)
    move_favorite(migrater)
    move_attached_tag(migrater)
    move_comment(migrater)
    # TODO: move_panorama(migrater)
    # -- 
    fixup_comment_count(migrater.db)
    fixup_user_photo_id(migrater.db, migrater.cursor)
    fixup_article_count_of_cafe(migrater.db)
    fixup_ancestor_article_id(migrater.db)
    test_parent_article_id(migrater.db)

    migrater.close()
