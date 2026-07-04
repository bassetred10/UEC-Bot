import time
import re
import hashlib
import logging
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from config import Config

logger = logging.getLogger(__name__)


@dataclass
class UserActivity:
    """تتبع نشاط المستخدم"""
    user_id: int
    requests: List[float] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)
    last_request: float = 0
    clip_count_today: int = 0
    last_clip_time: float = 0
    is_blacklisted: bool = False
    warnings: int = 0


class SecurityManager:
    """
    مدير الأمان والحماية
    """
    
    def __init__(self):
        """تهيئة مدير الأمان"""
        self.user_activities: Dict[int, UserActivity] = {}
        self.blacklisted_ips: List[str] = []
        self.global_request_count = 0
        self.request_history: List[float] = []
        
        # إعدادات الحماية
        self.max_requests_per_minute = Config.MAX_REQUESTS_PER_MINUTE
        self.max_similar_messages = Config.MAX_SIMILAR_MESSAGES
        self.spam_window = Config.SPAM_WINDOW
        self.max_clips_per_day = Config.MAX_CLIPS_PER_USER_DAY
        
        logger.info("🔒 Security Manager initialized")
    
    def is_user_blacklisted(self, user_id: int) -> bool:
        """التحقق من وجود المستخدم في القائمة السوداء"""
        if user_id in Config.BLACKLISTED_USERS:
            return True
        
        if user_id in self.user_activities:
            return self.user_activities[user_id].is_blacklisted
        
        return False
    
    def blacklist_user(self, user_id: int, reason: str = "انتهاك قواعد الأمان"):
        """إضافة مستخدم إلى القائمة السوداء"""
        if user_id not in self.user_activities:
            self.user_activities[user_id] = UserActivity(user_id=user_id)
        
        self.user_activities[user_id].is_blacklisted = True
        logger.warning(f"🚫 User {user_id} blacklisted: {reason}")
        
        # تسجيل في قاعدة البيانات
        self._log_security_event(user_id, "BLACKLIST", reason)
    
    def check_rate_limit(self, user_id: int) -> Tuple[bool, str]:
        """
        التحقق من معدل الطلبات
        
        Returns:
            Tuple[bool, str]: (مسموح, رسالة الخطأ)
        """
        if not Config.ENABLE_RATE_LIMIT:
            return True, ""
        
        if self.is_user_blacklisted(user_id):
            return False, "⛔ تم حظر حسابك بسبب انتهاك قواعد الأمان"
        
        # الحصول على نشاط المستخدم
        activity = self._get_user_activity(user_id)
        
        # تنظيف الطلبات القديمة
        current_time = time.time()
        activity.requests = [t for t in activity.requests 
                           if current_time - t < Config.RATE_LIMIT_WINDOW]
        
        # التحقق من عدد الطلبات
        if len(activity.requests) >= self.max_requests_per_minute:
            warning_msg = f"⚠️ تجاوزت الحد المسموح من الطلبات ({self.max_requests_per_minute} في الدقيقة)"
            logger.warning(f"Rate limit exceeded for user {user_id}")
            
            # زيادة عدد التحذيرات
            activity.warnings += 1
            
            # حظر تلقائي بعد 3 تحذيرات
            if activity.warnings >= 3:
                self.blacklist_user(user_id, "تجاوز حد الطلبات بشكل متكرر")
                return False, "⛔ تم حظر حسابك بسبب تجاوز حد الطلبات بشكل متكرر"
            
            return False, warning_msg
        
        # تسجيل الطلب
        activity.requests.append(current_time)
        activity.last_request = current_time
        self.global_request_count += 1
        
        # تنظيف التاريخ العالمي
        self.request_history = [t for t in self.request_history 
                              if current_time - t < Config.RATE_LIMIT_WINDOW]
        self.request_history.append(current_time)
        
        return True, ""
    
    def check_anti_spam(self, user_id: int, message: str) -> Tuple[bool, str]:
        """
        التحقق من البريد العشوائي
        
        Returns:
            Tuple[bool, str]: (مسموح, رسالة الخطأ)
        """
        if not Config.ENABLE_ANTI_SPAM:
            return True, ""
        
        if self.is_user_blacklisted(user_id):
            return False, "⛔ تم حظر حسابك بسبب انتهاك قواعد الأمان"
        
        activity = self._get_user_activity(user_id)
        
        # تنظيف الرسائل القديمة
        current_time = time.time()
        # نحتفظ فقط بالرسائل الحديثة
        if len(activity.messages) > self.max_similar_messages * 2:
            activity.messages = activity.messages[-self.max_similar_messages * 2:]
        
        # التحقق من تشابه الرسائل
        similar_count = 0
        for old_msg in activity.messages[-self.max_similar_messages:]:
            # حساب نسبة التشابه
            similarity = self._calculate_similarity(message, old_msg)
            if similarity > 0.8:  # تشابه 80%
                similar_count += 1
        
        # إضافة الرسالة للسجل
        activity.messages.append(message)
        
        if similar_count >= self.max_similar_messages:
            logger.warning(f"Spam detected from user {user_id}")
            activity.warnings += 1
            
            if activity.warnings >= 3:
                self.blacklist_user(user_id, "إرسال رسائل مكررة بشكل مفرط")
                return False, "⛔ تم حظر حسابك بسبب إرسال رسائل مكررة"
            
            return False, "⚠️ تم اكتشاف نشاط مريب، يرجى التوقف عن إرسال رسائل مكررة"
        
        return True, ""
    
    def check_url_safety(self, url: str) -> Tuple[bool, str]:
        """
        التحقق من أمان الرابط
        
        Returns:
            Tuple[bool, str]: (آمن, رسالة الخطأ)
        """
        if not url:
            return False, "الرابط فارغ"
        
        # التحقق من وجود الرابط
        if not url.startswith(('http://', 'https://')):
            return False, "❌ الرابط غير صحيح"
        
        # التحقق من النطاقات المسموحة
        is_allowed = False
        for domain in Config.ALLOWED_DOMAINS:
            if domain in url.lower():
                is_allowed = True
                break
        
        if not is_allowed:
            return False, "❌ هذا الرابط غير مدعوم. يرجى إرسال رابط من يوتيوب فقط"
        
        # التحقق من وجود أي نصوص ضارة
        dangerous_patterns = [
            r'<script', r'javascript:', r'onclick=', 
            r'onerror=', r'alert\(', r'%3Cscript'
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                logger.warning(f"Dangerous URL detected: {url[:50]}...")
                return False, "⛔ تم اكتشاف رابط غير آمن"
        
        return True, ""
    
    def check_clip_limit(self, user_id: int) -> Tuple[bool, str]:
        """
        التحقق من الحد الأقصى للمقاطع في اليوم
        
        Returns:
            Tuple[bool, str]: (مسموح, رسالة الخطأ)
        """
        activity = self._get_user_activity(user_id)
        
        # التحقق من اليوم الحالي
        today = datetime.now().date()
        if activity.last_clip_time > 0:
            last_date = datetime.fromtimestamp(activity.last_clip_time).date()
            if last_date != today:
                # يوم جديد، إعادة تعيين العداد
                activity.clip_count_today = 0
        
        if activity.clip_count_today >= self.max_clips_per_day:
            return False, f"⚠️ تجاوزت الحد اليومي من المقاطع ({self.max_clips_per_day})"
        
        return True, ""
    
    def increment_clip_count(self, user_id: int):
        """زيادة عدد المقاطع المستخرجة للمستخدم"""
        activity = self._get_user_activity(user_id)
        activity.clip_count_today += 1
        activity.last_clip_time = time.time()
    
    def _get_user_activity(self, user_id: int) -> UserActivity:
        """الحصول على نشاط المستخدم"""
        if user_id not in self.user_activities:
            self.user_activities[user_id] = UserActivity(user_id=user_id)
        return self.user_activities[user_id]
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        حساب نسبة التشابه بين نصين
        
        Returns:
            float: نسبة التشابه (0.0 - 1.0)
        """
        if not text1 or not text2:
            return 0.0
        
        # تبسيط النصوص للمقارنة
        t1 = text1.lower().strip()
        t2 = text2.lower().strip()
        
        if t1 == t2:
            return 1.0
        
        # حساب التشابه باستخدام Jaccard
        words1 = set(t1.split())
        words2 = set(t2.split())
        
        if not words1 and not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def _log_security_event(self, user_id: int, event_type: str, details: str):
        """تسجيل حدث أمني"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'event_type': event_type,
            'details': details
        }
        
        # تسجيل في ملف السجلات
        logger.warning(f"🔒 SECURITY EVENT: {log_entry}")
        
        # هنا يمكن إضافة تخزين في قاعدة البيانات


# إنشاء كائن مدير الأمان العالمي
security_manager = SecurityManager()
