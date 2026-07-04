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

# ============================================
# إعداد نظام التسجيل (Logging)
# ============================================

# إنشاء مجلد السجلات
os.makedirs('logs', exist_ok=True)

logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL if hasattr(Config, 'LOG_LEVEL') else 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log', encoding='utf-8'),
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

# التحقق من صحة الإعدادات
if not validate_config():
    logger.error("Configuration validation failed")
    # استمرار التشغيل حتى مع وجود أخطاء (لـ Render)
    logger.warning("Continuing despite validation errors...")

# التحقق من تثبيت المتطلبات (تجاوز في Render)
try:
    if not check_requirements():
        logger.warning("Some requirements missing, but continuing...")
except Exception as e:
    logger.warning(f"Requirements check failed: {e}")

# تهيئة البوت
try:
    bot = Bot(
        token=Config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # تهيئة معالج الفيديو
    processor = VideoProcessor()
    
    logger.info("Bot initialized successfully")
    
except Exception as e:
    logger.error(f"Failed to initialize bot: {e}")
    sys.exit(1)

# ============================================
# دوال مساعدة
# ============================================

async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(
            chat_id=Config.CHANNEL_ID,
            user_id=user_id
        )
        is_subscribed = member.status in ['member', 'administrator', 'creator']
        return is_subscribed
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

def get_keyword_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    row = []
    
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
    
    buttons.append([
        InlineKeyboardButton(
            text="🔄 تحديث الكلمات",
            callback_data="refresh_keywords"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ============================================
# معالجات الأوامر
# ============================================

@dp.message(CommandStart())
async def start_command(message: Message, state: FSMContext) -> None:
    user = message.from_user
    
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
    
    welcome_message = (
        "👋 <b>مرحباً بك في بوت بودكاست</b>\n\n"
        "🎙️ <i>تحويل فيديوهات البودكاست الدينية لتسهيل نشرها في مواقع التواصل الاجتماعي</i>\n\n"
        "📤 أرسل رابط الفيديو الآن وسأقوم بقص أهم الفوائد "
        "(دعاء، حديث، حكمة) لك!\n\n"
        "🔍 الكلمات المفتاحية المدعومة:\n"
        f"{', '.join(Config.KEYWORDS[:10])}..."
    )
    
    await message.answer(welcome_message, reply_markup=get_main_keyboard())
    await message.answer(
        "🔑 <b>الكلمات المفتاحية المدعومة:</b>\n"
        f"{', '.join(Config.KEYWORDS[:15])}...\n\n"
        "💡 يمكنك اختيار كلمة من الأزرار أدناه",
        reply_markup=get_keyword_keyboard()
    )
    
    await state.set_state(ProcessState.waiting_for_url)

@dp.message(Command("help"))
async def help_command(message: Message) -> None:
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
    if message.from_user.id != Config.ADMIN_ID:
        await message.answer("⛔ هذا الأمر مخصص للإدمن فقط")
        return
    
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
    user = message.from_user
    
    if not await check_subscription(user.id):
        await message.answer(
            "⚠️ يرجى الاشتراك في قناتنا أولاً",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    url = message.text.strip()
    
    if not (url.startswith('http://') or url.startswith('https://')):
        await message.answer(
            "❌ يرجى إرسال رابط صحيح للفيديو من يوتيوب\n\n"
            "مثال: https://www.youtube.com/watch?v=xxxxx"
        )
        return
    
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
                processor.cleanup_clip(clip_path)
                
            except Exception as e:
                logger.error(f"Failed to send clip {i}: {e}")
                await message.answer(f"❌ فشل إرسال المقطع {i}: {e}")
        
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
# معالجات الأزرار
# ============================================

@dp.callback_query()
async def handle_callback(callback: CallbackQuery, state: FSMContext) -> None:
    user = callback.from_user
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
                f"📅 <b>آخر نشاط:</b> {user_stats['last_activity'].strftime('%Y-%m-%d %H:%M')}"
            )
            await callback.message.answer(profile_text)
        else:
            await callback.message.answer("❌ لم يتم العثور على بياناتك")
        await callback.answer()
        return
    
    if data == "my_clips":
        clips = db.get_user_clips(user.id, limit=5)
        if clips:
            clips_text = "📋 <b>آخر مقاطعك المستخرجة</b>\n\n"
            for i, clip in enumerate(clips, 1):
                import json
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
    
    if data.startswith("keyword_"):
        keyword = data.replace("keyword_", "")
        await callback.answer(
            f"🔍 تم اختيار الكلمة: {keyword}\n"
            "📤 أرسل رابط فيديو لبدء المعالجة",
            show_alert=True
        )
        await state.set_state(ProcessState.waiting_for_url)
        return
    
    if data == "refresh_keywords":
        keyboard = get_keyword_keyboard()
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await callback.answer("🔄 تم تحديث قائمة الكلمات المفتاحية")
        return
    
    await callback.answer("⚠️ إجراء غير معروف")

# ============================================
# تشغيل البوت
# ============================================

async def main() -> None:
    logger.info("="*50)
    logger.info("Starting Islamic Podcast Bot on Render")
    logger.info("="*50)
    logger.info(f"Bot Token: {Config.BOT_TOKEN[:10]}...")
    logger.info(f"Channel: {Config.CHANNEL_USERNAME}")
    logger.info(f"Admin ID: {Config.ADMIN_ID}")
    logger.info(f"Keywords count: {len(Config.KEYWORDS)}")
    logger.info("="*50)
    
    os.makedirs(Config.TEMP_DIR, exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    
    try:
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
