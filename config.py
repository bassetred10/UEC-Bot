import os
from typing import List

class Config:
    """
    فئة تحتوي على جميع إعدادات البوت
    """
    
    # ============================================
    # إعدادات البوت الأساسية (من متغيرات البيئة)
    # ============================================
    
    # توكن البوت من BotFather (مطلوب)
    BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
    
    # معرف القناة الإجبارية (من متغيرات البيئة)
    CHANNEL_ID = int(os.getenv('CHANNEL_ID', '-1004304853750'))
    
    # اسم المستخدم للقناة
    CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME', 'uec_u')
    
    # معرف الأدمن (من متغيرات البيئة)
    ADMIN_ID = int(os.getenv('ADMIN_ID', '6046274404'))
    
    # ============================================
    # إعدادات الكوكيز
    # ============================================
    
    COOKIES_FILE = os.getenv('COOKIES_FILE', 'cookies.txt')
    
    # ============================================
    # الكلمات المفتاحية الدينية
    # ============================================
    
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
    
    # ============================================
    # إعدادات المعالجة
    # ============================================
    
    MAX_CLIPS = 5
    PADDING_TIME = 1.0
    MAX_PROCESSING_TIME = 300
    WHISPER_MODEL = 'base'  # tiny, base, small, medium, large
    AUDIO_QUALITY = '0'
    
    # ============================================
    # إعدادات النظام
    # ============================================
    
    DB_PATH = os.getenv('DB_PATH', 'bot_database.db')
    TEMP_DIR = os.getenv('TEMP_DIR', 'temp')
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = 'logs/bot.log'
    
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
    """
    التحقق من صحة الإعدادات
    """
    errors = []
    
    # التحقق من التوكن
    if Config.BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        errors.append("❌ BOT_TOKEN غير صحيح. يرجى إضافته في متغيرات البيئة")
    elif len(Config.BOT_TOKEN) < 20:
        errors.append("❌ BOT_TOKEN يبدو غير صحيح (قصير جداً)")
    
    # التحقق من معرف القناة
    if Config.CHANNEL_ID == 0:
        errors.append("❌ CHANNEL_ID غير صحيح. يرجى إضافته في متغيرات البيئة")
    
    # التحقق من معرف الأدمن
    if Config.ADMIN_ID == 0:
        errors.append("❌ ADMIN_ID غير صحيح. يرجى إضافته في متغيرات البيئة")
    
    # عرض النتائج
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
    print()
    return True


if __name__ == "__main__":
    validate_config()
