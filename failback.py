_INVALID_USER_UID = set()
_INVALID_FAVORITE_TARGET_UID = set()
_ORPHANED_FILE_UID = set()
_END_OF_UID = [None]

from pprint import pprint

def cursor_generator(cursor):
    row = cursor.fetchone()
    while row:
        yield row
        row = cursor.fetchone()

def config_failback(cursor):
    tables = ["article", "comment", "tag", 
              "tag_relation", "tag_parent_relation",
              "favorite", "panorama", "survey"]

    for table in tables:
        query = '''SELECT DISTINCT "{0}".user_uid FROM "{0}" WHERE "{0}".user_uid NOT IN (SELECT uid FROM "user")'''.format(table)
        cursor.execute(query)
        for d in cursor_generator(cursor):
            user_uid = d["user_uid"]
            _INVALID_USER_UID.add(user_uid)

    print "len(Invalid  user uid)", len(_INVALID_USER_UID)
    pprint(_INVALID_USER_UID)
    cursor.execute('''
        SELECT MAX(uid) AS max FROM uid_list
    ''')
    _END_OF_UID[0] = cursor.fetchone()["max"]
    print "END OF UID", _END_OF_UID

    cursor.execute('''
        SELECT target_uid FROM favorite 
        WHERE target_uid NOT IN (SELECT uid FROM uid_list)
    ''')
    for d in cursor_generator(cursor):
        target_uid = d["target_uid"]
        _INVALID_FAVORITE_TARGET_UID.add(target_uid)

    cursor.execute('''
        select uid_list.uid from uid_list where uid_list.type = 'file' and uid_list.uid not in (select "file".uid from "file")
    ''')
    for d in cursor_generator(cursor):
        uid = d["uid"]
        _ORPHANED_FILE_UID.add(uid)


 
def get_end_of_uid():
    return _END_OF_UID[0]

def is_invalid_user_uid(user_uid):
    return user_uid in _INVALID_USER_UID

def filter_user_uid(user_uid):
    if is_invalid_user_uid(user_uid):
        return None
    else:
        return user_uid

def is_invalid_favorite_target_uid(target_uid):
    return target_uid in _INVALID_FAVORITE_TARGET_UID

def is_orphaned_file_uid(file_uid):
    return file_uid in _ORPHANED_FILE_UID
