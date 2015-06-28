import sqlalchemy

from sqlalchemy.sql.expression import func

from urllib import urlopen

from migfuns import cursor_generator
from mimetype import guess_mimetype
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


def window_iter_on_uid(db, objclass, window_size, crits=()):
    offset = 0
    while True:
        print "OFFSET", offset
        q = db.query(objclass).filter(*((objclass.uid >= offset,) + crits))
        pres = q.limit(window_size).all()
        if len(pres) == 0:
            break
        _max = 0
        for item in pres:
            if item.uid > _max:
                _max = item.uid
            yield item
        offset = _max + 1


def fixup_user_photo_id(db, cursor):
    cursor.execute('''
        SELECT uid, photo_uid FROM "user"
        WHERE photo_uid IS NOT NULL
    ''')
    for wing in cursor_generator(cursor):
        userobj = db.query(User).filter_by(uid = wing["uid"]).first()
        if userobj is not None:
            userobj.photo_id = wing["photo_uid"]
            db.commit()


def test_parent_article_id(db):
    for idx, article in enumerate(window_iter_on_uid(db, Article, 10000)):
        if idx % 1000 == 0:
            print "testing %d-th article..."%idx
        if article.parent_article_id is None:
            continue
        t = db.query(Article)\
              .filter_by(uid = article.parent_article_id)\
              .first()
        if t is None:
            if article.parent_article_id == 0:
                print "Warning! relate has 0 value to represent no parent, instead of NULL value: #%d" % article.uid
            else:
                raise Exception("Failed for article #%d" % article.uid)


def fixup_ancestor_article_id(db):
    visited = set()

    ancestor_cache = {}
    def _iter(p, modified_articles):
        parent_id = p.parent_article_id 
        if p.uid in visited:
            if p.uid in ancestor_cache:
                return ancestor_cache[p.uid]
            else:
                return p.ancestor_article_id
        elif parent_id is None or parent_id == 0 or parent_id == p.uid:
            visited.add(p.uid)
            modified_articles.append(p)
            p.ancestor_article_id = p.uid
            ancestor_cache[p.uid] = p.uid
            return p.uid
        else:
            visited.add(p.uid)
            parent = db.query(Article)\
                       .filter_by(uid = parent_id)\
                       .one()
            ancestor_id = _iter(parent, modified_articles)
            p.ancestor_article_id = ancestor_id
            modified_articles.append(p)
            ancestor_cache[p.uid] = ancestor_id
            assert ancestor_id
            return ancestor_id
    print "START FIXUP"

    modified_articles = []
    for idx, article in enumerate(window_iter_on_uid(db, Article, 10000)):
        if idx % 1000 == 0:
            print "fixing %d-th article..."%idx
        _iter(article, modified_articles)

        # flush result
        if idx % 10000 == 0:
            print "FLUSHING"
            db.commit()
            modified_articles = []
            ancestor_cache.clear()
    db.commit()

def fixup_comment_count(db):
    # TODO: to be tested
    modified_comments = []

    for comment in enumerate(window_iter_on_uid(db, Comment, 10000, crits=(Comment.comment_count > 0, ))):
        if idx % 1000 == 0:
            print "fixing count of comment attached to %d-th comment..."%idx
        comment.comment_count = 0
        modified_comments.add(comment)

        if len(modified_comments) >= 10000:
            db.commit()
            modified_comments = []
    db.commit()
    print "CLEARED comment count"

    modified_comments = []
    for idx, comment in enumerate(window_iter_on_uid(db, Comment, 10000, crits=(Comment.parent_comment_id != None, ))):
        if idx % 1000 == 0:
            print "fixing count of comment attached to %d-th comment..."%idx
        db.query(Base).filter_by(uid=comment.parent_comment_id).update({"comment_count": Base.comment_count + 1})
    db.commit()


def gather_psy_test(migrater):
# TODO
    pass

def fixup_article_count_of_cafe(db):
    for idx, group in enumerate(window_iter_on_uid(db, Group, 10000)):
        if idx % 1000 == 0:
            print "fixing count of article of %d-th group..."%idx
        result = db.query(Group.uid, func.sum(Board.article_count).label("count"))\
                   .filter(Group.uid == group.uid)\
                   .join(GroupMenu, Group.uid == GroupMenu.group_id)\
                   .join(Board, GroupMenu.board_uid == Board.uid)\
                   .group_by(Group.uid)\
                   .first()

        if result is None:
            count = 0
        else:
            count = result[1]
        group.article_count = count
        db.commit()


def move_files(file_id_lower_bound=0):
    # TODO
    pass
