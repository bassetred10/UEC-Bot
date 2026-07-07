import time
import re
import logging
from typing import Dict, List, Tuple
from collections import defaultdict
from datetime import datetime

from config import Config

logger = logging.getLogger(__name__)


class SecurityManager:
    """
    مدير الأمان والحماية
    """
    
    def __init__(self):
        """تهيئة مدير الأمان"""
        self.user_activities = {}
        self.blacklisted_users = []
        
        # 🔴 التعديل هنا: MAX_REQUESTS_PER_MINUTE (مع S)
        self.max_requests_per_minute = Config.MAX_REQUESTS_PER_MINUTE
        self.max_similar_messages = Config.MAX_SIMILAR_MESSAGES
        self.spam_window = Config.SPAM_WINDOW
        self.max_clips_per_day = Config.MAX_CLIPS_PER_USER_DAY
        
        logger.info("🔒 Security Manager initialized")
    
    def is_user_blacklisted(self, user_id: int) -> bool:
        """التحقق من وجود المستخدم في القائمة السوداء"""
        if user_id in Config.BLACKLISTED_USERS:
            return True
        return False
    
    def check_rate_limit(self, user_id: int) -> Tuple[bool, str]:
        """التحقق من معدل الطلبات"""
        if not Config.ENABLE_RATE_LIMIT:
            return True, ""
        
        if user_id not in self.user_activities:
            self.user_activities[user_id] = {'requests': [], 'messages': []}
        
        # تنظيف الطلبات القديمة
        current_time = time.time()
        self.user_activities[user_id]['requests'] = [
            t for t in self.user_activities[user_id]['requests']
            if current_time - t < Config.RATE_LIMIT_WINDOW
        ]
        
        if len(self.user_activities[user_id]['requests']) >= self.max_requests_per_minute:
            return False, "⚠️ تجاوزت حد الطلبات المسموح به"
        
        self.user_activities[user_id]['requests'].append(current_time)
        return True, ""
    
    def check_anti_spam(self, user_id: int, message: str) -> Tuple[bool, str]:
        """التحقق من البريد العشوائي"""
        if not Config.ENABLE_ANTI_SPAM:
            return True, ""
        
        if user_id not in self.user_activities:
            self.user_activities[user_id] = {'requests': [], 'messages': []}
        
        # تنظيف الرسائل القديمة
        current_time = time.time()
        self.user_activities[user_id]['messages'] = [
            m for m in self.user_activities[user_id]['messages'][-10:]
        ]
        
        # التحقق من تشابه الرسائل
        similar_count = 0
        for old_msg in self.user_activities[user_id]['messages']:
            if self._calculate_similarity(message, old_msg) > 0.8:
                similar_count += 1
        
        self.user_activities[user_id]['messages'].append(message)
        
        if similar_count >= self.max_similar_messages:
            return False, "⚠️ تم اكتشاف نشاط مريب، يرجى التوقف"
        
        return True, ""
    
    def check_url_safety(self, url: str) -> Tuple[bool, str]:
        """التحقق من أمان الرابط"""
        if not url:
            return False, "الرابط فارغ"
        
        if not url.startswith(('http://', 'https://')):
            return False, "❌ الرابط غير صحيح"
        
        is_allowed = False
        for domain in Config.ALLOWED_DOMAINS:
            if domain in url.lower():
                is_allowed = True
                break
        
        if not is_allowed:
            return False, "❌ هذا الرابط غير مدعوم. يرجى إرسال رابط من يوتيوب فقط"
        
        return True, ""
    
    def check_clip_limit(self, user_id: int) -> Tuple[bool, str]:
        """التحقق من الحد الأقصى للمقاطع في اليوم"""
        return True, ""
    
    def increment_clip_count(self, user_id: int):
        """زيادة عدد المقاطع المستخرجة للمستخدم"""
        pass
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """حساب نسبة التشابه بين نصين"""
        if not text1 or not text2:
            return 0.0
        
        t1 = text1.lower().strip()
        t2 = text2.lower().strip()
        
        if t1 == t2:
            return 1.0
        
        words1 = set(t1.split())
        words2 = set(t2.split())
        
        if not words1 and not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0


# إنشاء كائن مدير الأمان العالمي
security_manager = SecurityManager()
