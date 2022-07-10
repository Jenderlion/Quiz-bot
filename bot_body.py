import db_handler
import quiz_handler
import datetime
import logging
import telebot
import json
import pandas
import openpyxl  # for correct pandas work
from telebot.types import ReplyKeyboardMarkup
from telebot.types import InlineKeyboardMarkup
from telebot.types import InlineKeyboardButton
import time
from bot_init import init_logger
import bot_init
import functools
import threading


# set new StreamHandler with level DEBUG by default
log_handler = logging.StreamHandler()
log_handler.level = logging.INFO
init_logger.addHandler(log_handler)


# bot init
tg_bot = telebot.TeleBot(bot_init.get_bot_api_token())


# bot settings
min_time_delta = 2


# wrappers
def message_wrapper(func):
    """Decorator that writes messages to logs"""

    def wrapper(*args):
        message: telebot.types.Message = args[0]
        user_quiz_status = db_handler.get_quiz_status(message.from_user.id)
        last_message_time = db_handler.get_last_timestamp(message.from_user.id)
        current_message_date = datetime.datetime.fromtimestamp(float(message.date))
        db_handler.add_message_in_log(
            message.from_user.id,
            message.id,
            message.text,
            float(message.date)
        )
        time_delta = (current_message_date - last_message_time).seconds
        if user_quiz_status is None:
            if time_delta >= min_time_delta:  # change it in bot settings
                func(message)
            else:
                simple_send_message(message.chat.id, 'Вы отправляете сообщения слишком часто!',
                                    None)
        else:

            current_quiz = int(user_quiz_status.split()[0])
            current_question = int(user_quiz_status.split()[1])
            is_rewrite = False
            if 'r' in user_quiz_status:
                is_rewrite = True
            if is_rewrite is False:
                answer_status = db_handler.add_new_answer(
                    message.from_user.id,
                    current_quiz,
                    current_question,
                    message.text
                )
            else:
                answer_status = db_handler.rewrite_answer(
                    message.from_user.id,
                    current_quiz,
                    current_question,
                    message.text
                )
                simple_send_message(
                    message.chat.id,
                    'Ответ успешно перезаписан!',
                    get_welcome_markup()
                )
            if answer_status is False:
                simple_send_message(message.chat.id, 'Что-то пошло не так :(\n\n'
                                                     'Попробуйте ещё раз или свяжитесь с'
                                                     ' администратором')
            elif not is_rewrite:
                question_list = db_handler.get_list_of_questions_in_quiz(current_quiz)
                if len(question_list) > current_question:
                    db_handler.update_user_quiz_status(
                        message.from_user.id,
                        f'{current_quiz} {current_question + 1}'
                    )
                    send_question(message.from_user.id, message.chat.id)

                elif len(question_list) <= current_question:
                    end_quiz(message.from_user.id, message.chat.id, current_quiz)

    return wrapper


def document_wrapper(func):
    """Decorator that writes doc-info messages to logs"""

    def wrapper(*args):
        message: telebot.types.Message = args[0]
        last_message_time = db_handler.get_last_timestamp(message.from_user.id)
        current_message_date = datetime.datetime.fromtimestamp(float(message.date))
        db_handler.add_message_in_log(
            message.from_user.id,
            message.id,
            f'Doc: {message.document.file_name}',
            float(message.date)
        )
        time_delta = (current_message_date - last_message_time).seconds
        if time_delta >= min_time_delta:  # change in bot settings
            func(message)
        else:
            simple_send_message(message.chat.id, 'Вы отправляете сообщения слишком часто!', None)

    return wrapper


def callback_wrapper(func):
    """Decorator that writes callback messages to logs"""

    def wrapper(*args):
        call: telebot.types.CallbackQuery = args[0]
        tg_bot.edit_message_reply_markup(call.message.chat.id, call.message.id, reply_markup=None)
        last_message_time = db_handler.get_last_timestamp(call.from_user.id)
        current_message_date = datetime.datetime.now()
        db_handler.add_message_in_log(
            call.from_user.id,
            call.message.id,
            f'In-Line: {call.data}',
            current_message_date.timestamp()
        )
        time_delta = (current_message_date - last_message_time).seconds
        if time_delta >= min_time_delta:  # change in bot settings
            func(call)
        else:
            simple_send_message(
                call.message.chat.id,
                'Вы отправляете сообщения слишком часто!',
                None
            )

    return wrapper


def rule_wrapper(rules):
    """A decorator that enables (for editor+) or disables (for user) the execution of function,
    also checks if the user is banned.

    This decorator checks the availability of USER GROUP by the RULES passed and, if everything is
    OK, allows the function to be executed, otherwise it does nothing
    """

    def decorator(func):

        def wrapper(*args):
            message: telebot.types.Message = args[0]
            user = db_handler.get_user_info(message.from_user.id)
            if user.is_ban:
                simple_send_message(message.chat.id, 'Вы забанены!\n\n'
                                                     'Если Вы считаете, что полученная блокировка'
                                                     ' несправедлива, свяжитесь с администартором:'
                                                     ' введите команду /help и нажмите на пункт'
                                                     ' "Мне нужна помощь!"')
            elif user.group in rules:
                func(message)

        return wrapper

    return decorator


# general functions
def end_quiz(tg_id, chat_id, quiz_id):
    """Initiates completion of the quiz"""
    gratitude_message = db_handler.get_end_message(quiz_id)
    simple_send_message(
        chat_id,
        gratitude_message,
        get_welcome_markup()
    )
    db_handler.update_user_quiz_status(tg_id, None)


def simple_send_message(chat_id, message_text, markup=None):
    """Simple send-message function"""
    tg_bot.send_message(chat_id, message_text, reply_markup=markup)
    init_logger.info('Message "%s" to user with id: %s' % (message_text, chat_id))


def send_question(tg_id: int, chat_id: int):
    """Initiates checking and sending a message with a question

    Keep in mind that sending several "empty" questions at once is not recommended!!!

    :param tg_id: user id (message.from_user.id)
    :param chat_id: chat id (message.chat.id)
    :return: None
    """
    user = db_handler.get_user_info(tg_id)
    question_data = user.quiz_status.split()
    current_quiz_id = int(question_data[0])
    current_question_id = int(question_data[1])
    quiz_questions_list = db_handler.get_list_of_questions_in_quiz(current_quiz_id)
    if len(quiz_questions_list) < current_question_id:
        end_quiz(tg_id, chat_id, current_quiz_id)
    current_question: db_handler.QuizQuestions = quiz_questions_list[current_question_id - 1]
    if current_question.quest_relation:
        check_quest_id, check_value = current_question.quest_relation.split(' -> ')
        if not db_handler.check_quest_relation(
                tg_id, int(current_quiz_id),
                int(check_quest_id),
                check_value
        ):
            db_handler.add_new_answer(tg_id, current_quiz_id, current_question_id, 'None')
            db_handler.update_user_quiz_status(
                tg_id, f'{current_quiz_id} {current_question_id + 1}'
            )
            send_question(tg_id, chat_id)
        else:
            quest_text = current_question.quest_text
            quest_answers = current_question.quest_ans.split(' || ')
            if quest_answers[0] == 'MANUAL_INPUT':
                ans_menu = None
            else:
                ans_menu = get_question_markup(quest_answers)
            simple_send_message(chat_id, quest_text, ans_menu)
    else:
        quest_text = current_question.quest_text
        quest_answers = current_question.quest_ans.split(' || ')
        if quest_answers[0] == 'MANUAL_INPUT':
            ans_menu = None
        else:
            ans_menu = get_question_markup(quest_answers)
        simple_send_message(chat_id, quest_text, ans_menu)


def get_question_markup(ans_list):
    """Constructs a one-time keyboard with data from ans_list"""
    question_menu = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for ans in ans_list:
        question_menu.row(ans)
    return question_menu


def get_available_quiz_inline_markup(input_list: list or tuple, completed_quizzes_id: set):
    """Create inline menu with available quizzes"""
    quiz_menu = InlineKeyboardMarkup(row_width=1)
    for _ in input_list:
        if _[1] not in completed_quizzes_id:
            quiz_menu.add(
                InlineKeyboardButton(text=_[0], callback_data=f'start_quiz {_[1]}')
            )
    return quiz_menu


@functools.cache
def get_welcome_markup():
    """Create welcome greet menu"""

    greet_menu = ReplyKeyboardMarkup(resize_keyboard=True)
    greet_menu.row('Пройти опрос')
    greet_menu.row('Изменить ответы в последнем опросе')
    greet_menu.row('Настройки рассылки')
    greet_menu.row('Мой статус')

    return greet_menu


@functools.cache
def get_editor_inline_markup():
    """Create editor inline menu"""

    editor_menu = InlineKeyboardMarkup(row_width=1)
    editor_menu.add(
        InlineKeyboardButton(text='Получить список всех опросов', callback_data=f'list')
    )
    editor_menu.add(
        InlineKeyboardButton(text='Получить список видимых опросов', callback_data=f'visible_list')
    )

    return editor_menu


def get_help_inline_markup():
    """Create help-message inline menu"""

    help_menu = InlineKeyboardMarkup(row_width=1)
    help_menu.add(
        InlineKeyboardButton(text='Мне нужна помощь!', callback_data='help')
    )
    help_menu.add(
        InlineKeyboardButton(text='Я нашёл баг!', callback_data='bug_find')
    )
    help_menu.add(
        InlineKeyboardButton(text='Как мне получить такого же бота?', callback_data='get_a_project')
    )
    return help_menu


def quiz_list_prepare(message_tuple):
    """Returns string with quizzes info"""
    if len(message_tuple) == 2:
        quiz_l = db_handler.get_quiz_list()
        proc_quiz_l = ['Последние 10 опросов:\n']
    else:
        quiz_l = db_handler.get_quiz_list(True)
        proc_quiz_l = ['Последние 10 видимых опросов:\n']
    for quiz in quiz_l:
        proc_quiz_l.append(f'Имя: {quiz[0]}\nID: {quiz[1]}\nВидимость: {quiz[2]}\n')

    return '\n'.join(proc_quiz_l)


def auto_unban():
    """Separate thread for automated user unbanning"""
    while True:
        active_ban_list = db_handler.get_active_ban_list()
        for ban in active_ban_list:
            if ban.unban_time <= datetime.datetime.now():
                db_handler.unban_user(0, ban.tg_id)
        time.sleep(30)


def check_term(term: str):
    """Checks the term against a pattern [num][unit] like 5m, 7d and etc"""
    term_unit = term[-1]
    term_numeric = term[:-1]
    return term_unit in ('s', 'm', 'h', 'd') and term_numeric.isdigit()


def mailing(users_id: tuple or list, msg_text):
    """Auto-mailing

    Send {msg_text} for all users with id in {users_id}

    :param users_id: target ids
    :param msg_text: message for users
    :return: None
    """
    for user_id in users_id:
        simple_send_message(user_id, msg_text, get_welcome_markup())


# message handlers
@tg_bot.message_handler(commands=['start'])
# Decorator cannot be used because the user must be added first
def welcome_handler(message: telebot.types.Message):
    """Simple welcome-message handler

    Adds a new user if it doesn't already exist
    """
    db_handler.add_user(message.from_user.id, message.id, message.text, float(message.date))
    msg = f'Привет! Я автоматизированная система, созданная для проведения опросов среди' \
          f' пользователей Telegram ©.\n\n' \
          f'Правила пользования следующие:\n' \
          f'1. Будьте вежливы и не пытайтесь меня сломать — у меня тоже есть чувства.\n' \
          f'2. Внимательно читайте вопросы и ответы, ведь исправить их можно только в последнем' \
          f' пройденном опросе!' \
          f'3. Я всё ещё нахожусь в состоянии разработки. Если вы нашли баг, пожалуйста, введите' \
          f' команду /help и воспользуйтесь соответствующим пунктом меню.' \
          f'4. Если Вы начали проходить опрос, то его необходимо закончить, прежде чем перейти к' \
          f' другому функционалу.' \
          f'5. Не отправляйте сообщения чаще, чем раз в {min_time_delta} секунд.\n\n' \
          f'Особенное правило - в любой непонятной ситуации пишите /help'
    simple_send_message(message.chat.id, msg, get_welcome_markup())


@tg_bot.message_handler(commands=['help', 'h'])
@message_wrapper
def help_handler(message: telebot.types.Message):
    """/help handler"""
    simple_send_message(message.chat.id, 'Что случилось?', get_help_inline_markup())


@tg_bot.message_handler(commands=['role'])
@rule_wrapper(('admin', 'm_admin'))
@message_wrapper
def set_role_handler(message: telebot.types.Message):
    """/role handler"""
    command_seq = message.text.split()
    if len(command_seq) == 1:
        msg_text = '/role - отправляет это сообщение с помощью\n' \
                   '/role {id} - отправляет информацию о пользователе с {id}\n' \
                   '/role {id} {group} - установить {group} для пользователя с {id}:' \
                   ' group == (user, editor, admin)'
        simple_send_message(message.chat.id, msg_text)
    else:
        target_user_id = int(command_seq[1])
        if len(command_seq) == 2:
            target_user = db_handler.get_user_info(target_user_id)
            group_dict = {
                'ban': 'забанен',
                'user': 'пользователь',
                'editor': 'редактор',
                'admin': 'администратор',
                'm_admin': 'главный администратор'
            }
            simple_send_message(
                message.chat.id,
                f'ID: {target_user.tg_user_id}\n'
                f'Внутренний ID: {target_user.internal_user_id}\n'
                f'Роль: {group_dict[target_user.group]}\n'
                f'Рассылка: {"включена" if target_user.mailing else "отключена"}'
            )
        elif command_seq[2] in ('user', 'editor', 'admin'):
            target_user = db_handler.get_user_info(target_user_id)
            if target_user.group not in ('m_admin', 'ban'):
                db_handler.update_user_group(message.from_user.id, target_user_id, command_seq[2])
                simple_send_message(
                    message.chat.id,
                    f'Новая группа "{command_seq[2]}" установлена для пользователя с'
                    f' id {target_user_id}',
                    get_welcome_markup()
                )
            else:
                simple_send_message(
                    message.chat.id,
                    'Этому пользователю нельзя изменить группу!',
                    get_welcome_markup()
                )
        else:
            simple_send_message(
                message.chat.id,
                'Ошибка в написании команды',
                get_welcome_markup()
            )


@tg_bot.message_handler(commands=['ban'])
@rule_wrapper(('admin', 'm_admin'))
@message_wrapper
def ban_handler(message: telebot.types.Message):
    """/ban handler"""
    command_seq = message.text.split()
    if len(command_seq) == 1:
        msg_text = '/ban - отправляет это сообщение с помощью\n' \
                   '/ban {id} {term} {reason} - банит пользователя с {id} на срок {term} с' \
                   ' причиной {reason}\n' \
                   '/unban - вывод сообщения с помощью по разбану'
        simple_send_message(message.chat.id, msg_text)
    elif len(command_seq) >= 4:
        if command_seq[1].isdigit():
            if check_term(command_seq[2]):
                target_id = int(command_seq[1])
                ban_term = command_seq[2]
                ban_reason = ' '.join(command_seq[3:])
                try:
                    if db_handler.get_user_info(target_id).group != 'm_admin':
                        db_handler.ban_user(message.from_user.id, target_id, ban_reason, ban_term)
                        simple_send_message(
                            message.chat.id,
                            f'Пользователь с ID {target_id} забанен на {ban_term} по причине'
                            f' "{ban_reason}"'
                        )
                    else:
                        simple_send_message(
                            message.chat.id,
                            f'Забанить главного администратора нельзя!'
                        )
                except IndexError:
                    simple_send_message(
                        message.chat.id,
                        f'Пользователя с таким ID не существует!'
                    )
            else:
                simple_send_message(message.chat.id, 'Некорректный срок бана!')
        else:
            simple_send_message(message.chat.id, 'ID должен быть числом!')
    elif len(command_seq) == 2:
        pass


@tg_bot.message_handler(commands=['unban'])
@rule_wrapper(('admin', 'm_admin'))
@message_wrapper
def unban_handler(message: telebot.types.Message):
    """/unban handler"""
    command_seq = message.text.split()
    if len(command_seq) == 1:
        msg_text = '/unban - отправляет это сообщение с помощью\n' \
                   '/unban {id} {optional: reason} - разбанивает пользователя с {id}' \
                   '/ban - вывод сообщения с помощью по бану'
        simple_send_message(message.chat.id, msg_text)
    elif len(command_seq) >= 2:
        if command_seq[1].isdigit():
            reason = None
            if len(command_seq) >= 3:
                reason = ' '.join(command_seq[3:])
            db_handler.unban_user(message.from_user.id, int(command_seq[1]), reason)
            simple_send_message(message.chat.id, 'Пользователь успешно разбанен!')
        else:
            simple_send_message(message.chat.id, 'ID должен состоять только из цифр')


@tg_bot.message_handler(commands=['message'])
@rule_wrapper(('admin', 'm_admin'))
@message_wrapper
def unban_handler(message: telebot.types.Message):
    """"/message handler"""
    command_seq = message.text.split()
    if len(command_seq) <= 2:
        msg_text = '/message - отправляет это сообщение с помощью\n' \
                   '/message {id} {message} - остправляет пользователю с {id} сообщение {message}' \
                   '/message {group} {message} - остправляет пользователю с {id} сообщение' \
                   ' {message}: для группы "user" применяется флаг рассылки'
        simple_send_message(message.chat.id, msg_text)
    else:
        if command_seq[1].isdigit():
            try:
                simple_send_message(int(command_seq[1]), ' '.join(command_seq[2:]))
                simple_send_message(message.chat.id, 'Сообщение отправлено!')
            except Exception as exc:
                simple_send_message(message.chat.id, f'Exception!\n{type(exc)}\n{exc}')
        elif command_seq[1] in ('user', 'editor', 'm_admin', 'admin'):
            if command_seq[1] == 'user':
                target_ids = db_handler.get_users_id('user', True)
            else:
                target_ids = db_handler.get_users_id(command_seq[1])
            mailing(target_ids, ' '.join(command_seq[2:]))
            simple_send_message(message.chat.id, 'Рассылка завершена!')
        else:
            simple_send_message(message.chat.id, 'Некорректная группа или ID!')


@tg_bot.message_handler(commands=['quiz', 'editor'])
@rule_wrapper(('editor', 'admin', 'm_admin'))
@message_wrapper
def editor_handler(message: telebot.types.Message):
    """/quiz or /editor handler"""
    message_tuple = tuple(message.text.split())
    if len(message_tuple) == 1:
        msg_text = '/quiz - отправляет меню редактора\n' \
                   '/quiz {id} - отправляет результаты опроса\n' \
                   '/quiz list - отправляет список 10 последних добавленных опросов\n' \
                   '/quiz vis {id} {status} - установить {status} видимости для опроса с {id}'
        simple_send_message(message.chat.id, msg_text, get_editor_inline_markup())
    elif message_tuple[1] in ('list', ):
        ans = quiz_list_prepare(message_tuple)
        simple_send_message(message.chat.id, ans, get_welcome_markup())
    elif message_tuple[1] in ('vis', ):
        if message_tuple[2].isdigit():
            if message_tuple[3] in ('True', 'False'):
                ans = db_handler.update_quiz_status(
                    message_tuple[2],
                    message.chat.id,
                    message_tuple[3]
                )
            else:
                ans = 'Статус должен быть True или False!'
        else:
            ans = 'ID должен быть числом!'
        simple_send_message(message.chat.id, ans)
    elif message_tuple[1].isdigit():
        # analytical message
        analytical_message = db_handler.get_analytical_message(int(message_tuple[1]))
        file_name_a = 'temp_analytic.txt'
        with open(file_name_a, 'w', encoding='utf-8') as opened_file:
            opened_file.write(analytical_message)
        tg_bot.send_document(message.chat.id, open(file_name_a, 'rb'))
        # json
        quiz_json = json.dumps(
            db_handler.get_quiz_answers(int(message_tuple[1])), ensure_ascii=False
        )
        file_name_j = 'temp_json.json'
        with open(file_name_j, 'w', encoding='utf-8') as opened_file:
            opened_file.write(quiz_json)
        tg_bot.send_document(message.chat.id, open(file_name_j, 'rb'))
        # xlsx-table
        json_to_write = pandas.read_json(quiz_json)
        file_name_t = 'temp_table.xlsx'
        json_to_write.to_excel(file_name_t)
        tg_bot.send_document(message.chat.id, open(file_name_t, 'rb'))


@tg_bot.message_handler(content_types='text')
@rule_wrapper(('user', 'editor', 'admin', 'm_admin'))
@message_wrapper
def main_message_handler(message: telebot.types.Message):
    """Message handler for all users"""
    if message.text in ('Пройти опрос', 'пройти опрос', 'Ghjqnb jghjc', 'ghjqnb jghjc'):
        available_quiz_list = db_handler.get_quiz_list(visible=True)
        completed_quizzes_id = db_handler.get_completed_quizzes_id(message.from_user.id)
        quizzes_menu = get_available_quiz_inline_markup(available_quiz_list, completed_quizzes_id)
        if quizzes_menu.keyboard:
            text_to_send = 'Вам доступны следующие опросы:'
            menu_to_send = quizzes_menu
        else:
            text_to_send = 'Кажется, для Вас сейчас опросов нет!'
            menu_to_send = get_welcome_markup()

        simple_send_message(
            message.chat.id,
            text_to_send,
            menu_to_send
        )
    elif message.text == 'Изменить ответы в последнем опросе':
        completed_quizzes_id = db_handler.get_completed_quizzes_id(message.from_user.id)
        if completed_quizzes_id:
            last_quiz_id = max(completed_quizzes_id)
            quiz_r_menu = InlineKeyboardMarkup()
            answers = db_handler.get_list_of_questions_in_quiz(last_quiz_id)
            for _ in answers:
                if _.quest_relation:
                    quiz_r_menu.add(
                        InlineKeyboardButton(
                            text=f'Если на вопрос {_.quest_relation.split(" -> ")[0]} ответ'
                                 f' "{_.quest_relation.split(" -> ")[1]}": {_.quest_text}',
                            callback_data=f'quiz_rewrite {_.quiz_id} {_.quest_id}'
                        )
                    )
                else:
                    quiz_r_menu.add(
                        InlineKeyboardButton(
                            text=f'{_.quest_text}',
                            callback_data=f'quiz_rewrite {_.quiz_id} {_.quest_id}'
                        )
                    )
            simple_send_message(
                message.chat.id,
                'Выберите вопрос, ответ на который вы хотели бы изменить\n\nИзменять ответы на'
                ' вопросы, зависящие от других вопросов, нужно в ручном режиме',
                quiz_r_menu
            )
        else:
            simple_send_message(message.chat.id, 'У Вас ещё нет пройденных опросов!')
    elif message.text == 'Настройки рассылки':
        current_mailing_status = db_handler.get_current_mailing_status(message.from_user.id)
        mailing_menu = InlineKeyboardMarkup()
        mailing_menu.add(InlineKeyboardButton(
            'Изменить статус', callback_data=f'mailing {not current_mailing_status}')
        )
        simple_send_message(
            message.chat.id,
            f'Рассылка позволит вам получать уведомления о новых опросах и сообщения от'
            f' администраторов.\n\nТекущий статус:'
            f' {"разрешена" if current_mailing_status else "запрещена"}',
            mailing_menu
        )
    elif message.text == 'Мой статус':
        user = db_handler.get_user_info(message.from_user.id)
        group_dict = {
            'ban': 'забанен',
            'user': 'пользователь',
            'editor': 'редактор',
            'admin': 'администратор',
            'm_admin': 'главный администратор'
        }
        simple_send_message(
            message.chat.id,
            f'ID: {user.tg_user_id}\n'
            f'Внутренний ID: {user.internal_user_id}\n'
            f'Роль: {group_dict[user.group]}\n'
            f'Рассылка: {"включена" if user.mailing else "отключена"}'
        )


@tg_bot.callback_query_handler(func=lambda call: True)
@callback_wrapper
def callback_inline(call: telebot.types.CallbackQuery):
    """Callback-data handler"""

    if call.data == 'list':
        ans = quiz_list_prepare((0, 0))
        simple_send_message(call.message.chat.id, ans, None)
    elif call.data == 'visible_list':
        ans = quiz_list_prepare((0, 0, 0))
        simple_send_message(call.message.chat.id, ans, None)
    elif call.data == 'get_a_project':
        simple_send_message(call.message.chat.id, 'Вы можете связаться с моим создателем через'
                                                  ' его e-mail: vladchesyan@gmail.com\n\n'
                                                  'Некоммерческое использование бесплатно!')
    elif call.data in ('help', 'bug_find'):
        subs_id = call.from_user.id
        subs_name = call.from_user.username
        admins_ids = db_handler.get_users_id('m_admin') + db_handler.get_users_id('admin')
        if call.data == 'bug_find':
            msg_txt = f'Пользователь @{subs_name} с ID {subs_id} нашёл баг!'
        else:
            msg_txt = f'Пользователь @{subs_name} с ID {subs_id} просит о помощи!'
        mailing(admins_ids, msg_txt)
        simple_send_message(call.message.chat.id, 'Передал администраторам. С Вами скоро свяжутся!')
    elif call.data.split()[0] == 'start_quiz':
        db_handler.update_user_quiz_status(call.from_user.id, f'{call.data.split()[1]} 1')
        send_question(call.from_user.id, call.message.chat.id)
    elif call.data.split()[0] == 'quiz_rewrite':
        db_handler.update_user_quiz_status(
            call.from_user.id,
            f'{call.data.split()[1]} {call.data.split()[2]} r'
        )
        send_question(call.from_user.id, call.message.chat.id)
    elif call.data.split()[0] == 'mailing':
        db_handler.update_mailing_status(call.from_user.id, eval(call.data.split()[1]))
        simple_send_message(
            call.message.chat.id,
            'Статус рассылки успешно изменён!',
            get_welcome_markup()
        )


@tg_bot.message_handler(content_types=['document'])
@document_wrapper
@rule_wrapper(('editor', 'admin', 'm_admin'))
def document_handler(message: telebot.types.Message):
    """Document handler (only for add-quiz functions)"""

    file_extension = message.document.file_name.split('.')[-1]

    if file_extension == 'txt':
        file_name = message.document.file_name
        file_id = tg_bot.get_file(message.document.file_id)
        quiz_handler.dir_check()
        answer = quiz_handler.download_new_raw_quiz(tg_bot, file_name, file_id)
        simple_send_message(message.chat.id, answer[0], None)
        if answer[1]:
            answer_msg = quiz_handler.new_quiz_handler(file_name, message.from_user.id)
            simple_send_message(message.chat.id, answer_msg, None)


def main():
    """Main loop"""
    while True:
        # tg_bot.polling(none_stop=True, timeout=1)

        try:
            tg_bot.polling(none_stop=True, timeout=1)

        except Exception as Exc_txt:

            init_logger.error(f'Type: {type(Exc_txt)}, text: {Exc_txt}')
            time.sleep(2)


if __name__ == '__main__':
    main_thread = threading.Thread(target=main)
    unban_thread = threading.Thread(target=auto_unban, daemon=True)
    main_thread.start()
    unban_thread.start()
