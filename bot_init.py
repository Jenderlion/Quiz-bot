import datetime
import logging
import os
import time


# save the absolute path to the script
abs_file_path = os.path.abspath(__file__)
path, filename = os.path.split(abs_file_path)

if 'logs' not in os.listdir():
    os.mkdir('logs')

logging.basicConfig(
    format='%(asctime)s in %(filename)s(%(lineno)d): %(message)s',
    datefmt='%m/%d/%Y %I:%M:%S %p',
    filename='%s/logs/%s.log' % (path, str(datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S'))),
    level=0
)
init_logger = logging.getLogger(filename)
init_logger.debug('Successfully created "%s" logger' % init_logger.name)


def get_bot_api_token():
    if 'api.txt' not in os.listdir(path):
        with open('api.txt', 'w', encoding='utf-8') as opened_file:
            input_api = input('Please, enter API_token from @BotFather!\nAPI_token: ')
            opened_file.write(input_api)
            print('Token successfully writen!')
            init_logger.info('Create api.txt')
            time.sleep(1)
    with open('api.txt', 'r', encoding='utf-8') as opened_file:
        api_token = opened_file.read()
        print('TeleBot is running with the current api.\n'
              'To change the api, please delete the api.txt file')
        init_logger.debug('Got api')

    return api_token
