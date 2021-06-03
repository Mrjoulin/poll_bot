# Standard library imports
import os
import time
import random
import string
import logging
import datetime
from typing import Union

from gridfs import GridFS
from pymongo import MongoClient
from pymongo.collection import Collection


# Constants

SERVER_TIME_RELATIVE_TO_MSK = int(time.strftime("%z", time.localtime())) // 100 - 3
TG_USER_LINK = "tg://user?id="
DEFAULT_ID_LEN = 6


def get_correct_date(date: datetime.datetime = None, iso: bool = True) -> Union[str, datetime.datetime]:
    # Return current date by MSK time (+3 UTC)
    if date is None or not isinstance(date, datetime.datetime):
        date = datetime.datetime.now()

    date -= datetime.timedelta(hours=SERVER_TIME_RELATIVE_TO_MSK)

    return date.isoformat() if iso else date


def gen_random_token(token_len: int = DEFAULT_ID_LEN):
    alp = string.ascii_letters + string.digits

    token = "".join([random.choice(alp) for _ in range(token_len)])

    return token


DB_NAME = os.getenv("DB_NAME")
USERS_COLLECTION = os.getenv("USERS_COLLECTION")
POLLS_COLLECTION = os.getenv("POLLS_COLLECTION")


class MongoDB:
    def __init__(self, db_name=None):
        logging.info("Connecting to MongoDB Client")

        self.client = MongoClient("mongodb")
        self.db = None
        self.fs = None
        # Queue for updating ts
        self.ts_queue = []

        if db_name:
            self.connect_to_database(db_name)

        logging.info('Successful connection')

    def connect_to_database(self, db_name):
        self.db = self.client[db_name]
        self.fs = GridFS(self.db)

        return self.db

    def get_collection(self, collection_name) -> Collection:
        return self.db[collection_name]

    def put_grid_info(self, info, comment=""):
        return self.fs.put(info, encoding='utf-8', comment=comment)

    def get_grid_object(self, file_id):
        return self.fs.get(file_id)


db = MongoDB(db_name=DB_NAME)


def check_user_authorized(user_id: int, users: Union[Collection, None] = None) -> Union[dict, None]:
    if not users:
        users = db.get_collection(USERS_COLLECTION)

    info = users.find_one(
        {
            "_id": user_id
        }
    )

    return dict(info) if info else None


def add_user(user_id: int, name: str, username: Union[str, None]) -> dict:
    users = db.get_collection(USERS_COLLECTION)

    if bool(check_user_authorized(user_id=user_id, users=users)):
        logging.error("User %s is already authorized" % user_id)

        return {
            "success": True,
            "message": "Пользователь уже авторизован"
        }

    post = {
        "_id": user_id,
        "name": name,
        "username": username,
        "registration_date": get_correct_date(iso=True),
        "know_from": None
    }

    try:
        logging.info("Insert new user %s in database" % user_id)
        users.insert_one(post)

        return {
            "success": True,
            "info": post
        }
    except Exception as e:
        logging.error("Error while adding new user %s to db:" % user_id)
        logging.exception(e)

        return {
            "success": False,
            "message": "Произошла какая-то ошибка при добавлении чата"
        }


def get_all_users() -> list:
    users = db.get_collection(USERS_COLLECTION)

    info = list(users.find())

    return info


def update_user_know_from(user_id: int, know_from: str):
    users = db.get_collection(USERS_COLLECTION)

    try:
        matched_count = users.update_one(
            {
                "_id": user_id
            },
            {
                "$set": {
                    "know_from": know_from
                }
            }
        ).matched_count

        if not matched_count:
            return {
                "success": False,
                "message": "Пользователь не авторизован"
            }

        return {
            "success": True
        }

    except Exception as e:
        logging.exception(e)

        return {
            "success": False,
            "message": "Произошла какая-то ошибка при обновлении информации по пользователю"
        }


# ** Pools **

def get_poll(poll_id: str, polls: Union[Collection, None] = None):
    if not polls:
        polls = db.get_collection(POLLS_COLLECTION)

    logging.info("Find poll: %s" % poll_id)

    info = polls.find_one(
        {
            "_id": poll_id
        }
    )

    return dict(info) if info else None


def get_user_polls(user_id: int, polls: Collection = None):
    if not polls:
        polls = db.get_collection(POLLS_COLLECTION)

    find_json = {
        "user_id": user_id
    }

    info = polls.find(find_json)

    return list(info)


def add_poll(user_id: int, question: str, buttons: list):
    polls = db.get_collection(POLLS_COLLECTION)

    poll_id = gen_random_token()

    while get_poll(poll_id=poll_id, polls=polls):
        logging.error("Poll ID duplication! Generate new poll ID")
        logging.error("Probability 1 : %s" % 64 ** DEFAULT_ID_LEN)

        poll_id = gen_random_token()

    poll_info = {
        "_id": poll_id,
        "user_id": user_id,
        "created_at": get_correct_date(iso=True),
        "question": question,
        "buttons": buttons,
        "answers": {
            "count": 0,
            "users": []
        }
    }

    try:
        logging.info("Create new poll for user %s" % user_id)

        polls.insert_one(poll_info)

        return {
            "success": True,
            "info": poll_info
        }
    except Exception as e:
        logging.error("Error while creating new poll for user %s:" % user_id)
        logging.exception(e)

        return {
            "success": False,
            "message": "Произошла какая-то ошибка при добавлении опроса"
        }


def update_poll_user_vote(pool_id: str, vote: int, user_id: int, name: str, username: Union[str, None]):
    pools = db.get_collection(POLLS_COLLECTION)

    pool_info = get_poll(poll_id=pool_id, polls=pools)

    if not pool_info:
        return {
            "success": False,
            "message": "Опрос не найден"
        }

    users = pool_info["answers"]["users"]
    count = pool_info["answers"]["count"]

    users_answered = [user["id"] for user in users]
    users_votes = [user["vote"] for user in users]

    if user_id in users_answered:
        user_index = users_answered.index(user_id)

        if vote == users_votes[user_index]:
            # Remove answer
            users.pop(user_index)
            count -= 1
        else:
            users[user_index]["vote"] = vote
    else:
        user_info = {
            "id": user_id,
            "name": name,
            "username": username,
            "vote": vote
        }

        users.append(user_info)

        count += 1

    try:
        pools.update_one(
            {
                "_id": pool_id
            },
            {
                "$set": {
                    "answers": {
                        "count": count,
                        "users": users
                    }
                }
            }
        )

        pool_info["answers"]["users"] = users

        return {
            "success": True,
            "info": pool_info
        }

    except Exception as e:
        logging.exception(e)

        return {
            "success": False,
            "message": "Произошла какая-то ошибка при обновлении информации по пользователю"
        }
