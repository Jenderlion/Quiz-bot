"""
Create vars.env and writes to it.
"""


from bot_init import path
import os
import dotenv


def load_vars():
    if 'vars.env' not in os.listdir(path):
        # create vars.env
        with open('vars.env', 'w') as opened_file:
            for var in ('db_username', 'db_password', 'db_host', 'db_port', 'db_name', 'echo_mode'):
                new_var = input(f'Enter {var}: ')
                opened_file.write(f'{var} = {new_var}\n')
    # load vars.env
    dotenv.load_dotenv(f'{path}/vars.env')
