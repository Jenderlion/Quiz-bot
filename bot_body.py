import logging
import telebot
import time
from bot_init import init_logger
import bot_init


# set new StreamHandler with level DEBUG by default
log_handler = logging.StreamHandler()
log_handler.level = logging.INFO
init_logger.addHandler(log_handler)

tg_bot = telebot.TeleBot(bot_init.get_bot_api_token())


@tg_bot.message_handler(commands=['start'])
def welcome_handler(message):
    print(message)


while True:
    try:
        tg_bot.polling(none_stop=True, timeout=1)

    except Exception as Exc_txt:

        print(type(Exc_txt))
        print(Exc_txt)
        time.sleep(5)
