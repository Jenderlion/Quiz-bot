import logging


init_logger = logging.getLogger('Bot_init_logger')
print(init_logger)


def main():
    init_logger.warning('Hello World!')


if __name__ == '__main__':
    main()
