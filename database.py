from sqlalchemy import create_engine, Column, Integer, String, DateTime, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import json

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    total_clips = Column(Integer, default=0)

class Clip(Base):
    __tablename__ = 'clips'
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, nullable=False)
    video_url = Column(String)
    clip_path = Column(String)
    keywords_found = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class Database:
    def __init__(self, db_path='bot_database.db'):
        self.engine = create_engine(f'sqlite:///{db_path}')
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
    
    def add_user(self, user_id, username, first_name, last_name):
        session = self.Session()
        try:
            user = session.query(User).filter_by(user_id=user_id).first()
            if not user:
                user = User(user_id=user_id, username=username, first_name=first_name, last_name=last_name)
                session.add(user)
                session.commit()
        finally:
            session.close()

    def add_clip(self, user_id, video_url, clip_path, keywords):
        session = self.Session()
        try:
            clip = Clip(user_id=user_id, video_url=video_url, clip_path=clip_path, keywords_found=json.dumps(keywords))
            session.add(clip)
            session.commit()
        finally:
            session.close()
