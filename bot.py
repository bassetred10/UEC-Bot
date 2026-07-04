import os
import sys
import logging
import asyncio
import threading
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

from config import Config, validate_config
from database import db
from processor import VideoProcessor, check_requirements
from security import security_manager
from keep_alive import keep_alive_manager

# ============================================
# إعداد نظام التسجيل
# ============================================

os.makedirs('logs', exist_ok=True)

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
# تعريف حالات FSM
# ============================================

class ProcessState(StatesGroup):
    waiting_for_url = State()


# ============================================
# تهيئة البوت والمعالجات
# ============================================

if not validate_config():
    logger.error("Configuration validation failed")
    sys.exit(1)

try:
    if not check_requirements():
        logger.warning("Some requirements missing, but continuing...")
except Exception as e:
    logger.warning(f"Requirements check failed: {e}")

try:
    bot = Bot(
        token=Config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    processor = VideoProcessor()
    
    logger.info("Bot initialized successfully")
    
except Exception as e:
    logger.error(f"Failed to initialize bot: {e}")
    sys.exit(1)


# ============================================
# دالة Health Check
# ============================================

def run_health_check():
    """تشغيل خادم Health Check"""
    try:
        from health import run_health_server
        threading.Thread(target=run_health_server, daemon=True).start()
        logger.info("✅ Health check server started")
    except Exception as e:
        logger.warning(f"⚠️ Health check server failed: {e}")


# ============================================
# دوال مساعدة
# ============================================

async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(
            chat_id=Config.CHANNEL_ID,
            user_id=user_id
        )
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Subscription check error: {e}")
        return False

def get_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 الإحصائيات", callback_data="stats"),
            InlineKeyboardButton(text="ℹ️ المساعدة", callback_data="help")
        ],
        [
            InlineKeyboardButton(text="👤 ملفي الشخصي", callback_data="profile"),
            InlineKeyboardButton(text="📋 مقاطعي", callback_data="my_clips")
        ],
        [
            InlineKeyboardButton(text="🔒 الأمان", callback_data="security_info")
        ]
    ])

def get_subscription_keyboard() -> InlineKeyboardMarkup:
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


# ============================================
# معالجات الأوامر
# ============================================

@dp.message(CommandStart())
async def start_command(message: Message, state: FSMContext) -> None:
    user = message.from_user
    
    if security_manager.is_user_blacklisted(user.id):
        await message.answer("⛔ <b>تم حظر حسابك</b>")
        return
    
    allowed, error_msg = security_manager.check_rate_limit(user.id)
    if not allowed:
        await message.answer(error_msg)
        return
    
    logger.info(f"User {user.id} (@{user.username}) started the bot")
    
    db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    if not await check_subscription(user.id):
        await message.answer(
            "👋 مرحبا بك في <b>بوت بودكاست</b>\n\n"
            "للاستفادة من خدمات البوت، يرجى الاشتراك في قناتنا أولاً 📢",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    await message.answer(Config.WELCOME_MESSAGE, reply_markup=get_main_keyboard())
    await state.set_state(ProcessState.waiting_for_url)


@dp.message(Command("help"))
async def help_command(message: Message) -> None:
    user = message.from_user
    
    if security_manager.is_user_blacklisted(user.id):
        await message.answer("⛔ تم حظر حسابك")
        return
    
    allowed, _ = security_manager.check_rate_limit(user.id)
    if not allowed:
        return
    
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
        "🔒 <b>الأمان:</b>\n"
        "• نظام حماية من الهجمات\n"
        "• تحديد معدل الطلبات\n"
        "• مكافحة البريد العشوائي\n\n"
        "📢 <b>قناتنا:</b> @uec_u"
    )
    await message.answer(help_text, reply_markup=get_main_keyboard())


@dp.message(Command("stats"))
async def stats_command(message: Message) -> None:
    user = message.from_user
    
    if user.id != Config.ADMIN_ID:
        await message.answer("⛔ هذا الأمر مخصص للإدمن فقط")
        return
    
    users_count, clips_count = db.get_stats()
    
    stats_text = (
        f"📊 <b>إحصائيات البوت</b>\n\n"
        f"👥 عدد المستخدمين: <b>{users_count:,}</b>\n"
        f"🎬 المقاطع المستخرجة: <b>{clips_count:,}</b>\n"
        f"⏱️ وقت التشغيل: <b>{datetime.now().strftime('%Y-%m-%d %H:%M')}</b>\n\n"
        f"🔒 <b>حالة الأمان:</b>\n"
        f"• Rate Limit: {'مفعل' if Config.ENABLE_RATE_LIMIT else 'معطل'}\n"
        f"• Anti-Spam: {'مفعل' if Config.ENABLE_ANTI_SPAM else 'معطل'}\n"
        f"• المستخدمين المحظورين: {len([u for u in security_manager.user_activities.values() if u.is_blacklisted])}\n\n"
        f"⚙️ <b>الإعدادات:</b>\n"
        f"• نموذج Whisper: {Config.WHISPER_MODEL}\n"
        f"• الحد الأقصى للمقاطع: {Config.MAX_CLIPS}"
    )
    
    await message.answer(stats_text)


@dp.message(StateFilter(ProcessState.waiting_for_url))
async def handle_url(message: Message, state: FSMContext) -> None:
    user = message.from_user
    
    if security_manager.is_user_blacklisted(user.id):
        await message.answer("⛔ تم حظر حسابك")
        return
    
    allowed, error_msg = security_manager.check_rate_limit(user.id)
    if not allowed:
        await message.answer(error_msg)
        return
    
    allowed, error_msg = security_manager.check_anti_spam(user.id, message.text)
    if not allowed:
        await message.answer(error_msg)
        return
    
    if not await check_subscription(user.id):
        await message.answer(
            "⚠️ يرجى الاشتراك في قناتنا أولاً",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    url = message.text.strip()
    
    safe, error_msg = security_manager.check_url_safety(url)
    if not safe:
        await message.answer(error_msg)
        return
    
    allowed, error_msg = security_manager.check_clip_limit(user.id)
    if not allowed:
        await message.answer(error_msg)
        return
    
    processing_msg = await message.answer(
        "🔄 <b>جاري تحميل وتحليل الفيديو...</b>\n"
        "⏳ قد يستغرق هذا بعض الوقت (حتى 5 دقائق)\n"
        "🔒 <i>نظام الأمان نشط - يتم مراقبة جميع العمليات</i>"
    )
    
    try:
        logger.info(f"Processing video for user {user.id}: {url}")
        segments, clips = await processor.process_video(url, Config.KEYWORDS)
        
        if not segments:
            await processing_msg.edit_text(
                "❌ <b>لم يتم العثور على كلمات مفتاحية دينية</b>\n\n"
                "💡 حاول استخدام فيديو آخر يحتوي على:\n"
                f"• {', '.join(Config.KEYWORDS[:5])}"
            )
            return
        
        await processing_msg.edit_text(
            f"✅ <b>تم العثور على {len(segments)} مقطع ديني!</b>\n"
            f"🎥 <i>جاري تحميل المقاطع...</i>"
        )
        
        for i, (segment, clip_path) in enumerate(zip(segments, clips), 1):
            keywords_text = ', '.join(segment['keywords'])
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
                with open(clip_path, 'rb') as audio_file:
                    await message.answer_audio(
                        audio_file,
                        caption=caption,
                        performer="بودكاست ديني",
                        title=f"مقطع ديني {i}"
                    )
                
                db.add_clip(
                    user_id=user.id,
                    video_url=url,
                    clip_path=clip_path,
                    keywords=segment['keywords'],
                    start_time=segment['start'],
                    end_time=segment['end']
                )
                db.increment_clips(user.id)
                security_manager.increment_clip_count(user.id)
                processor.cleanup_clip(clip_path)
                
            except Exception as e:
                logger.error(f"Failed to send clip {i}: {e}")
                await message.answer(f"❌ فشل إرسال المقطع {i}: {e}")
        
        await processing_msg.edit_text(
            "✅ <b>تم الانتهاء من استخراج جميع المقاطع!</b>\n\n"
            "🔗 يمكنك مشاركة هذه المقاطع في مواقع التواصل الاجتماعي\n"
            "🔒 <i>جميع العمليات مراقبة بأمان</i>"
        )
        
    except Exception as e:
        logger.error(f"Processing error for user {user.id}: {e}")
        await processing_msg.edit_text(
            f"❌ <b>حدث خطأ أثناء المعالجة</b>\n\n"
            f"<code>{str(e)}</code>\n\n"
            "💡 نصائح:\n"
            "• تأكد من صحة الرابط\n"
            "• حاول مرة أخرى بعد قليل"
        )


# ============================================
# معالجات الأزرار
# ============================================

@dp.callback_query()
async def handle_callback(callback: CallbackQuery, state: FSMContext) -> None:
    user = callback.from_user
    
    if security_manager.is_user_blacklisted(user.id):
        await callback.answer("⛔ تم حظر حسابك", show_alert=True)
        return
    
    allowed, _ = security_manager.check_rate_limit(user.id)
    if not allowed:
        await callback.answer("⚠️ تجاوزت حد الطلبات", show_alert=True)
        return
    
    data = callback.data
    
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
    
    if data == "stats":
        if user.id == Config.ADMIN_ID:
            await stats_command(callback.message)
        else:
            await callback.answer("⛔ هذا الأمر مخصص للإدمن فقط")
        await callback.answer()
        return
    
    if data == "help":
        await help_command(callback.message)
        await callback.answer()
        return
    
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
                f"📅 <b>آخر نشاط:</b> {user_stats['last_activity'].strftime('%Y-%m-%d %H:%M')}\n\n"
                f"🔒 <b>حالة الأمان:</b>\n"
                f"• محظور: {'نعم' if security_manager.is_user_blacklisted(user.id) else 'لا'}"
            )
            await callback.message.answer(profile_text)
        else:
            await callback.message.answer("❌ لم يتم العثور على بياناتك")
        await callback.answer()
        return
    
    if data == "my_clips":
        clips = db.get_user_clips(user.id, limit=5)
        if clips:
            import json
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
    
    if data == "security_info":
        security_text = (
            "🔒 <b>معلومات الأمان</b>\n\n"
            "🛡️ <b>أنظمة الحماية المطبقة:</b>\n\n"
            "1️⃣ <b>معدل الطلبات</b>\n"
            f"   • الحد الأقصى: {Config.MAX_REQUESTS_PER_MINUTE} طلب في الدقيقة\n\n"
            "2️⃣ <b>مكافحة البريد العشوائي</b>\n"
            f"   • الحد الأقصى: {Config.MAX_SIMILAR_MESSAGES} رسائل متشابهة\n\n"
            "3️⃣ <b>حماية الروابط</b>\n"
            "   • فقط روابط يوتيوب مسموحة\n\n"
            "4️⃣ <b>الحد اليومي</b>\n"
            f"   • {Config.MAX_CLIPS_PER_USER_DAY} مقطع في اليوم\n\n"
            "⚙️ <b>إعدادات الأداء:</b>\n"
            f"• نموذج Whisper: {Config.WHISPER_MODEL} (موفر للذاكرة)\n"
            f"• الحد الأقصى للمقاطع: {Config.MAX_CLIPS}\n\n"
            "✅ <i>جميع العمليات مراقبة ومسجلة</i>"
        )
        await callback.message.answer(security_text)
        await callback.answer()
        return
    
    if data.startswith("keyword_"):
        keyword = data.replace("keyword_", "")
        await callback.answer(
            f"🔍 تم اختيار الكلمة: {keyword}\n"
            "📤 أرسل رابط فيديو لبدء المعالجة",
            show_alert=True
        )
        await state.set_state(ProcessState.waiting_for_url)
        return


# ============================================
# الدالة الرئيسية
# ============================================

async def main() -> None:
    logger.info("="*50)
    logger.info("🛡️ Starting Islamic Podcast Bot with Security")
    logger.info("="*50)
    logger.info(f"Bot Token: {Config.BOT_TOKEN[:10]}...")
    logger.info(f"Channel: {Config.CHANNEL_USERNAME}")
    logger.info(f"Admin ID: {Config.ADMIN_ID}")
    logger.info(f"Keywords: {len(Config.KEYWORDS)} words")
    logger.info(f"Whisper Model: {Config.WHISPER_MODEL} (Memory Optimized)")
    logger.info(f"Max Clips: {Config.MAX_CLIPS}")
    logger.info("="*50)
    
    os.makedirs(Config.TEMP_DIR, exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    
    run_health_check()
    await keep_alive_manager.start()
    
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
    finally:
        await keep_alive_manager.stop()
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
