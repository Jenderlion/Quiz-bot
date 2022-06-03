import os

import db_handler
import quiz_handler
import datetime
import logging
import telebot
from telebot.types import ReplyKeyboardMarkup
from telebot.types import InlineKeyboardMarkup
from telebot.types import InlineKeyboardButton
import time
from bot_init import init_logger
import bot_init
import functools


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
        last_message_time = db_handler.get_last_timestamp(message.from_user.id)
        current_message_date = datetime.datetime.fromtimestamp(float(message.date))
        db_handler.add_message_in_log(message.from_user.id, message.text, float(message.date))
        time_delta = (current_message_date - last_message_time).seconds
        if time_delta >= min_time_delta:  # change in bot settings
            func(message)
        else:
            simple_send_message(message.chat.id, 'Вы отправляете сообщения слишком часто!', None)

    return wrapper


def document_wrapper(func):
    """Decorator that writes doc-info messages to logs"""

    def wrapper(*args):
        message: telebot.types.Message = args[0]
        last_message_time = db_handler.get_last_timestamp(message.from_user.id)
        current_message_date = datetime.datetime.fromtimestamp(float(message.date))
        db_handler.add_message_in_log(
            message.from_user.id,
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
        last_message_time = db_handler.get_last_timestamp(call.from_user.id)
        current_message_date = datetime.datetime.now()
        db_handler.add_message_in_log(
            call.from_user.id,
            f'In-Line: {call.data}',
            current_message_date.timestamp()
        )
        print(current_message_date)
        print(last_message_time)
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
    """A decorator that enables (for editor+) or disables (for user) the execution of function

    This decorator checks the availability of USER GROUP by the RULES passed and, if everything is
    OK, allows the function to be executed, otherwise it does nothing
    """

    def decorator(func):

        def wrapper(*args):
            message: telebot.types.Message = args[0]
            user = db_handler.get_user_info(message.from_user.id)
            if user.group in rules:
                func(message)

        return wrapper

    return decorator


# general functions
def simple_send_message(chat_id, message_text, markup):
    """Simple send-message function"""
    tg_bot.send_message(chat_id, message_text, reply_markup=markup)
    init_logger.info('Message %s to user %s' % (message_text, chat_id))


@functools.cache
def get_welcome_markup():
    """Create welcome greet menu"""

    greet_menu = ReplyKeyboardMarkup(resize_keyboard=True)
    greet_menu.row('Пройти опрос')
    greet_menu.row('Настройки рассылки')
    greet_menu.row('Мой статус')
    greet_menu.row('Check')

    return greet_menu


@functools.cache
def get_editor_inline_markup():
    """Create editor inline menu"""

    editor_menu = InlineKeyboardMarkup(row_width=1)
    editor_menu.add(
        InlineKeyboardButton(text='Получить список всех опросов', callback_data=f'list'))
    editor_menu.add(
        InlineKeyboardButton(text='Получить список видимых опросов', callback_data=f'visible_list'))

    return editor_menu


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

    print(proc_quiz_l)

    return '\n'.join(proc_quiz_l)


# message handlers
@tg_bot.message_handler(commands=['start'])
# Decorator cannot be used because the user must be added first
def welcome_handler(message: telebot.types.Message):
    """Simple welcome-message handler

    Adds a new user if it doesn't already exist
    """
    db_handler.add_user(message.from_user.id, message.text, float(message.date))
    simple_send_message(message.chat.id, 'Привет!', get_welcome_markup())


@tg_bot.message_handler(commands=['quiz', 'editor'])
@rule_wrapper(('editor', 'admin', 'm_admin'))
@message_wrapper
def editor_handler(message: telebot.types.Message):
    """Editor-message handler

    Send help-message with in-line menu
    """
    message_tuple = tuple(message.text.split())
    if len(message_tuple) == 1:
        simple_send_message(message.chat.id, 'editor-menu', get_editor_inline_markup())
    elif message_tuple[1] in ('list', ):
        ans = quiz_list_prepare(message_tuple)
        simple_send_message(message.chat.id, ans, get_editor_inline_markup())
    elif message_tuple[1] in ('vis', ):
        if message_tuple[2].isdigit():
            if message_tuple[3] in ('True', 'False'):
                ans = db_handler.update_quiz_status(message_tuple[2], message.chat.id, message_tuple[3])
            else:
                ans = 'Статус должен быть True или False!'
        else:
            ans = 'ID должен быть числом!'
        simple_send_message(message.chat.id, ans, get_editor_inline_markup())


@tg_bot.message_handler(content_types='text')
@message_wrapper
def main_message_handler(message: telebot.types.Message):
    """Message handler for all users"""
    if message.text in ('Пройти опрос', 'пройти опрос', 'Ghjqnb jghjc', 'ghjqnb jghjc'):
        user = db_handler.get_user_info(message.from_user.id)
        print(user.group)
    elif message.text == 'Настройки рассылки':
        pass
    elif message.text == 'Мой статус':
        pass
    elif message.text == 'Check':
        msg = quiz_handler.new_quiz_handler('quiz_example.txt', message.from_user.id)
        simple_send_message(message.chat.id, msg, None)


@tg_bot.callback_query_handler(func=lambda call: True)
@callback_wrapper
def callback_inline(call: telebot.types.CallbackQuery):

    if call.data == 'list':
        ans = quiz_list_prepare((0, 0))
        simple_send_message(call.message.chat.id, ans, None)
    elif call.data == 'visible_list':
        ans = quiz_list_prepare((0, 0, 0))
        simple_send_message(call.message.chat.id, ans, None)


@tg_bot.message_handler(content_types=['document'])
@document_wrapper
@rule_wrapper(('editor', 'admin', 'm_admin'))
def document_handler(message: telebot.types.Message):

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


# endless cycle
while True:

    tg_bot.polling(none_stop=True, timeout=1)

    # try:
    #     tg_bot.polling(none_stop=True, timeout=1)
    #
    # except Exception as Exc_txt:
    #
    #     init_logger.error(f'Type: {type(Exc_txt)}, text: {Exc_txt}')
    #     time.sleep(5)
