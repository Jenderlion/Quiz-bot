"""
Create vars.env and writes to it.
"""


import os

import dotenv

from bot_init import path


def load_vars():
    if 'vars.env' not in os.listdir(path):
        # create vars.env
        with open('vars.env', 'w') as opened_file:
            print('Now, please, type environment vars. Vars "echo_mode" and "is_looped" should be "True" or "False".')
            for var in ('db_username', 'db_password', 'db_host', 'db_port', 'db_name', 'echo_mode', 'is_looped'):
                new_var = input(f'Enter {var}: ')
                opened_file.write(f'{var} = {new_var}\n')
    # load vars.env
    dotenv.load_dotenv(f'{path}/vars.env')
