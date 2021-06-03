from ..utils import *


class PollProcess(SendMessage):
    def __init__(self, bot, user_id: int):
        super(PollProcess, self).__init__(bot, user_id)

    def new_poll_process(self):
        poll_info = {
            "user_id": self.user_id,
        }

        get_product_info = {
            "question": {
                "text": "Введите вопрос",
            },
            "buttons": {
                "text": "Теперь введи название кнопок (через запятю или ;)",
                "extension": "buttons"
            },
            "preview": {
                "preview_text": "Сделал тебе превью твоего опроса! Проверь всё ли так, как ты хотел и, "
                                "если всё хорошо, то нажимай \"Готово\". Но если тебе нужно поменять что-то "
                                "в опросе, то просто нажми на кнопку с тем, что ты хочешь поменять"
            }
        }
        get_product_info = list(get_product_info.items())

        logging.info("Start adding new poll to user %s" % self.user_id)

        cur_index = 0

        while cur_index < len(get_product_info):
            param, source_param_info = get_product_info[cur_index]
            param_info = source_param_info.copy()

            if param in poll_info and poll_info[param]:
                cur_index += 1
                continue

            if "text" in param_info:
                cur_info = yield from self.get_product_info(**param_info)
            elif "preview_text" in param_info:
                to_change = yield from self.poll_preview(info=poll_info, text=param_info["preview_text"])

                if to_change != "done":
                    poll_info[to_change] = None
                    cur_index = 0
                    continue

                break
            else:
                logging.error("No params found in info: { %s: %s }" % (param, param_info))
                return

            if cur_info is None:
                cur_index -= 1

                if cur_index < 0:
                    self.delete_last_message()
                    logging.info("Cancel adding new poll to user %s" % self.user_id)
                    return

                last_param = get_product_info[cur_index][0]
                poll_info[last_param] = None

                continue
            else:
                cur_index += 1

            poll_info[param] = cur_info

        logging.info("Add new poll: %s" % poll_info)

        status = add_poll(**poll_info)

        if status["success"]:
            self.send_message(text="✅ Новый опрос успешно добавлен!\n"
                                   "Чтобы отвправить его в чат, напиши в этом чате @poll_tbot и выбери этот опрос")

            logging.info("Successful add new poll to user %s" % self.user_id)
        else:
            logging.error("Error while adding new poll: %s" % status)

            self.send_message(text="❌ Не удалось добавить новый опрос: %s" % status["message"])

        return status

    def get_product_info(self, text: str, extension: str = None):
        self.send_message(text=text, buttons=INPUT_BUTTONS)

        while True:
            yield from self.new_message()

            if not self.mes_text:
                self.send_message(text=text, buttons=INPUT_BUTTONS)
                continue

            if "назад" in self.mes_text:
                return None
            elif "помощь" in self.mes_text:
                self.send_message(text=HELP_MESSAGE + text, buttons=INPUT_BUTTONS)
            else:
                if extension == "buttons":
                    buttons_text = self.message["text"].replace(", ", ";").replace("; ", ";")
                    buttons = buttons_text.split(";")

                    if len(buttons) > 10:
                        self.send_message(
                            text="Вы не можете добавить больше 10 кнопок\n" + text,
                            buttons=INPUT_BUTTONS
                        )
                        continue

                    return buttons
                else:
                    return self.message["text"]

    def poll_preview(self, info: dict, text: str):
        self.send_message(text=info["question"], buttons=split_array_to_chunks(info["buttons"], num_in_chunk=2))
        poll_message_id = self.last_my_message_id

        lower_buttons = list(map(str.lower, info["buttons"]))

        buttons = [
            [("Вопрос", "question"), ("Кнопки", "buttons")],
            [("Готово", "done")]
        ]

        data_names = ["question", "buttons", "done"]

        text += "\n\n*Внимание!* Данный опрос является лишь превью настоящего опроса и " \
                "информация по нему не записывается"

        self.send_message(text=text, buttons=buttons)

        while True:
            yield from self.new_message()

            if self.mes_text in data_names:
                self.delete_last_message(message_id=poll_message_id)

                return self.mes_text
            elif self.mes_text in lower_buttons and self.callback:
                self.callback.answer(text="Да, это превью кнопка")
                continue

            self.send_message(text=CHOSE_BUTTON_MESSAGE + text, buttons=buttons)

    def user_pools_process(self):
        polls = get_user_polls(user_id=self.user_id)

        if not polls:
            self.send_message(text="Нет добавленных опросов")
            return False

        poll_ids = [poll["_id"] for poll in polls]
        questions = [(poll["question"], poll["_id"]) for poll in polls]
        questions = split_array_to_chunks(questions, num_in_chunk=2)

        offset = 0
        num_buttons_on_block = 3

        while True:
            current_buttons = questions[offset:offset + num_buttons_on_block]

            if offset > 0 and offset + num_buttons_on_block < len(questions):
                current_buttons.append(["⬅️", ("Меню", "меню"), "➡️"])
            elif offset + num_buttons_on_block < len(questions):
                current_buttons.append([("Меню", "меню"), "➡️"])
            elif offset > 0:
                current_buttons.append(["⬅️", ("Меню", "меню")])
            else:
                current_buttons.append([("Меню", "меню")])

            self.send_message(text=CHOSE_POLL_MESSAGE, buttons=current_buttons)

            while True:
                yield from self.new_message()

                if "меню" in self.mes_text:
                    return None
                elif "➡️" in self.mes_text and offset + num_buttons_on_block < len(questions):
                    offset += num_buttons_on_block
                    break
                elif "⬅️" in self.mes_text and offset > 0:
                    offset -= num_buttons_on_block
                    break
                elif self.mes_text in poll_ids:
                    poll_info = polls[poll_ids.index(self.mes_text)]

                    yield from self.show_poll_info(poll_id=poll_info["_id"])

                    break
                else:
                    self.send_message(text=CHOSE_BUTTON_MESSAGE, buttons=current_buttons)

    def show_poll_info(self, poll_id):
        poll_info = get_poll(poll_id=poll_id)

        buttons = poll_info["buttons"].copy()
        buttons_count = dict.fromkeys(buttons, 0)

        for user in poll_info["answers"]["users"]:
            button = buttons[user["vote"]]
            buttons_count[button] += 1

        buttons = [button + (" (%s)" % buttons_count[button] if buttons_count[button] else "") for button in buttons]

        text = "*Опрос \"%s\"*\nВарианты: %s\nВсего ответов: %s\n" \
               "Чтобы посмотреть список пользователей по варианту, кликни на соответствующую кнопку" % (
                   poll_info["question"], ", ".join(buttons), poll_info["answers"]["count"]
               )

        lower_buttons = list(map(str.lower, poll_info["buttons"]))
        buttons = split_array_to_chunks(poll_info["buttons"], num_in_chunk=2) + [BACK_BUTTON]

        self.send_message(text=text, buttons=buttons)

        while True:
            yield from self.new_message()

            if "назад" in self.mes_text:
                return None
            elif self.mes_text in lower_buttons:
                button_index = lower_buttons.index(self.mes_text)

                filter_users = list(
                    filter(
                        lambda user_info: user_info["vote"] == button_index,
                        poll_info["answers"]["users"],
                    )
                )

                if filter_users:
                    users_texts = []

                    for user in filter_users:
                        if user["username"]:
                            users_texts.append("@" + user["username"])
                        else:
                            users_texts.append("[%s](%s%s)" % (user["name"], TG_USER_LINK, user["id"]))

                    users_text = ", ".join(users_texts)

                    self.send_message(text="На кнопку \"%s\" нажали:\n\n%s" % (self.mes_text, users_text))
                else:
                    self.send_message(text="Пока никто не выбирал ответ %s" % self.mes_text)

                self.message_id = None

            self.send_message(text=text, buttons=buttons)
