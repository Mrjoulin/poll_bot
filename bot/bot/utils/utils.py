# Standard library imports
import threading as thr

# Third party imports
import requests
from validators import url as correct_url
from dateutil.parser import parse as parse_date, ParserError
from telegram.error import NetworkError, Unauthorized
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram import InlineQuery, InlineQueryResultArticle, InputTextMessageContent, CallbackQuery

# Local imports

from .db import *

# Environment info

ADMINS = [int(admin_id) for admin_id in os.getenv("ADMINS_IDS").split(",")]
IS_PROD = bool(int(os.getenv("IS_PROD")))

# Currently authorized in bot users

AUTH_USERS = {}


def split_array_to_chunks(arr, num_in_chunk):
    if num_in_chunk < 1:
        return arr

    new_arr = []

    for i in range(len(arr)):
        if i % num_in_chunk == 0:
            new_arr.append([])

        new_arr[-1].append(arr[i])

    return new_arr


def get_correct_text(text, extended=True):
    to_replace = "_~["

    if extended:
        to_replace += "*`"

    for char in to_replace:
        text = text.replace(char, "\\" + char)

    return text


def get_dot_number(number: Union[int, float]):
    int_num, fractional_num = str(float(number)).split(".")

    split_number = split_array_to_chunks(int_num[::-1], num_in_chunk=3)

    correct_number = " ".join(reversed(["".join(reversed(cur_number)) for cur_number in split_number]))

    return correct_number + (f",{fractional_num}" if fractional_num != "0" else "")


def listen(bot):
    try:
        update_id = bot.get_updates()[0].update_id
    except IndexError:
        update_id = None

    # Remove telegram updating logging warnings
    logging.getLogger("telegram.vendor.ptb_urllib3.urllib3.connectionpool").setLevel(logging.ERROR)

    while True:
        try:
            for update in bot.get_updates(offset=update_id, timeout=10):
                update_id = update.update_id + 1

                if update.message or update.callback_query or update.inline_query:
                    yield update
        except NetworkError:
            time.sleep(1)
        except Unauthorized:
            update_id += 1
        except Exception as e:
            logging.error(e)


def get_event_user_id(event: Update):
    if event.message:
        return event.message.chat_id
    elif event.callback_query:
        return event.callback_query.from_user.id
    elif event.inline_query:
        return event.inline_query.from_user.id
    else:
        return None


class NewMessage:
    def __init__(self, bot: Bot):
        self.bot = bot

        self.callback = None
        self.message = None
        self.mes_text = None
        self.message_id = None

        self.new_payment = None

    def new_message(self):
        while True:
            event = (yield)

            if event.inline_query:
                self.process_inline_query(query=event.inline_query)
                continue

            if event.callback_query:
                self.callback = event.callback_query

                self.mes_text = event.callback_query.data

                if self.mes_text.startswith("poll_vote"):
                    self.process_poll_vote()
                    continue

                self.message = event.callback_query.message
                self.message_id = self.message.message_id

                user = self.callback["from_user"]
            else:
                self.callback = None

                self.message = event.message
                self.mes_text = self.message.text.lower() if self.message.text else self.message.caption or ""
                self.message_id = None

                user = self.message["from_user"]

            logging.info("New %s from %s (%s): %s" % (
                "callback" if self.callback else "message", user["first_name"], user["id"], self.mes_text
            ))

            return

    def process_inline_query(self, query: InlineQuery):
        user_id = query.from_user.id

        all_polls = get_user_polls(user_id=user_id)

        if not all_polls:
            logging.error("Error while getting products to inline query: %s" % all_polls)
            query.answer(results=[])
            return None

        query_text = query.query.lower()
        polls = []

        logging.info("Find %s polls to search by query \"%s\"" % (len(all_polls), query_text))

        for poll in all_polls:
            if query_text in poll["question"].lower():
                message = InputTextMessageContent(message_text=poll["question"])

                buttons = [
                    (button, "poll_vote_%s_%s" % (
                        poll["_id"], poll["buttons"].index(button)
                    )) for button in poll["buttons"]
                ]
                buttons = split_array_to_chunks(buttons, num_in_chunk=2)
                reply_markup = get_reply_markup(buttons)

                article = InlineQueryResultArticle(
                    id=str(random.randint(10 * 3, 10 ** 30)),
                    title=poll["question"],
                    description=", ".join(poll["buttons"]),
                    input_message_content=message,
                    reply_markup=reply_markup
                )

                polls.append(article)

        query.answer(results=polls)

    def process_poll_vote(self):
        poll_info = self.mes_text.split("_")

        if len(poll_info) < 4:
            return None

        poll_id, vote_index = poll_info[2], int(poll_info[3])

        user_id = self.callback["from_user"]["id"]
        surname = self.callback["from_user"]["last_name"]
        name = self.callback["from_user"]["first_name"] + (" " + surname if surname else "")
        username = self.callback["from_user"]["username"]

        logging.info("New poll %s vote by user %s (%s)" % (poll_id, username, user_id))

        status = update_poll_user_vote(pool_id=poll_id, vote=vote_index, user_id=user_id, name=name, username=username)

        if status["success"]:
            poll_info = status["info"]
            buttons = poll_info["buttons"].copy()
            buttons_count = dict.fromkeys(buttons, 0)

            for user in poll_info["answers"]["users"]:
                button = buttons[int(user["vote"])]
                buttons_count[button] += 1

            buttons = [
                (
                    button + ((" " + str(buttons_count[button])) if buttons_count[button] else ""),
                    "poll_vote_%s_%s" % (poll_info["_id"], buttons.index(button))
                 ) for button in buttons
            ]

            buttons = split_array_to_chunks(buttons, num_in_chunk=2)
            reply_markup = get_reply_markup(buttons)

            try:
                self.callback.edit_message_reply_markup(reply_markup=reply_markup)
                self.callback.answer(text="You answered for \"%s\"" % poll_info["buttons"][vote_index])
            except Exception as e:
                logging.error("Error while sending reply markup for poll %s: %s" % (poll_info["_id"], e))
        else:
            logging.error("Not update poll user vote: %s" % status)


def get_reply_markup(buttons):
    if buttons is not None:
        keyboard = []

        for reply_buttons in buttons:
            if not isinstance(reply_buttons, list):
                reply_buttons = [reply_buttons]

            line = []

            for reply_button in reply_buttons:
                if isinstance(reply_button, tuple):
                    if correct_url(reply_button[1]):
                        button = InlineKeyboardButton(reply_button[0], url=reply_button[1])
                    else:
                        button = InlineKeyboardButton(reply_button[0], callback_data=reply_button[1])
                else:
                    button = InlineKeyboardButton(reply_button, callback_data=reply_button.lower())

                line.append(button)

            keyboard.append(line)

        markup = InlineKeyboardMarkup(keyboard)
    else:
        markup = None

    return markup


class SendMessage(NewMessage):
    def __init__(self, bot: Bot, user_id: int):
        super(SendMessage, self).__init__(bot)

        self.bot = bot
        self.user_id = int(user_id)

        self.last_my_message_id = None
        self.last_send_text = None
        self.last_send_buttons = None

    def send_message(self, text, buttons=None, photo=None, use_message_id=True, attempts=2):
        markup = get_reply_markup(buttons=buttons)

        text = get_correct_text(text, extended=False)

        try:
            if photo:
                message = self.bot.send_photo(
                    chat_id=self.user_id, caption=text, photo=photo, reply_markup=markup, parse_mode="markdown"
                )

                if not isinstance(photo, str):
                    photo_id = message.photo[-1].file_id
                    new_path = "/".join(photo.name.split("/")[:-1]) + "/%s.png" % photo_id
                    os.rename(photo.name, new_path)

                self.last_my_message_id = None

            elif self.message_id is None or self.message_id != self.last_my_message_id or not use_message_id:
                if self.message_id is not None and self.message_id != self.last_my_message_id and use_message_id:
                    self.delete_last_message()

                mes_id = self.bot.send_message(
                    chat_id=self.user_id, text=text, reply_markup=markup, parse_mode="markdown"
                ).message_id
                self.last_my_message_id = mes_id

            elif text != self.last_send_text:
                self.bot.edit_message_text(
                    chat_id=self.user_id, message_id=self.message_id, text=text,
                    reply_markup=markup, parse_mode="markdown"
                )
            elif buttons != self.last_send_buttons:
                self.bot.edit_message_reply_markup(
                    chat_id=self.user_id, message_id=self.message_id, reply_markup=markup
                )
            elif self.callback:
                self.callback.answer(text="✅ Данные успешно обновлены")
                self.callback = None

            if self.callback:
                self.callback.answer()

            self.callback = None
            self.last_send_text = text

            if buttons:
                self.last_send_buttons = []
                for buttons_line in buttons:
                    if isinstance(buttons_line, list):
                        self.last_send_buttons.append(buttons_line.copy())
                    else:
                        self.last_send_buttons.append(buttons_line)
            else:
                self.last_send_buttons = None

        except Exception as e:
            logging.error("Error while sending message to chat %s: %s" % (self.user_id, e))

            if attempts > 0:
                logging.info("Try send message after 1 second")
                thr.Timer(1, self.send_message, [get_correct_text(text), buttons, photo, None, attempts - 1]).start()
            else:
                logging.error("Max num attempts to send message to chat %s" % self.user_id)

    def delete_last_message(self, message_id=None):
        try:
            if message_id:
                self.bot.deleteMessage(chat_id=self.user_id, message_id=message_id)

                if message_id == self.message_id:
                    self.message_id = None

                return True
            elif self.message_id:
                self.bot.deleteMessage(chat_id=self.user_id, message_id=self.message_id)
                self.message_id = None

                return True
        except Exception as e:
            logging.error("Can't delete message %s: %s" % (message_id or self.message_id, e))

        return False
