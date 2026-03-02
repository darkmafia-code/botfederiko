from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship, declarative_base
import datetime

Base = declarative_base()


class Chat(Base):
    __tablename__ = "chats"
    id = Column(BigInteger, primary_key=True, index=True)
    title = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    users = relationship("UserChatStats", back_populates="chat")


class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    stats = relationship("UserChatStats", back_populates="user")


class UserChatStats(Base):
    __tablename__ = "user_chat_stats"
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(BigInteger, ForeignKey("chats.id"))
    user_id = Column(BigInteger, ForeignKey("users.id"))
    messages_sent = Column(Integer, default=0, nullable=False)
    replies_sent = Column(Integer, default=0, nullable=False)
    reactions_given = Column(Float, default=0.0, nullable=False)
    reactions_received = Column(Float, default=0.0, nullable=False)
    current_streak = Column(Integer, default=0, nullable=False)
    longest_streak = Column(Integer, default=0, nullable=False)
    deleted_messages = Column(Integer, default=0, nullable=False)
    last_activity_date = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    total_score = Column(Float, default=0.0, nullable=False)

    user = relationship("User", back_populates="stats")
    chat = relationship("Chat", back_populates="users")


class Achievement(Base):
    __tablename__ = "achievements"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(String)


class UserAchievement(Base):
    __tablename__ = "user_achievements"
    id = Column(Integer, primary_key=True, index=True)
    user_chat_stats_id = Column(Integer, ForeignKey("user_chat_stats.id"))
    achievement_id = Column(Integer, ForeignKey("achievements.id"))
    awarded_at = Column(DateTime, default=datetime.datetime.utcnow)

    stats = relationship("UserChatStats")
    achievement = relationship("Achievement")
