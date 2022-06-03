import db_handler
from bot_init import path
import os


class PreparedQuiz:
    """Simple class to describe the quiz

    Call this with (quiz name, title, list/tuple of questions, gratitude)
    """

    def __init__(self, name: str, title: str, questions: list or tuple, gratitude: str):
        self.name = name
        self.title = title
        self.questions = questions
        self.gratitude = gratitude


class Question:
    """Class to describe each question

    Call this with (question text, answers, relation)

    Keep in mind patterns of relation: QUESTION_NUM -> DESIRED_ANSWER like '2 -> Yes'
    """

    def __init__(self, text: str, answers: list or tuple, relation: str):
        self.text = text
        self.answers = answers
        self.relation = relation


def dir_check():
    """checks for the existence of a "raw_quizzes" directory and, if necessary, creates it"""
    if 'raw_quizzes' not in os.listdir(path):
        os.mkdir('raw_quizzes')


def download_new_raw_quiz(bot, file_name, file_id):
    """Downloads the file if it doesn't already exist and returns a tuple with a message and status

    :param bot: current bot, telebot.TeleBot
    :param file_name: filename, str
    :param file_id: file id, int
    :return: (message, status) where status - bool
    """
    if file_name not in os.listdir(f'{path}\\raw_quizzes'):

        with open(f'raw_quizzes/{file_name}', 'w', encoding='utf-8', errors='ignore') \
                as new_raw_quiz:
            file_for_download = bot.download_file(file_id.file_path)
            text_to_write = file_for_download.decode()
            text_to_write = text_to_write.replace('\r', '')
            new_raw_quiz.write(text_to_write)
            return 'Первичный файл успешно загружен! Начинаем обработку!', True

    else:
        return 'Пожалуйста, переименуйте файл!', False


def new_quiz_handler(file_name, tg_id):
    """Simple handler for adding a quiz"""

    with open(f'raw_quizzes/{file_name}', 'r', encoding='utf-8') as opened_file:
        file_content = [i[:-1] for i in opened_file.readlines()]
    questions = get_questions_list(file_content[2:-1])
    new_quiz = PreparedQuiz(file_content[0], file_content[1], questions, file_content[-1])
    info_message = db_handler.add_new_quiz(new_quiz, tg_id)
    return info_message


def get_questions_list(input_list: list or tuple) -> list:
    """Prepares data for insert into table

    :param input_list: raw list or tuple with quest-info
    :return: list containing instances of quiz_handler.Questions
    """
    return_list = []
    for question_string in input_list:
        question, answers = question_string.split('//\\\\')
        answers = answers.split('/\\')
        relation = None
        if question.startswith('[{'):
            char_num = question.index(']') + 1
            relation = question[:char_num][2:-2]
            question = question[char_num:]
        return_list.append(Question(question, answers, relation))

    return return_list
