from sqlalchemy import create_engine, Column, Integer, String, DateTime, BigInteger, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
import json
from typing import Tuple, Optional
import logging

from config import Config

logger = logging.getLogger(__name__)
Base = declarative_base()


class User(Base):
    """
    نموذج المستخدم في قاعدة البيانات
    """
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    total_clips = Column(Integer, default=0)
    is_active = Column(Integer, default=1)  # 1 = نشط, 0 = محظور


class Clip(Base):
    """
    نموذج المقاطع المستخرجة في قاعدة البيانات
    """
    __tablename__ = 'clips'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    video_url = Column(String, nullable=False)
    clip_path = Column(String, nullable=False)
    keywords_found = Column(Text, nullable=True)  # JSON array
    start_time = Column(String, nullable=True)  # التوقيت بالثواني
    end_time = Column(String, nullable=True)
    duration = Column(String, nullable=True)  # المدة بالثواني
    created_at = Column(DateTime, default=datetime.utcnow)


class Database:
    """
    فئة التعامل مع قاعدة البيانات
    """
    
    def __init__(self, db_path: str = None):
        """
        تهيئة قاعدة البيانات
        
        Args:
            db_path: مسار ملف قاعدة البيانات
        """
        if db_path is None:
            db_path = Config.DB_PATH
        
        self.engine = create_engine(f'sqlite:///{db_path}')
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        logger.info(f"Database initialized at {db_path}")
    
    def get_session(self) -> Session:
        """
        الحصول على جلسة قاعدة البيانات
        
        Returns:
            Session: جلسة قاعدة البيانات
        """
        return self.Session()
    
    def add_user(self, user_id: int, username: str = None, 
                 first_name: str = None, last_name: str = None) -> bool:
        """
        إضافة مستخدم جديد أو تحديث مستخدم موجود
        
        Args:
            user_id: معرف المستخدم
            username: اسم المستخدم
            first_name: الاسم الأول
            last_name: الاسم الأخير
        
        Returns:
            bool: نجاح العملية
        """
        session = self.get_session()
        try:
            # البحث عن المستخدم
            user = session.query(User).filter_by(user_id=user_id).first()
            
            if not user:
                # إنشاء مستخدم جديد
                user = User(
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name
                )
                session.add(user)
                logger.info(f"New user added: {user_id}")
            else:
                # تحديث بيانات المستخدم
                if username:
                    user.username = username
                if first_name:
                    user.first_name = first_name
                if last_name:
                    user.last_name = last_name
                user.last_activity = datetime.utcnow()
                logger.info(f"User updated: {user_id}")
            
            session.commit()
            return True
            
        except Exception as e:
            session.rollback()
            logger.error(f"Database error in add_user: {e}")
            return False
        finally:
            session.close()
    
    def increment_clips(self, user_id: int) -> bool:
        """
        زيادة عدد المقاطع المستخرجة للمستخدم
        
        Args:
            user_id: معرف المستخدم
        
        Returns:
            bool: نجاح العملية
        """
        session = self.get_session()
        try:
            user = session.query(User).filter_by(user_id=user_id).first()
            if user:
                user.total_clips += 1
                user.last_activity = datetime.utcnow()
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Database error in increment_clips: {e}")
            return False
        finally:
            session.close()
    
    def add_clip(self, user_id: int, video_url: str, clip_path: str, 
                 keywords: list, start_time: float = None, 
                 end_time: float = None) -> bool:
        """
        إضافة مقطع مستخرج إلى قاعدة البيانات
        
        Args:
            user_id: معرف المستخدم
            video_url: رابط الفيديو
            clip_path: مسار المقطع
            keywords: قائمة الكلمات المفتاحية
            start_time: وقت البداية
            end_time: وقت النهاية
        
        Returns:
            bool: نجاح العملية
        """
        session = self.get_session()
        try:
            clip = Clip(
                user_id=user_id,
                video_url=video_url,
                clip_path=clip_path,
                keywords_found=json.dumps(keywords),
                start_time=str(start_time) if start_time else None,
                end_time=str(end_time) if end_time else None,
                duration=str(end_time - start_time) if (start_time and end_time) else None
            )
            session.add(clip)
            session.commit()
            logger.info(f"New clip added for user {user_id}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Database error in add_clip: {e}")
            return False
        finally:
            session.close()
    
    def get_stats(self) -> Tuple[int, int]:
        """
        الحصول على إحصائيات البوت
        
        Returns:
            Tuple[int, int]: (عدد المستخدمين, عدد المقاطع)
        """
        session = self.get_session()
        try:
            users_count = session.query(User).filter_by(is_active=1).count()
            clips_count = session.query(Clip).count()
            return users_count, clips_count
        except Exception as e:
            logger.error(f"Database error in get_stats: {e}")
            return 0, 0
        finally:
            session.close()
    
    def get_user_stats(self, user_id: int) -> Optional[dict]:
        """
        الحصول على إحصائيات مستخدم معين
        
        Args:
            user_id: معرف المستخدم
        
        Returns:
            Optional[dict]: بيانات المستخدم
        """
        session = self.get_session()
        try:
            user = session.query(User).filter_by(user_id=user_id).first()
            if user:
                return {
                    'user_id': user.user_id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'total_clips': user.total_clips,
                    'created_at': user.created_at,
                    'last_activity': user.last_activity
                }
            return None
        except Exception as e:
            logger.error(f"Database error in get_user_stats: {e}")
            return None
        finally:
            session.close()
    
    def get_user_clips(self, user_id: int, limit: int = 10) -> list:
        """
        الحصول على المقاطع المستخرجة لمستخدم معين
        
        Args:
            user_id: معرف المستخدم
            limit: عدد المقاطع المطلوبة
        
        Returns:
            list: قائمة المقاطع
        """
        session = self.get_session()
        try:
            clips = session.query(Clip).filter_by(user_id=user_id)\
                .order_by(Clip.created_at.desc()).limit(limit).all()
            return clips
        except Exception as e:
            logger.error(f"Database error in get_user_clips: {e}")
            return []
        finally:
            session.close()


# إنشاء كائن قاعدة البيانات العالمي
db = Database()
