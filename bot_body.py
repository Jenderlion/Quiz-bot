import DB_handler
import datetime
import logging
import telebot
from telebot.types import ReplyKeyboardMarkup
import time
from bot_init import init_logger
import bot_init


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
        last_message_time = DB_handler.get_last_timestamp(message.from_user.id)
        current_message_date = datetime.datetime.fromtimestamp(float(message.date))
        DB_handler.add_message_in_log(message.from_user.id, message.text, float(message.date))
        time_delta = (current_message_date - last_message_time).seconds
        if time_delta >= min_time_delta:  # change in bot settings
            func(message)
        else:
            simple_send_message(message.chat.id, 'Вы отправляете сообщения слишком часто!', None)

    return wrapper


# general functions
def simple_send_message(chat_id, message_text, markup):
    tg_bot.send_message(chat_id, message_text, reply_markup=markup)
    init_logger.info('Message %s to user %s' % (message_text, chat_id))


def get_welcome_markup():
    greet_menu = ReplyKeyboardMarkup(resize_keyboard=True)
    greet_menu.row('Пройти опрос')
    greet_menu.row('Настройки рассылки')
    greet_menu.row('Мой статус')
    return greet_menu


# message handlers
@tg_bot.message_handler(commands=['start'])
# Decorator cannot be used because the user must be added first
def welcome_handler(message: telebot.types.Message):
    """Simple welcome-message handler

    Adds a new user if it doesn't already exist
    """
    DB_handler.add_user(message.from_user.id, message.text, float(message.date))
    simple_send_message(message.chat.id, 'Привет!', get_welcome_markup())


@tg_bot.message_handler(content_types='text')
@message_wrapper
def main_message_handler(message: telebot.types.Message):
    if message.text in ('Пройти опрос', 'пройти опрос', 'Ghjqnb jghjc', 'ghjqnb jghjc'):
        pass
    elif message.text == 'Настройки рассылки':
        pass
    elif message.text == 'Мой статус':
        pass


while True:
    try:
        tg_bot.polling(none_stop=True, timeout=1)

    except Exception as Exc_txt:

        init_logger.error(f'Type: {type(Exc_txt)}, text: {Exc_txt}')
        time.sleep(5)
