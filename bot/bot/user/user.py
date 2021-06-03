from .poll import *


class UserProcess(PollProcess):
    def __init__(self, bot, user_id: int):
        super(UserProcess, self).__init__(bot, user_id)

        self.user_info = None

    def process(self):
        update_user_status = yield from self.update_user_info()

        if not update_user_status:
            return False

        while True:
            yield from self.new_message()

            use_message_id = False

            if "помо" in self.mes_text or "/help" in self.mes_text:
                self.send_message(text=HELP_MENU_MESSAGE, buttons=MAIN_MENU_BUTTONS)
                continue

            elif "добавить опрос" in self.mes_text:
                yield from self.new_poll_process()

            elif "опросы" in self.mes_text:
                yield from self.user_pools_process()
                use_message_id = True

            self.send_message(text=MENU_MESSAGE, buttons=MAIN_MENU_BUTTONS, use_message_id=use_message_id)

    def update_user_info(self):
        self.user_info = check_user_authorized(user_id=self.user_id)

        if not self.user_info:
            yield from self.new_message()

            logging.info("Add new user %s to db" % self.user_id)

            success = self.add_new_user()

            if not success:
                return False

            self.send_message(text=HELLO_MESSAGE)

        if not self.user_info["know_from"]:
            know_from = yield from self.how_did_user_know()

            if know_from:
                update_user_know_from(user_id=self.user_id, know_from=know_from)

                logging.info("Get know_from info from user %s: %s" % (self.user_id, know_from))

            self.send_message(text=ALMOST_READY_MESSAGE)
            self.send_message(text=MENU_MESSAGE, buttons=MAIN_MENU_BUTTONS, use_message_id=False)

        return True

    def add_new_user(self):
        surname = self.message["from_user"]["last_name"]
        name = self.message["from_user"]["first_name"] + (" " + surname if surname else "")
        username = self.message["from_user"]["username"]

        status = add_user(user_id=self.user_id, name=name, username=username)

        if status["success"]:
            self.user_info = status["info"]

            return True
        else:
            logging.error("User not added to db: %s" % status)
            self.send_message(text=status["message"])

            return False

    def how_did_user_know(self):
        self.send_message(text=HOW_DID_USER_KNOW_MESSAGE, buttons=HOW_DID_USER_KNOW_BUTTONS, use_message_id=False)

        while True:
            yield from self.new_message()

            if self.callback:
                return self.mes_text

            return self.message["text"]