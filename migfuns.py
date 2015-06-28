# -*- coding: utf-8 -*-
import json
import cloud_models.panorama as panorama

from mimetype import guess_mimetype
from failback import get_end_of_uid, filter_user_uid, is_invalid_favorite_target_uid, is_orphaned_file_uid
from time import sleep
from pprint import pprint
from datetime import datetime, timedelta
from itertools import chain
from migrate import BaseCustomSaver
from sqlalchemy import func, or_, and_
from cloud_models import Base
from cloud_models.user import User
from cloud_models.attachment import File, Comment, Tag, RelatedTag, AttachedTag
from cloud_models.board import Board, BoardAndArticle
from cloud_models.best_article import BestArticle
from cloud_models.article import Article
from cloud_models.survey import Survey, SurveyQuestion, SurveyAnswer 
from cloud_models.group import Group, GroupMenu
from cloud_models.favorite import Favorite
from cloud_models.panorama import Panorama
from cloud_models.message import MessageThread, Message

def get_comment_uid(comment_id) :
    return comment_id + get_end_of_uid()

def cursor_generator(cursor):
    row = cursor.fetchone()
    while row:
        yield row
        row = cursor.fetchone()

def make_single_gatherer(table, appendix=''):
    def gatherer(cursor, cursor2):
        cursor.execute('''SELECT "{0}".* FROM "{0}" {1}'''.format(table, appendix))
        return cursor_generator(cursor)
    return gatherer


# User
def user_gatherer(cursor, cursor2):
    cursor.execute('''
        SELECT "user".*
        FROM "user" 
    ''')
    for idx, record in enumerate(cursor_generator(cursor)):
        if idx % 1000 == 0:
            print "NOW MOVE %d-th record..."%idx
        user_uid = record["uid"]
        cursor2.execute('''SELECT * FROM user_phone_number WHERE user_uid='%s' '''%user_uid)
        phones = [x['phone_number'] for x in cursor2.fetchall()]
        cursor2.execute('''SELECT email FROM user_email WHERE user_uid='%s' '''%user_uid)
        emails = [d["email"] for d in cursor2.fetchall()]
        cursor2.execute('''SELECT class FROM user_class WHERE user_uid='%s' '''%user_uid)
        classes = [d["class"] for d in cursor2.fetchall()]

        profile_content = None
        if record["article_uid"] is not None:
            cursor2.execute('''
                SELECT content FROM article WHERE uid = %d
            '''%record["article_uid"])
            prf = cursor2.fetchone()
            if prf is not None and prf["content"] is not None:
                profile_content = prf["content"]

        yield (record, phones, emails, classes, profile_content)


def user_converter(_iter):
    for (wing, phones, emails, classes, profile_content) in _iter:
        try:
            phone = phones[0][:20]
        except IndexError:
            phone = ""

        user = User(wing["account"], 
                    "There's no darkside of the moon indeed.",
                    realname=wing["name"],
                    email=json.dumps(emails),
                    phone=phone,
                    birthday=wing["birthday"],
                    bs_number=wing["bs_number"],
                    ms_number=wing["ms_number"],
                    phd_number=wing["phd_number"],
                    classes=classes[0] if classes else u"",
                    photo_id=None,
                    state="normal",
                    graduate=None)
        user.uid=wing["uid"]
        # user._password = wing["password"]
        user.password = "1234" # for debugging
        if wing["signature"]:
            user.signature = wing["signature"]
        if profile_content:
            user.profile = profile_content
        yield user


# article
def article_gatherer(cursor, cursor2):
    cursor.execute('''SELECT * FROM article''')
    for wing in cursor_generator(cursor):
        wing["user_uid"] = filter_user_uid(wing["user_uid"])
        yield wing

class BoardAndArticleSaver(BaseCustomSaver):
    def __init__(self, board_id, article_id):
        self.board_id = board_id
        self.article_id = article_id

    def save(self, db):
        ins = BoardAndArticle.insert().values(board_id=self.board_id, 
                                              article_id=self.article_id)
        db.execute(ins)

_saved_article_uid = {}
_saved_comment_uid = {}
class ArticleSaver(BaseCustomSaver):
    def __init__(self, article_obj):
        self.article_obj = article_obj

    def save(self, db):
        uid = self.article_obj.uid
        parent_article_id = self.article_obj.parent_article_id

        while (parent_article_id is not None and 
               parent_article_id not in _saved_article_uid):
            sleep(0)
        db.add(self.article_obj)
        db.commit()
        _saved_article_uid[uid] = uid

class CommentSaver(BaseCustomSaver):
    def __init__(self, comment_obj):
        self.comment_obj = comment_obj

    def save(self, db):
        uid = self.comment_obj.uid
        parent_comment_id = self.comment_obj.parent_comment_id

        while (parent_comment_id is not None and 
               parent_comment_id not in _saved_comment_uid):
            sleep(0)
        db.add(self.comment_obj)
        db.commit()
        _saved_comment_uid[uid] = uid


def article_converter(_iter):
    for idx, wing in enumerate(_iter):
        if idx % 1000 == 0:
            print "NOW MOVING %d-th record of article table..."%idx

        if wing["relate"] is None or wing["relate"] <= 0 or wing["relate"] == wing["uid"]:
            parent_article_id = None
        else:
            parent_article_id = wing["relate"]

    
        if wing["render_type"] == "htmlbr":
            render_type = 'html<br />'
        else:
            render_type = wing["render_type"]

        # FIXME: In schedule board, created_at is set to the time at which schedule of article is done.
        article = Article(recommend_count=wing["recommendation_count"],
                          comment_count=wing["comment_count"],
                          is_notice=wing["is_notice"],
                          title=wing["subject"],
                          content=wing["content"],
                          author_id=wing["user_uid"],
                          anonymous=None,
                          view_count=wing["hit"],
                          created_at=wing["time"],
                          render_type=render_type,
                          parent_article_id=parent_article_id,
                          ancestor_article_id=None)

        '''
            user_account is NULL and user_uid is NULL
                Obviously, anonymous article
            
            user_account is NULL and user_uid is not NULL
                Legacy 

            user_account is not NULL and user_uid is NULL
                Legacy. Be converted as if it were anonymous.

            user_account is not NULL and user_uid is not NULL
                named article
        '''
        if wing["user_uid"] is None:
            article.anonymous_name = wing["user_name"] or ""
            article.anonymous["password"] = _hexdigest(wing["user_password"])
        article.uid = wing["uid"]

        bna = BoardAndArticleSaver(board_id=wing["board_uid"],
                                   article_id=wing["uid"])
        yield ArticleSaver(article), bna

# comment

def make_bounded_comment_gatherer(lower=0):
    def _fun(cursor, cursor2):
        cursor.execute('''
            SELECT "comment".* FROM "comment"
            JOIN uid_list
            ON uid_list.uid = "comment".parent_uid
            WHERE uid_list.type != 'dolblog' AND
                  uid_list.type != 'app' AND
                  id >= %d
            ORDER BY id ASC
        '''%lower)
        return cursor_generator(cursor)
    return _fun



def _hexdigest(s):
    if s is None:
        return None
    res = ""
    for c in s:
        low = ord(c) % 16
        high = ord(c) / 16
        if low >= 10:
            low = chr(low - 10 + ord('a'))
        else:
            low = chr(low + ord('0'))
        if high >= 10:
            high = chr(high - 10 + ord('a'))
        else:
            high = chr(high + ord('0'))
        res += high + low
    return res




def comment_converter(_iter):
    for idx, wing in enumerate(_iter):
        if idx % 1000 == 0:
            print "NOW MOVING %d-th record of comment table..."%(wing["id"] - 1)
        if wing["relate"] is None or wing["relate"] == wing["id"]:
            parent_comment_id = None
        else:
            parent_comment_id = get_comment_uid(wing["relate"])
        comment = Comment(recommend_count=wing["recommendation_count"],
                          author_id=filter_user_uid(wing["user_uid"]),
                          anonymous=None,
                          parent_id=wing["parent_uid"],
                          parent_comment_id=parent_comment_id,
                          display_order=wing["position"],
                          reply_display_order=wing["depth_position"],
                          content=wing["content"],
                          created_at=wing["time"])
        if filter_user_uid(wing["user_uid"]) is None:
            comment.anonymous_name = wing["user_name"] or None
            # password may be NULL
            comment.anonymous["password"] = _hexdigest(wing["user_password"])
        comment.uid = get_comment_uid(wing["id"])
        yield comment

tag_gatherer = make_single_gatherer("tag")
def tag_converter(_iter):
    for idx, wing in enumerate(_iter):
        if idx % 1000 == 0:
            print "NOW MOVING %d-th record of tag table..."%idx
    
        creator_id = filter_user_uid(wing["user_uid"])
        if creator_id < 0 or creator_id == 3027: # SUPER HACK!
            creator_id = None

        tag = Tag(name=wing["name"],
                  creator_id=creator_id)
        tag.id = wing["id"]

        yield tag


def attached_tag_gatherer(cursor, cursor2):
    cursor.execute('''
        SELECT tag_parent_relation.* FROM tag_parent_relation
        JOIN uid_list
        ON tag_parent_relation.parent_uid = uid_list.uid
        WHERE uid_list.type != 'dolblog'
    ''')
    return cursor_generator(cursor)



def attached_tag_converter(_iter):
    for idx, wing in enumerate(_iter):
        if idx % 1000 == 0:
            print "NOW MOVING %d-th record of attached-tag table..."%idx

        area = None if wing["extra"] is None else json.loads(wing["extra"])

        if is_orphaned_file_uid(wing["parent_uid"]):
            print wing["parent_uid"], "is orphaned"
            continue

        attached_tag = AttachedTag(tag_id=wing["tag_id"],
                                   target_id=wing["parent_uid"],
                                   creator_id=filter_user_uid(wing["user_uid"]),
                                   created_at=wing["time"],
                                   area=area)
        yield attached_tag


related_tag_gatherer = make_single_gatherer("tag_relation")
def related_tag_converter(_iter):
    for idx, wing in enumerate(_iter):
        if idx % 1000 == 0:
            print "NOW MOVING %d-th record of related-tag table..."%idx


        class RelatedTagSaver(BaseCustomSaver):
            def save(self, db):
                max_id = db.query(func.max(RelatedTag.columns.get('id'))).scalar()
                if max_id is None:
                    max_id = 0
                max_id += 1
                ins = RelatedTag.insert().values(id=max_id,
                                                 tag_1_id=wing["parent_id"], 
                                                 tag_2_id=wing["id"],
                                                 related_by_id=filter_user_uid(wing["user_uid"]),
                                                 related_at=wing["time"])
                db.execute(ins)
                db.commit()

        yield RelatedTagSaver()


board_gatherer = make_single_gatherer("board")
def board_converter(_iter):
    for idx, wing in enumerate(_iter):
        if idx % 1000 == 0:
            print "NOW MOVING %d-th record of board table..."%idx

        # cloud TODO: 
        #  possible board type
        #     "andromeda", "normal", "forum", "image", 
        #     "profile",  "anonym", "calendar"
        # FIXING:
        #   "andromeda" => normal
        #   profile -> 각 유저에한테 매핑해서 쿵짝쿵짝(모든 User.article_uid가 들어있는 게시판이 바로 이것!), 일단은 normal로 보존해놓음.
        #   anonymous -> normal
        #   calendar -> cloud TODO

        wing_board_type = wing["type"]
        if wing_board_type in ("normal", "forum", ):
            board_type = wing_board_type
        elif wing_board_type == "image":
            board_type = "album"
        elif wing_board_type in ("andromeda", "anonymous", ):
            board_type = "normal"
        elif wing_board_type == "profile":
            print "NOTE: profile board is not required anymore."
            board_type = "normal"
        elif wing_board_type == "calender":
            # CLOUD TODO
            print "TODO: calender board type is not implemented yet. Consider it as 'normal'"%wing_board_type
            board_type = "normal"
        else:
            print "TODO: unknown board type '%s'. Consider it as 'normal'"%wing_board_type
            board_type = 'normal'

        board = Board(name=wing["name"],
                      board_type=board_type,
                      last_updated_at=wing["last_updated_time"],
                      admin_id=wing["god_uid"],
                      article_count=(wing["next_number"] - 1))
        board.uid = wing["uid"]
        yield board


def best_article_gatherer (cursor, cursor2):
    type_dict = {}
    for _type in ["year", "month", "week"]:
        cursor.execute('''
            SELECT distint year, month, week
            FROM best_article
            WHERE type='%s'
        '''%_type)
        for record in cursor.fetchall():
            if _type not in type_dict:
                type_dict[_type] = []
            type_dict[_type].append(record)
    year_gen = None
    month_gen = None
    week_gen = None

    for _type in ['year', 'month', 'week']:
        for type_info in type_dict.get(_type, []):
            year = type_info['year']
            month = type_info['month']
            week = type_info['week']
            if _type == 'year':
                cursor.execute('''
                    SELECT article_uid, count
                    FROM best_article
                    WHERE
                        type='year' AND
                        year=%d
                '''%(year))
            elif _type == 'month':
                cursor.execute('''
                    SELECT article_uid, count
                    FROM best_article
                    WHERE
                        type='year' AND
                        year=%d AND
                        month=%d
                '''%(year, month))
            elif _type == 'week':
                cursor.execute('''
                    SELECT article_uid, count
                    FROM best_article
                    WHERE
                        type='year' AND
                        year=%d AND
                        month=%d AND
                        week=%d
                '''%(year, month, week))
            else:
                raise Exception("NOT REACHABLE")
            article_uid_list = [(record['article_uid'], record['count']) 
                                for record in cursor.fetchall()]
            yield {'year': year, 
                   'month': month, 
                   'week': week, 
                   'articles': article_uid_list}

def best_article_converter(_iter):
    for idx, wing in enumerate(_iter):
        if idx % 1000 == 0:
            print "NOW MOVING %d-th record of best article table..."%idx

        _type = wing["type"]
        if _type == "last":
            continue

        year = wing["year"]
        month = wing["month"]
        week = wing["week"]
        ba = BestArticle(year=year,
                         month=month,
                         week=week)
        ba._articles = wing["articles"]
        yield ba

def survey_gatherer(cursor, cursor2):
    cursor.execute('''SELECT * FROM survey
    WHERE is_psychological_test = 0
    ''')
    for record in cursor_generator(cursor):
        survey_id = record['id']
        cursor2.execute('''
            SELECT user_uid
            FROM survey_participant
            WHERE survey_id=%d
        '''%survey_id)
        answered_user = filter(lambda x: x is not None, 
                               [filter_user_uid(r['user_uid']) for r in cursor2.fetchall()])
        article_uid = record['article_uid'] 
        if article_uid is not None:
            cursor2.execute('''
                SELECT time,
                       uid AS article_uid
                FROM article
                WHERE
                    article.uid = %d
            '''%(article_uid))
            misc_info = cursor2.fetchone()
            if not misc_info:
                time = None
            else:
                time = misc_info['time']
        else:
            time = None
        record['answered_user'] = answered_user
        record['time'] = time
        
        yield record

def survey_converter(_iter):
    for idx, wing in enumerate(_iter):
        if idx % 1000 == 0:
            print "NOW MOVING %d-th record of survey table..."%idx

        due_date = wing["due"] or (datetime.utcnow() + timedelta(days=36500))
        survey = Survey(name=wing["subject"],
                        due_date=due_date,
                        parent_id=wing["article_uid"],
                        owner_id=filter_user_uid(wing["user_uid"]),
                        is_anonymous=wing["is_anonymous"],
                        permission_type=wing["permission_type"],
                        permission_value=wing["permission"] or "",
                        expose_level=wing["expose_level"],
                        min_vote_num=wing["minimum_number_of_votes"],
                        _answered_user=json.dumps(wing["answered_user"]),
                        created_at=wing["time"])
        survey.id = wing["id"]

        yield survey


def survey_question_gatherer(cursor, cursor2):
    cursor.execute('''
        SELECT survey_question.* 
        FROM survey_question
        JOIN survey
        ON survey_question.survey_id = survey.id
        WHERE survey.is_psychological_test = 0
    ''')

    for record in cursor_generator(cursor):
        question_id = record["id"]
        cursor2.execute('''
            SELECT id, "option"
            FROM survey_option
            WHERE
                question_id = %d
            ORDER BY id ASC
        '''%(question_id))

        so_dict_list = cursor2.fetchall()
        base_option_id = so_dict_list[0]['id']
        examples = [d['option'] for d in so_dict_list]
        cursor2.execute('''
            SELECT survey_selection.user_uid AS user_uid,
                   survey_option.question_id AS survey_question_id,
                   survey_option.id AS option_id
            FROM survey_selection 
            JOIN survey_option ON
                survey_selection.choice_id = survey_option.id
            JOIN survey_question ON
                survey_option.question_id = survey_question.id
            WHERE
                survey_question.id = %d
        '''%(question_id))

        survey_selection = []
        for option_assoc in cursor2.fetchall():
            option_assoc['answer'] = option_assoc['option_id'] - base_option_id
            survey_selection.append(option_assoc)

        record['examples'] = examples
        record['survey_selection'] = survey_selection

        yield record

def survey_question_converter(_iter):
    for idx, wing in enumerate(_iter):
        if idx % 1000 == 0:
            print "NOW MOVING %d-th record of survey question table..."%idx
        
        sq = SurveyQuestion(content=wing["question"],
                            min_answers=wing["lower_bound"],
                            max_answers=wing["upper_bound"],
                            _examples=json.dumps(wing["examples"]),
                            survey_id=wing["survey_id"],
                            order=wing["number"])
        sq.id = wing["id"]
        yield sq
        for p in wing["survey_selection"]:
            yield SurveyAnswer(survey_question_id=p["survey_question_id"],
                               user_id=filter_user_uid(p["user_uid"]),
                               answer=p["answer"])


def file_gatherer(cursor, cursor2):
    '''
    Type of Author Id of file 
    --
    user
    article  -> author of article
    cafe -> NULL
    app - TODO
    '''

    cursor.execute('''
        SELECT "file".*,
               uid_list.type AS parent_uid_type
        FROM "file"
        JOIN uid_list ON 
            "file".parent_uid = uid_list.uid
    ''')
    for record in cursor_generator(cursor):
        parent_uid_type = record["parent_uid_type"]
        parent_uid = record["parent_uid"]
        if parent_uid_type == "user":
            record["author_id"] = parent_uid 
        elif parent_uid_type == "article":
            cursor2.execute('''
                SELECT user_uid FROM article WHERE uid = %d
            '''%(parent_uid))
            record["author_id"] = filter_user_uid(cursor2.fetchone()["user_uid"])
        elif parent_uid_type == "cafe":
            record["author_id"] = None
        elif parent_uid_type == "app":
            print "App(%d) file won't be migrated in this phase"%parent_uid
            continue
            '''
            # FIXME: author of app
            record["author_id"] = None
            '''
        else:
            raise Exception("NOT REACHABLE: %s"%parent_uid_type)
        yield record

_PRINTABLE_CHARS = map(chr, xrange(0x20, 0x7e+1))

def _extract_ext(filename):
    idx = filename.rfind(".")
    if idx == -1:
        return ""
    else:
        return filename[idx:]


def file_converter(_iter):
    for idx, wing in enumerate(_iter):
        if idx % 1000 == 0:
            print "NOW MOVING %d-th record of file table..."%idx
        parent_uid = wing['parent_uid']
        ext = _extract_ext(wing['name'])

        filename = "%d"%wing["uid"]
        if ext:
            filename += ".%s"%ext

        f = File(filename=filename,
                 upload_filename=wing['name'],
                 mime=guess_mimetype(wing['name']),
                 filesize=wing['size'],
                 parent_id=wing['parent_uid'],
                 author_id=wing["author_id"],
                 created_at=wing['time'])
        f.uid = wing['uid']
        yield f

favorite_gatherer = make_single_gatherer("favorite", 
    '''JOIN uid_list 
       ON uid_list.uid = favorite.target_uid 
       WHERE uid_list.type != 'dolblog' 
''')
def favorite_converter(_iter):
    for idx, wing in enumerate(_iter):
        if idx % 1000 == 0:
            print "NOW MOVING %d-th record of favorite table..."%idx
        #FIXME: order in cloud.db
        if is_invalid_favorite_target_uid(wing["target_uid"]):
            print wing["target_uid"], "is target_uid!"
            continue

        if is_orphaned_file_uid(wing["target_uid"]):
            print wing["target_uid"], "is orphaned!"
            continue

        user_uid = filter_user_uid(wing["user_uid"])
        if user_uid is None:
            print "user_uid cannot be NULL!"
            continue

        favorite = Favorite(user_id=user_uid,
                            target_id=wing["target_uid"],
                            name=wing["name"],
                            order=wing["position"])
        favorite.id = wing["id"]
        yield favorite



def panorama_gatherer (cursor, cursor2):
    cursor.execute('''
        SELECT * FROM "panorama"
        ORDER BY time ASC
    ''')
    return cursor_generator(cursor)


def format_panorama(wing):
    return "placeholder for panorama(TODO)"


def panorama_converter(_iter):
    # FIXME: type is incompatible
    #
    for idx, wing in enumerate(_iter):
        if idx % 1000 == 0:
            print "NOW MOVING %d-th record of panorama table..."%idx


        '''
        type
        --
        "article" -> "article"
        "cafe" -> "gruop"
        "dolblog" -> x
        "user" -> x
        "comment" -> "comment"
        "commented" -> x
        "tag" -> "tag"
        '''
        type=wing["type"]
        '''
        "addrel" -> "add_rel"
        "invalid" -> x
        "app" -> x
        "modify" -> "modify"
        "survey_start" -> "survey_start"
        "removerel" -> "remove_rel"
        "article" -> "article"
        "cafe" -> "group"
        "file" -> "file"
        "remove" -> "remove"
        "move" -> "move"
        "dolblog" -> x
        "add_link" -> "add_menu" 
        "add" -> "add" 
        "user" -> "user"
        "remove_link" -> "remove_menu"
        '''
        event=wing["event"]
        from_group_id=wing["cafe_uid"]
        from_board_id=wing["board_uid"]
        user_uid=filter_user_uid(wing["user_uid"])
        target_uid=wing["target_uid"]
        created_at=wing["time"]
        class PanoramaSaver(BaseCustomSaver):
            def save(self, db):
                class FakeSession:
                    def __init__(self):
                        self.result = []
                    def add(self, elem):
                        self.result.append(elem)
                fake_session = FakeSession()
        yield PanoramaSaver()


def message_gatherer (cursor, cursor2):
    cursor.execute('''
        SELECT message.id AS id,
               message.sender_uid AS sender_uid,  
               message.receiver_uid AS receiver_uid,  
               message.sent_time AS sent_time,
               message.content AS content,
               sender_user.account AS sender_account,
               sender_user.name AS sender_name,
               receiver_user.account AS receiver_account,
               receiver_user.name AS receiver_name
        FROM message 
        JOIN "user" AS sender_user 
            ON message.sender_uid = sender_user.uid
        JOIN "user" AS receiver_user
            ON message.receiver_uid = receiver_user.uid
    ''')
    return cursor_generator(cursor)


def message_converter(_iter):
    for idx, wing in enumerate(_iter):
        if idx % 1000 == 0:
            print "NOW MOVING %d-th record of message table..."%idx

        class MessageSaver(BaseCustomSaver):
            def save(self, db):
                # SUPER-HACKY solution! T_T
                dumb = User("DumbAss", "1234",
                            realname="",
                            email="",
                            phone="",
                            birthday="",
                            classes="",
                            state="",
                            bs_number="2020",
                            ms_number="2040",
                            phd_number="2520",
                            graduate=None)
                dumb_thread = MessageThread()
                message = Message(dumb, dumb, "", dumb_thread)
                message.sender_id = wing["sender_uid"]
                message.sender_username = wing["sender_account"]
                message.sender_realname = wing["sender_name"]
                message.receiver_username = wing["receiver_account"]
                message.receiver_realname = wing["receiver_name"]
                message.receiver_id = wing["receiver_uid"]
                message.sent_at = wing["sent_time"]
                message.sender = None
                message.receiver = None
                message.thread = None

                content = wing["content"]
                message.content = content

                last_update = wing["sent_time"]
                sender_uid = wing["sender_uid"]
                receiver_uid = wing["receiver_uid"]

                old = db.query(MessageThread)\
                        .filter(or_(and_(MessageThread.user1_id == sender_uid,
                                         MessageThread.user2_id == receiver_uid),
                                    and_(MessageThread.user2_id == sender_uid,
                                         MessageThread.user1_id == receiver_uid)))\
                        .first()

                mt_id = None
                if old:
                    if old.last_updated_at < last_update:
                        old.last_content = content
                        old.last_updated_at = last_update
                    mt_id = old.id
                else:
                    mt = MessageThread(user1_id=sender_uid,
                                       user2_id=receiver_uid,
                                       last_updated_at=last_update)
                    mt.last_content = content
                    db.add(mt)
                    db.commit()
                    mt_id = mt.id

                message.thread_id = mt_id

                db.add(message)
                db.commit()
        yield MessageSaver()



def group_gatherer(cursor, cursor2):
    cursor.execute('''
        SELECT cafe.*,
               article.content AS main_page
        FROM cafe
        LEFT OUTER JOIN article ON 
            cafe.front_page_uid = article.uid
    ''')

    return cursor_generator(cursor)


def group_converter(_iter):
    for idx, wing in enumerate(_iter):
        if idx % 1000 == 0:
            print "NOW MOVING %d-th group of group table..."%idx

        group = Group(name=wing["title"],
                      admin_id=wing["god_uid"],
                      main_page=wing["main_page"] or "",
                      last_updated_at=wing["last_updated_time"],
                      article_count=0,
                      is_public=wing["is_public"])
        group._public_password = _hexdigest(wing["password"])
        group.uid = wing["uid"]
        yield group

group_menu_gatherer = make_single_gatherer("cafe_link", "ORDER BY position ASC")
def group_menu_converter(_iter):
    for idx, wing in enumerate(_iter):
        if idx % 1000 == 0:
            print "NOW MOVING %d-th group of groupmenu table..."%idx



        # cloud TODO
        #362133L possible type
        #  "text"
        #  "normal"
        #  "external" -> if and only if is_internal_link is False
        #  "in"
        #  "out"
        #  "cafe"
        #
        #  "forum" -> board
        #  "profile" -> board
        #  "image" -> board
        #  "anonym" -> board
        #  "calender" -> board
        # 
        # NOTE:
        #   Unique constraint for tuple (cafe_uid, position) doesn't hold in Wing SNUCSE
        #   Thus, reordering is needed
        #
        class GroupMenuSaver(BaseCustomSaver):
            def __init__(self, wing):
                self.wing = wing
            def save(self, db):
                wing_type = self.wing["type"]
                _type = self.wing["type"]
                if _type == "external":
                    menu_type = "link"
                elif _type == "text":
                    menu_type = "text"
                elif _type == "in":
                    menu_type = "indent"
                elif _type == "out":
                    menu_type = "outdent"
                elif _type == "cafe":
                    menu_type = "link"
                else:
                    print "NOTE: uncompatible cafe link type '%s'. Treat it as 'board'"%(_type)
                    menu_type = "board"

                iter_position = self.wing["position"]
                item = db.query(GroupMenu)\
                         .filter(GroupMenu.group_id == self.wing["cafe_uid"],
                                 GroupMenu.position >= iter_position) \
                         .order_by(GroupMenu.position.desc()).first()
                if item:
                    iter_position = item.position + 1

                if wing_type == "cafe":
                    external_url = "/%d"%self.wing["internal_uid"]
                    board_uid = None
                else:
                    external_url = self.wing["external_url"]
                    board_uid = self.wing["internal_uid"]
                    assert board_uid != 362133 and board_uid != 2983
                gm = GroupMenu(group_id=self.wing["cafe_uid"],
                               name=self.wing["name"],
                               board_uid=board_uid,
                               menu_type=menu_type,
                               url=external_url,
                               position=iter_position)
                gm.id = self.wing["id"]
                db.add(gm)
                db.commit()

        yield GroupMenuSaver(wing)
