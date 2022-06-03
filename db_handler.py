import quiz_handler
from env_vars import load_vars
import datetime
import os
import sqlalchemy
from bot_init import init_logger
from sqlalchemy import VARCHAR
from sqlalchemy import BOOLEAN
from sqlalchemy import Column
from sqlalchemy import INTEGER
from sqlalchemy import ForeignKey
from sqlalchemy import TEXT
from sqlalchemy import TIMESTAMP
from sqlalchemy.orm import Session
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import and_
from sqlalchemy.sql import select
from sqlalchemy.sql import update


# DB info

load_vars()

db_username = os.environ.get('db_username')
db_password = os.environ.get('db_password')
db_host = os.environ.get('db_host')
db_port = os.environ.get('db_port')
db_name = os.environ.get('db_name')
echo_mode = os.environ.get('echo_mode')

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
    quiz_status = Column(INTEGER, default=0)  # current quiz id (0 - no current quiz)
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
    event_msg = Column(VARCHAR(64))  # info-message such as "added new user with {params}"
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
    internal_user_id = Column(INTEGER, ForeignKey('user.internal_user_id'))  # internal user id
    tg_user_id = Column(INTEGER, ForeignKey('user.tg_user_id'))  # tg user id
    reason = Column(VARCHAR(128))  # ban reason
    ban_time = Column(TIMESTAMP)  # ban time in seconds since the epoch
    unban_time = Column(TIMESTAMP)  # unban time in seconds since the epoch

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


# requests
def get_last_timestamp(tg_id):
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
    with Session(engine) as user_info_session:
        statement = (select(User).where(User.tg_user_id == tg_id))
        res_instance = user_info_session.scalars(statement).all()[0]
        return res_instance


def add_message_in_log(tg_id, msg_txt, msg_t_stamp):
    """Insert message with message-info to table 'message_log'"""
    with Session(engine) as msg_log_session:
        normal_date = get_normal_date_from_timestamp(msg_t_stamp)
        new_message = MessageLog(
            tg_user_id=tg_id,
            msg_text='%s' % msg_txt,
            msg_timestamp=normal_date
        )
        msg_log_session.add(new_message)
        msg_log_session.commit()
        init_logger.info('Message %s from user_id %s' % (msg_txt, tg_id))


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


def add_user(tg_id, msg_txt, msg_t_stamp):
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
        add_message_in_log(tg_id, msg_txt, msg_t_stamp)


def get_last_quiz_id(_quiz_name: str) -> int:
    """Returns last id from 'quiz_list' whit _quiz_name

    :param _quiz_name: quiz name to search
    :return: None
    """
    with Session(engine) as quiz_id_session:
        statement = (select(QuizList.quiz_id).where(QuizList.quiz_name == _quiz_name))
        res_instance = quiz_id_session.scalars(statement).all()[-1]
        return res_instance


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
    except Exception as exc:
        init_logger.error('Exception: %s\n%s' % (type(exc), exc))
        msg = 'Не получилось добавить вопросы к опросу "%s", id %s' % (input_instance.name, quiz_id)
        return msg

    return 'Успешно добавлен опрос "%s" с id "%s"' % (input_instance.name, quiz_id)


def get_quiz_list(visible: bool = False):
    """Prepares a list containing tuples with information about polls

    :param visible: visible status, bool
    :return: list with last 10 tuples
    """
    with Session(engine) as quiz_list_session:
        if visible:
            statement = (
                select(QuizList).where(QuizList.quiz_status is True)
            )
        else:
            statement = (
                select(QuizList)
            )
        result_list = [(i.quiz_name, i.quiz_id, i.quiz_status) for i in quiz_list_session.scalars(statement).all()]

        return result_list[-10:]


def update_quiz_status(quiz_id, tg_id, new_status):
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
