from botal import Botal

from .user import *


bot = Bot(os.getenv("BOT_TOKEN"))

logging.info(f'Bot info: {bot.get_me()}')

handler = Botal(listen(bot), get_event_user_id)


def get_user_process(user_id: int) -> 'UserProcess':
    if user_id not in AUTH_USERS:
        new_user = UserProcess(bot=bot, user_id=user_id)

        AUTH_USERS[user_id] = new_user

    return AUTH_USERS[user_id]


@handler.handler
def on_message(user_id):
    logging.info('Get new message from user %s' % user_id)

    user_process = get_user_process(user_id=user_id)

    yield from user_process.process()


@handler.error_handler(Exception)
def on_error(user_id, e):
    if not isinstance(e, StopIteration):
        logging.exception(e)
        bot.sendMessage(chat_id=user_id, text='Извини, у меня тут какие-то внутренние технические неполадки (%s)' % e)


def start_bot():
    # Colorized info
    logging.error("Start bot")

    handler.run()
