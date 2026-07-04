import os
import sys
import logging
import asyncio
from datetime import datetime
from typing import Optional

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramAPIError

# استيراد الإعدادات والملفات الأخرى
from config import Config, validate_config
from database import db
from processor import VideoProcessor, check_requirements

# إعداد نظام التسجيل (Logging)
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Config.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# ============================================
# تعريف حالات FSM (Finite State Machine)
# ============================================

class ProcessState(StatesGroup):
    """
    حالات معالجة الفيديو
    """
    waiting_for_url = State()  # انتظار رابط الفيديو


# ============================================
# تهيئة البوت والمعالجات
# ============================================

# التحقق من صحة الإعدادات
if not validate_config():
    logger.error("Configuration validation failed")
    sys.exit(1)

# التحقق من تثبيت المتطلبات
if not check_requirements():
    logger.error("Requirements check failed")
    sys.exit(1)

# تهيئة البوت
bot = Bot(
    token=Config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

# تهيئة التخزين المؤقت للحالات
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# تهيئة معالج الفيديو
processor = VideoProcessor()


# ============================================
# دوال مساعدة
# ============================================

async def check_subscription(user_id: int) -> bool:
    """
    التحقق من اشتراك المستخدم في القناة الإجبارية
    
    Args:
        user_id: معرف المستخدم
    
    Returns:
        bool: هل المستخدم مشترك في القناة
    """
    try:
        member = await bot.get_chat_member(
            chat_id=Config.CHANNEL_ID,
            user_id=user_id
        )
        is_subscribed = member.status in ['member', 'administrator', 'creator']
        
        if not is_subscribed:
            logger.info(f"User {user_id} is not subscribed to channel")
        
        return is_subscribed
        
    except TelegramAPIError as e:
        logger.error(f"Telegram API error in check_subscription: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error in check_subscription: {e}")
        return False


def get_main_keyboard() -> InlineKeyboardMarkup:
    """
    إنشاء لوحة المفاتيح الرئيسية
    
    Returns:
        InlineKeyboardMarkup: لوحة المفاتيح
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 الإحصائيات", callback_data="stats"),
            InlineKeyboardButton(text="ℹ️ المساعدة", callback_data="help")
        ],
        [
            InlineKeyboardButton(text="👤 ملفي الشخصي", callback_data="profile"),
            InlineKeyboardButton(text="📋 مقاطعي", callback_data="my_clips")
        ]
    ])


def get_subscription_keyboard() -> InlineKeyboardMarkup:
    """
    إنشاء لوحة مفاتيح الاشتراك الإجباري
    
    Returns:
        InlineKeyboardMarkup: لوحة مفاتيح الاشتراك
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📢 اشترك في القناة",
                url=f"https://t.me/{Config.CHANNEL_USERNAME}"
            )
        ],
        [
            InlineKeyboardButton(
                text="✅ تحقق من الاشتراك",
                callback_data="check_subscription"
            )
        ]
    ])


def get_keyword_keyboard() -> InlineKeyboardMarkup:
    """
    إنشاء لوحة مفاتيح الكلمات المفتاحية
    
    Returns:
        InlineKeyboardMarkup: لوحة مفاتيح الكلمات
    """
    buttons = []
    row = []
    
    # عرض أول 6 كلمات مفتاحية
    for i, keyword in enumerate(Config.KEYWORDS[:6]):
        row.append(InlineKeyboardButton(
            text=f"#{keyword}",
            callback_data=f"keyword_{keyword}"
        ))
        if len(row) == 3:
            buttons.append(row)
            row = []
    
    if row:
        buttons.append(row)
    
    # إضافة أزرار إضافية
    buttons.append([
        InlineKeyboardButton(
            text="🔄 تحديث الكلمات",
            callback_data="refresh_keywords"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ============================================
# معالجات الأوامر (Command Handlers)
# ============================================

@dp.message(CommandStart())
async def start_command(message: Message, state: FSMContext) -> None:
    """
    معالجة أمر /start
    
    تعرض رسالة ترحيب وتتحقق من اشتراك المستخدم
    
    Args:
        message: رسالة الأمر
        state: حالة FSM
    """
    user = message.from_user
    
    # تسجيل دخول المستخدم
    logger.info(f"User {user.id} (@{user.username}) started the bot")
    
    # إضافة المستخدم إلى قاعدة البيانات
    db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    # التحقق من الاشتراك في القناة
    if not await check_subscription(user.id):
        await message.answer(
            Config.SUBSCRIPTION_MESSAGE,
            reply_markup=get_subscription_keyboard()
        )
        return
    
    # عرض رسالة الترحيب
    await message.answer(
        Config.WELCOME_MESSAGE,
        reply_markup=get_main_keyboard()
    )
    
    # عرض الكلمات المفتاحية
    await message.answer(
        "🔑 <b>الكلمات المفتاحية المدعومة:</b>\n"
        f"{', '.join(Config.KEYWORDS[:15])}...\n\n"
        "💡 يمكنك اختيار كلمة من الأزرار أدناه",
        reply_markup=get_keyword_keyboard()
    )
    
    # تعيين حالة انتظار الرابط
    await state.set_state(ProcessState.waiting_for_url)


@dp.message(Command("help"))
async def help_command(message: Message) -> None:
    """
    معالجة أمر /help
    
    تعرض رسالة مساعدة تحتوي على شرح البوت والأوامر المتاحة
    
    Args:
        message: رسالة الأمر
    """
    help_text = (
        "🤖 <b>مساعدة البوت</b>\n\n"
        "📌 <b>كيفية الاستخدام:</b>\n"
        "1️⃣ أرسل رابط فيديو من يوتيوب\n"
        "2️⃣ سيقوم البوت بتحليل المحتوى\n"
        "3️⃣ سيتم استخراج المقاطع الدينية المهمة\n\n"
        "🔑 <b>الكلمات المفتاحية:</b>\n"
        f"{', '.join(Config.KEYWORDS)}\n\n"
        "⚙️ <b>الأوامر المتاحة:</b>\n"
        "/start - بدء البوت\n"
        "/help - المساعدة\n"
        "/stats - الإحصائيات (للإدمن فقط)\n\n"
        "📢 <b>قناتنا:</b> @uec_u"
    )
    
    await message.answer(help_text, reply_markup=get_main_keyboard())


@dp.message(Command("stats"))
async def stats_command(message: Message) -> None:
    """
    معالجة أمر /stats
    
    تعرض إحصائيات البوت (للمدير فقط)
    
    Args:
        message: رسالة الأمر
    """
    # التحقق من أن المستخدم هو المدير
    if message.from_user.id != Config.ADMIN_ID:
        await message.answer("⛔ هذا الأمر مخصص للإدمن فقط")
        return
    
    # جلب الإحصائيات من قاعدة البيانات
    users_count, clips_count = db.get_stats()
    
    stats_text = (
        f"📊 <b>إحصائيات البوت</b>\n\n"
        f"👥 عدد المستخدمين: <b>{users_count:,}</b>\n"
        f"🎬 المقاطع المستخرجة: <b>{clips_count:,}</b>\n"
        f"📅 آخر تحديث: <b>{datetime.now().strftime('%Y-%m-%d %H:%M')}</b>"
    )
    
    await message.answer(stats_text)


@dp.message(StateFilter(ProcessState.waiting_for_url))
async def handle_url(message: Message, state: FSMContext) -> None:
    """
    معالجة الروابط المرسلة من المستخدمين
    
    تقوم بتحميل الفيديو، تحويله إلى نص، واستخراج المقاطع الدينية
    
    Args:
        message: رسالة المستخدم
        state: حالة FSM
    """
    user = message.from_user
    
    # التحقق من الاشتراك
    if not await check_subscription(user.id):
        await message.answer(
            "⚠️ يرجى الاشتراك في قناتنا أولاً",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    # الحصول على النص المرسل
    url = message.text.strip()
    
    # التحقق من صحة الرابط
    if not (url.startswith('http://') or url.startswith('https://')):
        await message.answer(
            "❌ يرجى إرسال رابط صحيح للفيديو من يوتيوب\n\n"
            "مثال: https://www.youtube.com/watch?v=xxxxx"
        )
        return
    
    # إرسال رسالة المعالجة
    processing_msg = await message.answer(
        "🔄 <b>جاري تحميل وتحليل الفيديو...</b>\n"
        "⏳ قد يستغرق هذا بعض الوقت (حتى 5 دقائق)\n\n"
        "📌 الخطوات:\n"
        "1️⃣ تحميل الفيديو 📥\n"
        "2️⃣ تحويل الصوت إلى نص 🎙️\n"
        "3️⃣ البحث عن الكلمات المفتاحية 🔍\n"
        "4️⃣ استخراج المقاطع ✂️"
    )
    
    try:
        # معالجة الفيديو
        logger.info(f"Processing video for user {user.id}: {url}")
        segments, clips = await processor.process_video(url, Config.KEYWORDS)
        
        if not segments:
            await processing_msg.edit_text(
                "❌ <b>لم يتم العثور على كلمات مفتاحية دينية</b>\n\n"
                "💡 حاول استخدام فيديو آخر يحتوي على:\n"
                f"• {', '.join(Config.KEYWORDS[:5])}\n\n"
                "🔍 يمكنك أيضاً اختيار كلمة من الأزرار أدناه",
                reply_markup=get_keyword_keyboard()
            )
            return
        
        # تحديث رسالة المعالجة
        await processing_msg.edit_text(
            f"✅ <b>تم العثور على {len(segments)} مقطع ديني!</b>\n"
            f"🎥 <i>جاري تحميل المقاطع...</i>"
        )
        
        # إرسال المقاطع المستخرجة
        for i, (segment, clip_path) in enumerate(zip(segments, clips), 1):
            # الكلمات المفتاحية المكتشفة
            keywords_text = ', '.join(segment['keywords'])
            
            # نص المقطع (مختصر)
            text_preview = segment['text'][:200]
            if len(segment['text']) > 200:
                text_preview += '...'
            
            caption = (
                f"🎬 <b>المقطع {i}/{len(segments)}</b>\n\n"
                f"🔑 <b>الكلمات المفتاحية:</b> {keywords_text}\n"
                f"⏱️ <b>التوقيت:</b> {segment['start']:.2f} - {segment['end']:.2f} ثانية\n"
                f"📏 <b>المدة:</b> {segment['duration']:.2f} ثانية\n\n"
                f"📝 <b>النص:</b>\n<code>{text_preview}</code>"
            )
            
            try:
                # إرسال المقطع الصوتي
                with open(clip_path, 'rb') as audio_file:
                    await message.answer_audio(
                        audio_file,
                        caption=caption,
                        performer="بودكاست ديني",
                        title=f"مقطع ديني {i}"
                    )
                
                # تسجيل المقطع في قاعدة البيانات
                db.add_clip(
                    user_id=user.id,
                    video_url=url,
                    clip_path=clip_path,
                    keywords=segment['keywords'],
                    start_time=segment['start'],
                    end_time=segment['end']
                )
                
                # زيادة عدد المقاطع للمستخدم
                db.increment_clips(user.id)
                
                # تنظيف الملف المؤقت
                processor.cleanup_clip(clip_path)
                
            except Exception as e:
                logger.error(f"Failed to send clip {i}: {e}")
                await message.answer(f"❌ فشل إرسال المقطع {i}: {e}")
        
        # رسالة الانتهاء
        await processing_msg.edit_text(
            "✅ <b>تم الانتهاء من استخراج جميع المقاطع!</b>\n\n"
            "🔗 يمكنك مشاركة هذه المقاطع في مواقع التواصل الاجتماعي\n"
            "📤 استخدم زر المشاركة لمشاركة المقطع"
        )
        
    except Exception as e:
        logger.error(f"Processing error for user {user.id}: {e}")
        await processing_msg.edit_text(
            f"❌ <b>حدث خطأ أثناء المعالجة</b>\n\n"
            f"<code>{str(e)}</code>\n\n"
            "💡 نصائح:\n"
            "• تأكد من صحة الرابط\n"
            "• تأكد من وجود اتصال بالإنترنت\n"
            "• حاول مرة أخرى بعد قليل\n\n"
            "إذا استمر الخطأ، يرجى الاتصال بالدعم"
        )


# ============================================
# معالجات الأزرار (Callback Query Handlers)
# ============================================

@dp.callback_query()
async def handle_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """
    معالجة ضغطات الأزرار
    
    Args:
        callback: بيانات الضغط على الزر
        state: حالة FSM
    """
    user = callback.from_user
    data = callback.data
    
    # معالجة تحقق الاشتراك
    if data == "check_subscription":
        if await check_subscription(user.id):
            await callback.message.delete()
            await start_command(callback.message, state)
        else:
            await callback.answer(
                "⚠️ لم يتم الاشتراك بعد، يرجى الاشتراك أولاً",
                show_alert=True
            )
        await callback.answer()
        return
    
    # معالجة عرض الإحصائيات
    if data == "stats":
        if user.id == Config.ADMIN_ID:
            await stats_command(callback.message)
        else:
            await callback.answer("⛔ هذا الأمر مخصص للإدمن فقط")
        await callback.answer()
        return
    
    # معالجة عرض المساعدة
    if data == "help":
        await help_command(callback.message)
        await callback.answer()
        return
    
    # معالجة عرض الملف الشخصي
    if data == "profile":
        user_stats = db.get_user_stats(user.id)
        if user_stats:
            profile_text = (
                f"👤 <b>بيانات المستخدم</b>\n\n"
                f"🆔 <b>المعرف:</b> <code>{user_stats['user_id']}</code>\n"
                f"📛 <b>الاسم:</b> {user_stats['first_name'] or 'غير معروف'}\n"
                f"👤 <b>المعرف:</b> @{user_stats['username'] or 'غير موجود'}\n"
                f"📊 <b>المقاطع المستخرجة:</b> {user_stats['total_clips']}\n"
                f"📅 <b>تاريخ الانضمام:</b> {user_stats['created_at'].strftime('%Y-%m-%d %H:%M')}\n"
                f"📅 <b>آخر نشاط:</b> {user_stats['last_activity'].strftime('%Y-%m-%d %H:%M')}"
            )
            await callback.message.answer(profile_text)
        else:
            await callback.message.answer("❌ لم يتم العثور على بياناتك")
        await callback.answer()
        return
    
    # معالجة عرض مقاطع المستخدم
    if data == "my_clips":
        clips = db.get_user_clips(user.id, limit=5)
        if clips:
            clips_text = "📋 <b>آخر مقاطعك المستخرجة</b>\n\n"
            for i, clip in enumerate(clips, 1):
                keywords = json.loads(clip.keywords_found) if clip.keywords_found else []
                clips_text += (
                    f"{i}. 🔑 {', '.join(keywords[:3])}\n"
                    f"   📅 {clip.created_at.strftime('%Y-%m-%d %H:%M')}\n"
                )
            await callback.message.answer(clips_text)
        else:
            await callback.message.answer(
                "📋 <b>لم تقم باستخراج أي مقاطع بعد</b>\n\n"
                "💡 أرسل رابط فيديو لبدء الاستخراج"
            )
        await callback.answer()
        return
    
    # معالجة اختيار كلمة مفتاحية
    if data.startswith("keyword_"):
        keyword = data.replace("keyword_", "")
        await callback.answer(
            f"🔍 تم اختيار الكلمة: {keyword}\n"
            "📤 أرسل رابط فيديو لبدء المعالجة",
            show_alert=True
        )
        # تعيين حالة انتظار الرابط
        await state.set_state(ProcessState.waiting_for_url)
        return
    
    # معالجة تحديث الكلمات المفتاحية
    if data == "refresh_keywords":
        keyboard = get_keyword_keyboard()
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await callback.answer("🔄 تم تحديث قائمة الكلمات المفتاحية")
        return
    
    # أي ضغط آخر
    await callback.answer("⚠️ إجراء غير معروف")


# ============================================
# تشغيل البوت
# ============================================

async def main() -> None:
    """
    الدالة الرئيسية لتشغيل البوت
    """
    logger.info("="*50)
    logger.info("Starting Islamic Podcast Bot")
    logger.info("="*50)
    logger.info(f"Bot Token: {Config.BOT_TOKEN[:10]}...")
    logger.info(f"Channel: {Config.CHANNEL_USERNAME}")
    logger.info(f"Admin ID: {Config.ADMIN_ID}")
    logger.info(f"Keywords count: {len(Config.KEYWORDS)}")
    logger.info("="*50)
    
    # إنشاء مجلد للملفات المؤقتة
    os.makedirs(Config.TEMP_DIR, exist_ok=True)
    
    try:
        # بدء البوت
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
    finally:
        await bot.session.close()
        logger.info("Bot session closed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot terminated by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        sys.exit(1)
