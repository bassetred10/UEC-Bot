import os
from typing import List, Dict
from datetime import timedelta

class Config:
    """
    فئة تحتوي على جميع إعدادات البوت
    """
    
    # ============================================
    # إعدادات البوت الأساسية
    # ============================================
    
    BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
    CHANNEL_ID = int(os.getenv('CHANNEL_ID', '-1004304853750'))
    CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME', 'uec_u')
    ADMIN_ID = int(os.getenv('ADMIN_ID', '6046274404'))
    
    # ============================================
    # 🔒 إعدادات الأمان والحماية
    # ============================================
    
    # معدل الطلبات (Rate Limiting)
    ENABLE_RATE_LIMIT = os.getenv('ENABLE_RATE_LIMIT', 'true').lower() == 'true'
    MAX_REQUESTS_PER_MINUTE = int(os.getenv('MAX_REQUESTS_PER_MINUTE', '30'))
    RATE_LIMIT_WINDOW = 60  # ثانية
    
    # مكافحة البريد العشوائي (Anti-Spam)
    ENABLE_ANTI_SPAM = os.getenv('ENABLE_ANTI_SPAM', 'true').lower() == 'true'
    MAX_SIMILAR_MESSAGES = 3  # عدد الرسائل المتشابهة المسموح بها
    SPAM_WINDOW = 60  # ثانية
    
    # حماية الروابط
    ALLOWED_DOMAINS = [
        'youtube.com', 'youtu.be', 'www.youtube.com',
        'm.youtube.com', 'youtube-nocookie.com'
    ]
    
    # الحد الأقصى لطول الرسالة
    MAX_MESSAGE_LENGTH = 5000
    
    # الحد الأقصى لعدد المقاطع لكل مستخدم في اليوم
    MAX_CLIPS_PER_USER_DAY = 20
    
    # القائمة السوداء للمستخدمين
    BLACKLISTED_USERS = []  # يمكن إضافة IDs هنا
    
    # القائمة البيضاء (إذا كانت مفعلة)
    WHITELIST_ENABLED = False
    WHITELISTED_USERS = []
    
    # ============================================
    # إعدادات المعالجة
    # ============================================
    
    COOKIES_FILE = os.getenv('COOKIES_FILE', 'cookies.txt')
    
    KEYWORDS: List[str] = [
        'دعاء', 'اللهم', 'ربنا', 'يا رب',
        'استغفر الله', 'سبحان الله', 'الحمد لله', 'الله أكبر',
        'لا إله إلا الله', 'سبحان الله وبحمده',
        'حديث', 'قال رسول الله', 'قال النبي', 'عن النبي',
        'روى البخاري', 'روى مسلم',
        'قال الله', 'قال تعالى', 'آية', 'سورة', 'القرآن',
        'قصة', 'حكمة', 'عبرة', 'موعظة', 'نصيحة',
        'الله', 'محمد', 'رسول', 'نبي',
        'إسلام', 'إيمان', 'تقوى', 'توكل',
        'صلاة', 'زكاة', 'صوم', 'حج', 'عبادة'
    ]
    
    MAX_CLIPS = 5
    PADDING_TIME = 1.0
    MAX_PROCESSING_TIME = 300
    WHISPER_MODEL = 'base'
    AUDIO_QUALITY = '0'
    
    # ============================================
    # إعدادات النظام
    # ============================================
    
    DB_PATH = os.getenv('DB_PATH', 'bot_database.db')
    TEMP_DIR = os.getenv('TEMP_DIR', 'temp')
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = 'logs/bot.log'
    
    # ============================================
    # إعدادات Keep-Alive (لمنع النوم)
    # ============================================
    
    KEEP_ALIVE_INTERVAL = 300  # 5 دقائق
    KEEP_ALIVE_URL = os.getenv('RENDER_EXTERNAL_URL', '')
    
    # ============================================
    # رسائل البوت
    # ============================================
    
    WELCOME_MESSAGE = (
        "👋 <b>مرحباً بك في بوت بودكاست</b>\n\n"
        "🎙️ <i>تحويل فيديوهات البودكاست الدينية لتسهيل نشرها في مواقع التواصل الاجتماعي</i>\n\n"
        "📤 أرسل رابط الفيديو الآن وسأقوم بقص أهم الفوائد "
        "(دعاء، حديث، حكمة) لك!\n\n"
        "🔍 الكلمات المفتاحية المدعومة:\n"
        f"{', '.join(KEYWORDS[:10])}..."
    )


def validate_config() -> bool:
    """التحقق من صحة الإعدادات"""
    errors = []
    
    if Config.BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        errors.append("❌ BOT_TOKEN غير صحيح")
    elif len(Config.BOT_TOKEN) < 20:
        errors.append("❌ BOT_TOKEN قصير جداً")
    
    if Config.CHANNEL_ID == 0:
        errors.append("❌ CHANNEL_ID غير صحيح")
    
    if Config.ADMIN_ID == 0:
        errors.append("❌ ADMIN_ID غير صحيح")
    
    if errors:
        print("\n" + "="*50)
        print("⚠️  تحذير: يوجد أخطاء في الإعدادات")
        print("="*50)
        for error in errors:
            print(f"  {error}")
        print("="*50 + "\n")
        return False
    
    print("\n✅ تم التحقق من الإعدادات بنجاح")
    print(f"   - BOT_TOKEN: {Config.BOT_TOKEN[:10]}...")
    print(f"   - CHANNEL_ID: {Config.CHANNEL_ID}")
    print(f"   - ADMIN_ID: {Config.ADMIN_ID}")
    print(f"   - KEYWORDS: {len(Config.KEYWORDS)} كلمة")
    print(f"   - Rate Limit: {'مفعل' if Config.ENABLE_RATE_LIMIT else 'معطل'}")
    print(f"   - Anti-Spam: {'مفعل' if Config.ENABLE_ANTI_SPAM else 'معطل'}")
    print()
    return True


if __name__ == "__main__":
    validate_config()
