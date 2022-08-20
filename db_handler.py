import datetime
import os
import time

import sqlalchemy
from sqlalchemy import BOOLEAN
from sqlalchemy import Column
from sqlalchemy import ForeignKey
from sqlalchemy import INTEGER
from sqlalchemy import TEXT
from sqlalchemy import TIMESTAMP
from sqlalchemy import VARCHAR
from sqlalchemy.orm import Session
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import select

import quiz_handler
from bot_init import init_logger
from env_vars import load_vars

# DB info

load_vars()

db_username = os.environ.get('db_username')
db_password = os.environ.get('db_password')
db_host = os.environ.get('db_host')
db_port = os.environ.get('db_port')
db_name = os.environ.get('db_name')
echo_mode = os.environ.get('echo_mode')
is_looped = eval(os.environ.get('is_looped'))

# create DB
engine = sqlalchemy.create_engine(
    f"postgresql+psycopg2://{db_username}:{db_password}@{db_host}:{db_port}/{db_name}",
    echo=eval(echo_mode)
)
meta = sqlalchemy.MetaData()


# create tables
Base = declarative_base()


class User(Base):
    """Create table 'user'"""
    __tablename__ = 'user'
    internal_user_id = Column(INTEGER, primary_key=True)  # only internal user_id
    tg_user_id = Column(INTEGER, unique=True)  # tg id
    quiz_status = Column(VARCHAR(12), nullable=True)  # current quiz id (0 - no current quiz)
    is_ban = Column(BOOLEAN, default=0)  # ban status where 0 - unbanned and 1 - banned
    group = Column(VARCHAR(30), default='user')  # group in (m_admin, admin, editor or user)
    mailing = Column(BOOLEAN, default=1)  # mailing status where 0 - disable and 1 - enable

    def get_short_dict(self):
        return {
            'tg_user_id': self.tg_user_id,
            'quiz_status': self.quiz_status,
            'is_ban': self.is_ban,
            'group': self.group,
            'int_id': self.internal_user_id
        }


class MessageLog(Base):
    """Create table 'message_log'"""
    __tablename__ = 'message_log'
    internal_msg_id = Column(INTEGER, primary_key=True)  # only internal msg_id
    tg_user_id = Column(INTEGER, ForeignKey('user.tg_user_id'))  # tg sender id
    msg_tg_id = Column(INTEGER)  # message id in chat
    msg_text = Column(TEXT)  # text from message
    msg_timestamp = Column(TIMESTAMP)  # seconds since the epoch

    def get_short_dict(self):
        return {
            'tg_user_id': self.tg_user_id,
            'timestamp': self.msg_timestamp,
            'text': self.msg_text,
            'int_id': self.internal_msg_id
        }


class QuizList(Base):
    """Create table 'quiz_list'"""
    __tablename__ = 'quiz_list'
    quiz_id = Column(INTEGER, primary_key=True)  # quiz_id
    quiz_name = Column(VARCHAR(128))  # full quiz name
    quiz_title = Column(TEXT)  # quiz title
    quiz_status = Column(BOOLEAN, default=0)  # current status in 0 - hide, 1 - show
    quiz_gratitude = Column(VARCHAR(512))

    def get_short_dict(self):
        return {
            'quiz_id': self.quiz_id,
            'quiz_name': self.quiz_name,
            'quiz_title': self.quiz_title,
            'quiz_status': self.quiz_status
        }


class QuizQuestions(Base):
    """Create table 'quiz_questions'"""
    __tablename__ = 'quiz_questions'
    quiz_id = Column(INTEGER, ForeignKey('quiz_list.quiz_id'))  # quiz_id
    quest_id = Column(INTEGER)  # quest_id (unique only within the quiz)
    internal_quest_id = Column(INTEGER, primary_key=True)  # fully unique id
    quest_relation = Column(VARCHAR(50), nullable=True)  # This question will only be asked if the
    # correct answer to another question has been received
    quest_text = Column(TEXT)  # question text
    quest_ans = Column(TEXT)  # answer options or marker for self-written input

    def get_short_dict(self):
        return {
            'quiz_id': self.quiz_id,
            'quest_id': self.quest_id,
            'quest_text': self.quest_text,
            'quest_ans': self.quest_ans
        }


class QuestionsAnswers(Base):
    """Create table 'questions_answers'"""
    __tablename__ = 'questions_answers'
    quiz_id = Column(INTEGER, ForeignKey('quiz_list.quiz_id'))  # quiz_id
    quest_id = Column(INTEGER)  # quest_id
    internal_user_id = Column(INTEGER, ForeignKey('user.internal_user_id'))  # internal user id
    answer = Column(TEXT)  # text of user answer
    internal_ans_id = Column(INTEGER, primary_key=True)  # internal unique answer id

    def get_short_dict(self):
        return {
            'quiz_id': self.quiz_id,
            'quest_id': self.quest_id,
            'internal_user_id': self.internal_user_id,
            'answer': self.answer
        }


class Logs(Base):
    """Create table 'logs'"""
    __tablename__ = 'logs'
    event_id = Column(INTEGER, primary_key=True)  # internal event id
    event_msg = Column(TEXT)  # info-message such as "added new user with {params}"
    event_initiator = Column(VARCHAR(20))  # initiator such as {internal_user_id} or 'system'
    event_timestamp = Column(TIMESTAMP)  # seconds since the epoch

    def get_short_dict(self):
        return {
            'event_id': self.event_id,
            'event_msg': self.event_msg,
            'event_initiator': self.event_initiator
        }


class BanList(Base):
    """Create table 'ban_list'"""
    __tablename__ = 'ban_list'
    internal_ban_id = Column(INTEGER, primary_key=True)  # internal ban id
    initiator_tg_id = Column(INTEGER, ForeignKey('user.tg_user_id'))  # user-initiator id
    tg_id = Column(INTEGER, ForeignKey('user.tg_user_id'))  # tg user id
    reason = Column(VARCHAR(128))  # ban reason
    ban_time = Column(TIMESTAMP)  # ban time in seconds since the epoch
    unban_time = Column(TIMESTAMP)  # unban time in seconds since the epoch
    current_status = Column(BOOLEAN, default=True)

    def get_short_dict(self):
        return {
            'internal_user_id': self.internal_user_id,
            'tg_user_id': self.tg_user_id,
            'reason': self.reason,
            'ban_time': self.ban_time,
            'unban_time': self.ban_time
        }


Base.metadata.create_all(engine)


# service functions
def get_normal_date_from_timestamp(raw_date):
    """Convert timestamp into datetime.datetime

    :param raw_date: timestamp like 1653983835
    :return: instance of datetime.datetime
    """
    normal_date = datetime.datetime.fromtimestamp(raw_date)
    return normal_date


def convert_to_timedelta(term: str) -> datetime.timedelta:
    """Convert string with term to datetime.datetime-object

    Term should be in patter [num][unit] like 5m or 7d (use bot_body.check_term())

    :param term: string in pattern [num][unit]
    :return: datetime.datetime-object
    """
    term_unit = term[-1]
    term_numeric = int(term[:-1])
    if term_unit == 's':
        time_delta = datetime.timedelta(seconds=term_numeric)
    elif term_unit == 'm':
        time_delta = datetime.timedelta(minutes=term_numeric)
    elif term_unit == 'h':
        time_delta = datetime.timedelta(hours=term_numeric)
    else:
        time_delta = datetime.timedelta(days=term_numeric)

    return time_delta


def dict_analytic(input_dict: dict, questions_info: list[QuizQuestions]):
    """Prepare analytical message"""
    general_answers_seq = []
    for answers_dict in input_dict.values():
        answer_seq = []
        for answer in answers_dict.values():
            answer_seq.append(answer)
        while len(answer_seq) < len(questions_info):
            answer_seq.append(None)
        general_answers_seq.append(answer_seq)
    analytical_list = seq_analytic(general_answers_seq)
    info_analytical_list = []
    for index in range(len(analytical_list)):
        info_string = f'{questions_info[index].quest_text}\nСамый популярный ответ' \
                      f' ({analytical_list[index][1]}%): {analytical_list[index][0]}'
        info_analytical_list.append(info_string)
    return '\n'.join(info_analytical_list)


def seq_analytic(input_seq: list[list], output_seq: list or None = None) -> list:
    """Recursive sequence traversal"""
    if output_seq is None:
        output_seq = list()
    temp_dict = dict()
    second_seq = list()
    for user_answers in input_seq:
        if user_answers[0] not in temp_dict:
            temp_dict[user_answers[0]] = 1
        else:
            temp_dict[user_answers[0]] += 1

    frequent_answer = max(temp_dict, key=temp_dict.get)
    output_seq.append((frequent_answer,
                       round(temp_dict[frequent_answer] / len(input_seq) * 100, 2)))

    for user_answers in input_seq:
        if len(user_answers) > 0 and user_answers[0] == frequent_answer:
            second_seq.append(user_answers[1:])

    if len(second_seq[0]) > 0:
        seq = seq_analytic(second_seq, output_seq)
    else:
        seq = output_seq

    return seq


# requests
# get-requests
def get_last_timestamp(tg_id) -> datetime.datetime:
    """Return time of last message

    Can't use with REALLY new user!

    :param tg_id: telegram user id
    :return: time of last message
    """
    with Session(engine) as timestamp_session:
        statement = (select(MessageLog.msg_timestamp).where(MessageLog.tg_user_id == tg_id))
        res = timestamp_session.scalars(statement).all()
        return res[-1]


def get_user_info(tg_id) -> User:
    """Return db_handler.User"""
    with Session(engine) as user_info_session:
        statement = (select(User).where(User.tg_user_id == tg_id))
        res_instance = user_info_session.scalars(statement).all()[0]
        return res_instance


def get_last_quiz_id(_quiz_name: str) -> int:
    """Returns last id from 'quiz_list' whit _quiz_name

    :param _quiz_name: quiz name to search
    :return: None
    """
    with Session(engine) as quiz_id_session:
        statement = (select(QuizList.quiz_id).where(QuizList.quiz_name == _quiz_name))
        res_instance = quiz_id_session.scalars(statement).all()[-1]
        return res_instance


def get_quiz_list(visible: bool = False) -> list:
    """Prepares a list containing tuples with information about polls

    [[quiz_name, quiz_id, quiz_status], ...]

    :param visible: visible status, bool
    :return: list with last 10 tuples
    """
    with Session(engine) as quiz_list_session:
        if visible:
            statement = (
                select(QuizList).where(QuizList.quiz_status == True)
            )
        else:
            statement = (
                select(QuizList)
            )
        result_list = [(_.quiz_name, _.quiz_id, _.quiz_status)
                       for _ in quiz_list_session.scalars(statement).all()]

        return result_list[-10:]


def get_quiz_status(tg_id: int) -> str or None:
    """Return user quiz status"""
    with Session(engine) as user_quiz_status_session:
        statement = select(User.quiz_status).where(User.tg_user_id == tg_id)
        result = user_quiz_status_session.scalars(statement).first()
        return result


def get_list_of_questions_in_quiz(quiz_id) -> list[QuizQuestions]:
    """Return list with questions (db_handler.QuizQuestions)"""
    with Session(engine) as list_of_questions_session:
        statement = select(QuizQuestions).where(QuizQuestions.quiz_id == quiz_id)
        result_list = list_of_questions_session.scalars(statement).all()
        return result_list


def get_end_message(quiz_id) -> str:
    """Return and-message of quiz"""
    with Session(engine) as quiz_end_message_session:
        statement = select(QuizList.quiz_gratitude).where(QuizList.quiz_id == quiz_id)
        result = quiz_end_message_session.scalars(statement).all()[0]
        return result


def get_completed_quizzes_id(tg_id) -> set[int]:
    """Return a set with completed user quizzes"""
    user = get_user_info(tg_id)
    with Session(engine) as completed_quizzes_id_session:
        statement = select(QuestionsAnswers.quiz_id).\
            where(QuestionsAnswers.internal_user_id == user.internal_user_id)
        result = set(completed_quizzes_id_session.scalars(statement).all())
        return result


def get_current_mailing_status(tg_id) -> bool:
    """Return user mailing status"""
    with Session(engine) as current_mailing_status_session:
        statement = select(User.mailing).where(User.tg_user_id == tg_id)
        result = current_mailing_status_session.scalars(statement).all()[0]
        return result


def get_active_ban_list() -> list[BanList]:
    """Return list with db_handler.BanList-objects"""
    with Session(engine) as ban_list_session:
        statement = select(BanList).where(BanList.current_status == True)
        result = ban_list_session.scalars(statement).all()
        return result


def get_answers(quiz_id, quest_id) -> list[QuestionsAnswers]:
    """Return list with answers text

    Contains ONLY the text of the answers!!!

    :param quiz_id: target quiz id
    :param quest_id: target quest id
    :return: list with answers text
    """
    with Session(engine) as answers_session:
        statement = select(QuestionsAnswers).where(
            QuestionsAnswers.quiz_id == quiz_id,
            QuestionsAnswers.quest_id == quest_id
        )
        result = answers_session.scalars(statement).all()
        return result


def get_users_id(group: str, mailing: bool = False) -> tuple:
    """Generates a tuple with user ids for subsequent distribution

    Recommend using mailing restrictions only for the 'user' group
    :param group: target group of users
    :param mailing: whether users with disabled mailing will be added to the tuple
    :return: tuple with ids
    """
    with Session(engine) as users_id_session:
        if mailing:
            statement = select(User.tg_user_id).where(
                User.group == group,
                User.quiz_status == None,
                User.mailing == True
            )
        else:
            statement = select(User.tg_user_id).where(
                User.group == group,
                User.quiz_status == None
            )
        result_list = users_id_session.scalars(statement).all()
        return tuple(result_list)


def get_quiz_answers(quiz_id):
    """Prepares a dictionary with quiz answers

    It should be in pattern {question_1_text: {answer_1_text: count, ...}, ...}
    """
    with Session(engine) as quiz_answers_session:
        statement = select(QuestionsAnswers.quest_id).where(QuestionsAnswers.quiz_id == quiz_id)
        quests_id = frozenset(quiz_answers_session.scalars(statement).all())
    questions_info: list[QuizQuestions] = get_list_of_questions_in_quiz(quiz_id)
    info_dict = dict()
    for quest_id in quests_id:
        try:
            if questions_info[quest_id - 1].quest_text not in info_dict.keys():
                info_dict[questions_info[quest_id - 1].quest_text] = dict()
            answers = get_answers(quiz_id, quest_id)
            answers_text = [i.answer for i in answers]
            for answer in answers_text:
                if answer not in info_dict[questions_info[quest_id - 1].quest_text]:
                    info_dict[questions_info[quest_id - 1].quest_text][answer] = 0
                info_dict[questions_info[quest_id - 1].quest_text][answer] += 1
        except IndexError:
            pass

    return info_dict


def get_analytical_message(quiz_id):
    with Session(engine) as quiz_answers_session:
        statement = select(QuestionsAnswers.quest_id).where(QuestionsAnswers.quiz_id == quiz_id)
        quests_id = frozenset(quiz_answers_session.scalars(statement).all())
    questions_info: list[QuizQuestions] = get_list_of_questions_in_quiz(quiz_id)
    analytical_dict = dict()

    for quest_id in quests_id:
        try:
            answers = get_answers(quiz_id, quest_id)
            for answer in answers:
                if answer.internal_user_id not in analytical_dict:
                    analytical_dict[answer.internal_user_id] = dict()
                analytical_dict[answer.internal_user_id][answer.quest_id] = answer.answer
        except IndexError:
            pass
    return dict_analytic(analytical_dict, questions_info)


# add-requests
def add_message_in_log(tg_id, msg_id, msg_txt, msg_t_stamp):
    """Insert message with message-info to table 'message_log'"""
    with Session(engine) as msg_log_session:
        normal_date = get_normal_date_from_timestamp(msg_t_stamp)
        new_message = MessageLog(
            tg_user_id=tg_id,
            msg_tg_id=msg_id,
            msg_text='%s' % msg_txt,
            msg_timestamp=normal_date
        )
        msg_log_session.add(new_message)
        msg_log_session.commit()
        init_logger.info('Message "%s" from user with id: %s' % (msg_txt, tg_id))


def add_event_in_log(
        event_msg: str,
        event_initiator: str or int,
        event_timestamp: datetime.datetime,
        session: Session,
        logger_msg: str
):
    """Adds an event to the "logs" table

    :param event_msg: the message to be written to the "logs".even_msg, str
    :param event_initiator: "logs".event_initiator, str
    :param event_timestamp: "logs".event_timestamp, datetime.datetime
    :param session: current session
    :param logger_msg: message for logging in logs/
    :return: None
    """
    new_event = Logs(
        event_msg=event_msg,
        event_initiator=event_initiator,
        event_timestamp=event_timestamp
    )
    session.add(new_event)
    init_logger.info(logger_msg)


def add_user(tg_id, msg_id, msg_txt, msg_t_stamp):
    """Checks and optionally adds a new user to table 'user'"""
    with Session(engine) as session:

        statement = (select(User.tg_user_id).where(User.tg_user_id == tg_id))
        res = session.scalars(statement).all()
        if tg_id not in res:
            new_user = User(tg_user_id=tg_id)
            session.add(new_user)
            add_event_in_log(
                event_msg=f'New user: {tg_id}',
                event_initiator='system',
                event_timestamp=get_normal_date_from_timestamp(msg_t_stamp),
                session=session,
                logger_msg='Added new user with id %s' % tg_id
            )
            session.commit()

        # Decorator cannot be used because the user must be added first
        add_message_in_log(tg_id, msg_id, msg_txt, msg_t_stamp)


def add_new_quiz(input_instance: quiz_handler.PreparedQuiz, tg_id: int) -> str:
    """Insert new quiz into the 'quiz_list' table and questions into the 'quiz_questions' table

    !!!Keep in mind that input_instance can be only quiz_handler.PreparedQuiz!!!

    :param input_instance: quiz instance, quiz_handler.PreparedQuiz
    :param tg_id: initiator id, int
    :return: info-message
    """
    try:
        with Session(engine) as add_quiz_session:

            new_quiz = QuizList(
                quiz_name=input_instance.name,
                quiz_title=input_instance.title,
                quiz_gratitude=input_instance.gratitude
            )
            add_quiz_session.add(new_quiz)
            add_quiz_session.flush()
            quiz_id = new_quiz.quiz_id
            add_event_in_log(
                'Added new quiz %s' % input_instance.name,
                tg_id,
                datetime.datetime.now(),
                add_quiz_session,
                'New quiz with name %s from user %s' % (input_instance.name, tg_id)
            )
            add_quiz_session.commit()
    except KeyboardInterrupt:
        exit('Interrupted')
    except Exception as exc:
        init_logger.error('Exception: %s\n%s' % (type(exc), exc))
        return 'Не получилось добавить опрос %s' % input_instance.name

    try:
        with Session(engine) as add_questions_session:
            for question in input_instance.questions:
                new_question = QuizQuestions(
                    quiz_id=quiz_id,
                    quest_id=question.text.split('.')[0],
                    quest_relation=question.relation,
                    quest_text=question.text[question.text.index(' '):].strip(),
                    quest_ans=' || '.join(question.answers)
                )
                add_questions_session.add(new_question)
            add_event_in_log(
                'Added questions for quiz %s' % input_instance.name,
                tg_id,
                datetime.datetime.now(),
                add_questions_session,
                'Questions for quiz %s from user %s' % (input_instance.name, tg_id)
            )
            add_questions_session.commit()
    except KeyboardInterrupt:
        exit('Interrupted')
    except Exception as exc:
        init_logger.error('Exception: %s\n%s' % (type(exc), exc))
        msg = 'Не получилось добавить вопросы к опросу "%s", id %s' % (input_instance.name, quiz_id)
        return msg

    return 'Успешно добавлен опрос "%s" с id "%s"' % (input_instance.name, quiz_id)


def add_new_answer(tg_id: int, quiz_id: int, quest_id: int, answer_text: str):
    """Insert new answer in db

    Don't use that for rewrite answer!!!

    :param tg_id: user id
    :param quiz_id: quiz id
    :param quest_id: quest id
    :param answer_text: answer text
    :return:
    """
    user = get_user_info(tg_id)
    with Session(engine) as answer_session:
        new_answer = QuestionsAnswers(
            quiz_id=quiz_id,
            quest_id=quest_id,
            internal_user_id=user.internal_user_id,
            answer=answer_text
        )
        answer_session.add(new_answer)
        add_event_in_log(
            msg := 'Answer from user %s for quiz %s, question %s: %s' %
                   (tg_id, quiz_id, quest_id, answer_text),
            tg_id,
            datetime.datetime.now(),
            answer_session,
            msg
        )
        answer_session.flush()
        time.sleep(0.1)
        answer_session.commit()


# ban & unban
def ban_user(initiator_tg_id, target_tg_id, reason, term):
    """Ban user"""
    time_delta = convert_to_timedelta(term)

    ban_time = datetime.datetime.now()
    unban_time = ban_time + time_delta

    with Session(engine) as ban_user_session:
        new_ban = BanList(
            initiator_tg_id=initiator_tg_id,
            tg_id=target_tg_id,
            reason=reason,
            ban_time=ban_time,
            unban_time=unban_time
        )
        ban_user_session.add(new_ban)
        ban_user_session.query(User).filter(User.tg_user_id == target_tg_id).\
            update({'is_ban': True, 'group': 'user'})
        initiator_tg_id = initiator_tg_id if initiator_tg_id != 0 else 'system'
        add_event_in_log(
            'Ban user with tg_id %s for %s' % (target_tg_id, term),
            initiator_tg_id,
            datetime.datetime.now(),
            ban_user_session,
            'Ban %s for %s by %s with reason %s' % (target_tg_id, term, initiator_tg_id, reason)
        )
        ban_user_session.commit()


def unban_user(initiator_tg_id, target_tg_id, reason=None):
    """Unban user"""
    if reason is None:
        if initiator_tg_id == 0:
            reason = 'time has come'
        else:
            reason = 'mercy'

    with Session(engine) as unban_user_session:
        unban_user_session.query(User).filter(User.tg_user_id == target_tg_id).\
            update({'is_ban': False})
        unban_user_session.query(BanList).filter(BanList.tg_id == target_tg_id).\
            update({'current_status': False})
        initiator_tg_id = initiator_tg_id if initiator_tg_id != 0 else 'system'
        add_event_in_log(
            msg := 'Unban user with tg_id %s with reason "%s"' % (target_tg_id, reason),
            initiator_tg_id,
            datetime.datetime.now(),
            unban_user_session,
            msg
        )
        unban_user_session.commit()


# update-requests
def rewrite_answer(tg_id: int, quiz_id: int, quest_id: int, answer_text: str):
    """Update answer in db

    Don't use that for insert answer!!!

    :param tg_id: user id
    :param quiz_id: quiz id
    :param quest_id: quest id
    :param answer_text: new answer text
    :return: None
    """
    user = get_user_info(tg_id)
    try:
        with Session(engine) as user_answer_update_session:
            user_answer_update_session.query(QuestionsAnswers).filter(
                QuestionsAnswers.quiz_id == quiz_id,
                QuestionsAnswers.quest_id == quest_id,
                QuestionsAnswers.internal_user_id == user.internal_user_id
            ).\
                update({'answer': answer_text})
            add_event_in_log(
                msg := 'Rewrite answer from user %s for quiz %s, question %s' % (
                    tg_id, quiz_id, quest_id
                ),
                tg_id,
                datetime.datetime.now(),
                user_answer_update_session,
                msg
            )
            user_answer_update_session.commit()
        update_user_quiz_status(tg_id, None)
        return True
    except KeyboardInterrupt:
        exit('Interrupted')
    except Exception as exc:
        init_logger.error('Exception: %s\n%s' % (type(exc), exc))
        return False


def update_user_quiz_status(tg_id: int, new_status: str or None):
    """Update user quiz status in pattern like [quiz id] [quest id] or None"""
    with Session(engine) as user_quiz_status_update_session:
        user_quiz_status_update_session.query(User).filter(
            User.tg_user_id == tg_id
        ).\
            update({'quiz_status': new_status})
        add_event_in_log(
            'Update status for user %s' % tg_id,
            tg_id,
            datetime.datetime.now(),
            user_quiz_status_update_session,
            'Status "%s" for user with tg_id: %s' % (new_status, tg_id)
        )
        user_quiz_status_update_session.commit()


def update_quiz_status(quiz_id, tg_id, new_status):
    """Updates visibility status of quiz"""
    with Session(engine) as quiz_status_session:
        quiz_status_session.query(QuizList).filter(QuizList.quiz_id == quiz_id).\
            update({'quiz_status': eval(new_status)})
        add_event_in_log(
            'New status %s for quiz with ID: %s' % (new_status, quiz_id),
            tg_id,
            datetime.datetime.now(),
            quiz_status_session,
            'Update status for quiz %s from user %s: %s' % (quiz_id, tg_id, new_status)
        )
        quiz_status_session.commit()

    return 'Новый статус "%s" для опроса с ID "%s" успешно установлен!' % (new_status, quiz_id)


def update_mailing_status(tg_id: int, new_status: bool):
    """Updates mailing status of user"""
    with Session(engine) as update_mailing_status_session:
        update_mailing_status_session.query(User).filter(User.tg_user_id == tg_id).\
            update({'mailing': new_status})
        add_event_in_log(
            'New mailing status %s for user %s' % (new_status, tg_id),
            tg_id,
            datetime.datetime.now(),
            update_mailing_status_session,
            'Update mailing status "%s" for user %s' % (new_status, tg_id)
        )
        update_mailing_status_session.commit()


def update_user_group(initiator_tg_id, target_tg_id, new_group):
    """Updates group of user"""
    with Session(engine) as update_group_session:
        update_group_session.query(User).filter(User.tg_user_id == target_tg_id).\
            update({'group': new_group})
        add_event_in_log(
            'New group %s for user %s' % (new_group, target_tg_id),
            initiator_tg_id,
            datetime.datetime.now(),
            update_group_session,
            'Update group "%s" for user %s from %s' % (new_group, target_tg_id, initiator_tg_id)
        )
        update_group_session.commit()


# check-requests
def check_quest_relation(tg_id, quiz_id, check_quest_id, check_value) -> bool:
    """If check_value matches the writen earlier return True, another - False"""
    user = get_user_info(tg_id)
    with Session(engine) as check_relation_session:
        statement = select(QuestionsAnswers.answer).where(
            QuestionsAnswers.quiz_id == quiz_id,
            QuestionsAnswers.quest_id == check_quest_id,
            QuestionsAnswers.internal_user_id == user.internal_user_id
        )
        result_value = check_relation_session.scalars(statement).all()[0]
        return result_value == check_value
