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


# DB info

load_vars()

db_username = os.environ.get('db_username')
db_password = os.environ.get('db_password')
db_host = os.environ.get('db_host')
db_port = os.environ.get('db_port')
db_name = os.environ.get('db_name')
echo_mode = os.environ.get('echo_mode')

# create DB
engine = sqlalchemy.create_engine(f"postgresql+psycopg2://{db_username}:{db_password}@{db_host}:{db_port}/{db_name}", echo=eval(echo_mode))
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

    def __repr__(self):
        return {
            'tg_user_id': self.tg_user_id,
            'quiz_status': self.quiz_status,
            'is_ban': self.is_ban,
            'group': self.group,
            'int_id': self.internal_msg_id
        }


class MessageLog(Base):
    """Create table 'message_log'"""
    __tablename__ = 'message_log'
    internal_msg_id = Column(INTEGER, primary_key=True)  # only internal msg_id
    tg_user_id = Column(INTEGER, ForeignKey('user.tg_user_id'))  # tg sender id
    msg_text = Column(TEXT)  # text from message
    msg_timestamp = Column(TIMESTAMP)  # seconds since the epoch

    def __repr__(self):
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
    quiz_name = Column(TEXT)  # full quiz name
    quiz_title = Column(TEXT)  # quiz title
    quiz_status = Column(BOOLEAN, default=0)  # current status in 0 - hide, 1 - show

    def __repr__(self):
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
    quest_text = Column(TEXT)  # question text
    quest_ans = Column(TEXT)  # answer options or marker for self-written input

    def __repr__(self):
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

    def __repr__(self):
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

    def __repr__(self):
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

    def __repr__(self):
        return {
            'internal_user_id': self.internal_user_id,
            'tg_user_id': self.tg_user_id,
            'reason': self.reason,
            'ban_time': self.ban_time,
            'unban_time': self.ban_time
        }


Base.metadata.create_all(engine)


def get_last_timestamp(tg_id):
    with Session(engine) as timestamp_session:
        statement = (select(MessageLog.msg_timestamp).where(MessageLog.tg_user_id == tg_id))
        res = timestamp_session.scalars(statement).all()
        return res[-1]


def add_message_in_log(tg_id, msg_txt, msg_t_stamp):
    """Insert message with message-info to table 'message_log'"""
    with Session(engine) as msg_log_session:
        normal_date = datetime.datetime.fromtimestamp(msg_t_stamp)
        new_message = MessageLog(tg_user_id=tg_id, msg_text='%s' % msg_txt, msg_timestamp=normal_date)
        msg_log_session.add(new_message)
        msg_log_session.commit()
        init_logger.info('Message %s from user_id %s' % (msg_txt, tg_id))


def add_user(tg_id, msg_txt, msg_t_stamp):
    """Checks and optionally adds a new user to table 'user'"""
    with Session(engine) as session:

        statement = (select(User.tg_user_id).where(User.tg_user_id == tg_id))
        res = session.scalars(statement).all()
        if tg_id not in res:
            new_user = User(tg_user_id=tg_id)
            session.add(new_user)
            session.commit()
            init_logger.info('Added new user with id %s' % tg_id)

        add_message_in_log(tg_id, msg_txt, msg_t_stamp)  # Decorator cannot be used because the user must be added first
