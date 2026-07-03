import os
import subprocess
import tempfile
import whisper
import ffmpeg
from typing import List, Tuple, Optional
import json
import asyncio
from pydub import AudioSegment
import re

class VideoProcessor:
    def __init__(self, cookies_file: str = None):
        self.cookies_file = cookies_file
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """تحميل نموذج Whisper"""
        try:
            self.model = whisper.load_model("base")  # يمكن تغيير إلى tiny, base, small, medium, large
            print("Whisper model loaded successfully")
        except Exception as e:
            print(f"Error loading Whisper model: {e}")
    
    async def download_video(self, url: str) -> str:
        """تحميل الفيديو باستخدام yt-dlp"""
        temp_dir = tempfile.mkdtemp()
        output_path = os.path.join(temp_dir, 'video.mp4')
        
        cmd = [
            'yt-dlp',
            '-f', 'best[ext=mp4]',
            '-o', output_path,
            '--no-playlist',
            '--extract-audio',
            '--audio-format', 'mp3',
            '--audio-quality', '0',
        ]
        
        if self.cookies_file and os.path.exists(self.cookies_file):
            cmd.extend(['--cookies', self.cookies_file])
        
        cmd.append(url)
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise Exception(f"yt-dlp failed: {stderr.decode()}")
            
            # البحث عن ملف mp3
            audio_file = output_path.replace('.mp4', '.mp3')
            if not os.path.exists(audio_file):
                # محاولة العثور على أي ملف mp3 في المجلد
                for file in os.listdir(temp_dir):
                    if file.endswith('.mp3'):
                        audio_file = os.path.join(temp_dir, file)
                        break
            
            return audio_file
        except Exception as e:
            raise Exception(f"Download error: {e}")
    
    def extract_audio_text(self, audio_path: str) -> dict:
        """استخراج النص من الصوت مع التوقيت"""
        try:
            result = self.model.transcribe(audio_path)
            return result
        except Exception as e:
            raise Exception(f"Transcription error: {e}")
    
    def find_keywords(self, transcription: dict, keywords: List[str]) -> List[dict]:
        """البحث عن الكلمات المفتاحية في النص"""
        found_segments = []
        segments = transcription['segments']
        
        for segment in segments:
            text = segment['text']
            # البحث عن الكلمات المفتاحية
            for keyword in keywords:
                if keyword.lower() in text.lower():
                    # إضافة مدة قصيرة قبل وبعد المقطع
                    start = max(0, segment['start'] - 1)  # ثانية قبل
                    end = min(transcription['duration'], segment['end'] + 1)  # ثانية بعد
                    
                    # تمديد المقطع إذا كانت الكلمة في بداية أو نهاية المقطع
                    if segment['start'] == 0:
                        start = 0
                    
                    found_segments.append({
                        'keyword': keyword,
                        'text': text,
                        'start': start,
                        'end': end,
                        'duration': end - start
                    })
                    break  # نأخذ أول كلمة مفتاحية في المقطع
        
        return found_segments
    
    async def extract_clip(self, audio_path: str, start: float, end: float) -> str:
        """استخراج مقطع من الصوت"""
        try:
            temp_dir = tempfile.mkdtemp()
            output_path = os.path.join(temp_dir, f'clip_{start}_{end}.mp3')
            
            # استخدام ffmpeg لقص المقطع
            (
                ffmpeg
                .input(audio_path, ss=start, to=end)
                .output(output_path)
                .overwrite_output()
                .run(quiet=True)
            )
            
            return output_path
        except Exception as e:
            raise Exception(f"Clip extraction error: {e}")
    
    async def process_video(self, url: str, keywords: List[str]) -> Tuple[List[dict], List[str]]:
        """معالجة الفيديو بالكامل"""
        try:
            # تحميل الفيديو
            audio_path = await self.download_video(url)
            
            # استخراج النص
            transcription = self.extract_audio_text(audio_path)
            
            # البحث عن الكلمات المفتاحية
            segments = self.find_keywords(transcription, keywords)
            
            # استخراج المقاطع
            clips = []
            for segment in segments[:5]:  # حد أقصى 5 مقاطع
                clip_path = await self.extract_clip(
                    audio_path, 
                    segment['start'], 
                    segment['end']
                )
                clips.append(clip_path)
            
            # تنظيف الملفات المؤقتة
            # os.remove(audio_path)  # يمكن تفعيله لتنظيف الملفات
            
            return segments, clips
        except Exception as e:
            raise Exception(f"Processing error: {e}")

# bot.py
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
import asyncio
import logging
from datetime import datetime
import json
import os

from config import Config
from database import Database
from processor import VideoProcessor

# إعداد التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# تهيئة البوت
bot = Bot(
    token=Config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# تهيئة قاعدة البيانات والمعالج
db = Database()
processor = VideoProcessor(cookies_file=Config.COOKIES_FILE)

# حالات FSM
class ProcessState(StatesGroup):
    waiting_for_url = State()

# دوال مساعدة
def get_main_keyboard() -> InlineKeyboardMarkup:
    """إنشاء لوحة المفاتيح الرئيسية"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📊 الإحصائيات", 
                callback_data="stats"
            ),
            InlineKeyboardButton(
                text="ℹ️ المساعدة", 
                callback_data="help"
            )
        ],
        [
            InlineKeyboardButton(
                text="👤 ملفي الشخصي", 
                callback_data="profile"
            )
        ]
    ])
    return keyboard

def get_keyword_keyboard() -> InlineKeyboardMarkup:
    """إنشاء لوحة مفاتيح الكلمات المفتاحية"""
    buttons = []
    row = []
    for i, keyword in enumerate(Config.KEYWORDS[:6]):  # عرض 6 كلمات
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

async def check_subscription(user_id: int) -> bool:
    """التحقق من اشتراك المستخدم في القناة"""
    try:
        member = await bot.get_chat_member(
            chat_id=Config.CHANNEL_ID, 
            user_id=user_id
        )
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Subscription check error: {e}")
        return False

# معالجات الأوامر
@dp.message(CommandStart())
async def start_command(message: Message):
    """معالجة أمر /start"""
    user = message.from_user
    
    # إضافة المستخدم إلى قاعدة البيانات
    db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    # التحقق من الاشتراك
    if not await check_subscription(user.id):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 اشترك في القناة",
                    url=f"https://t.me/{Config.CHANNEL_USERNAME[1:]}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ تحقق من الاشتراك",
                    callback_data="check_subscription"
                )
            ]
        ])
        await message.answer(
            f"👋 مرحبا بك في <b>بوت بودكاست</b>\n\n"
            f"للاستفادة من خدمات البوت، يرجى الاشتراك في قناتنا أولاً 📢",
            reply_markup=keyboard
        )
        return
    
    # رسالة الترحيب
    await message.answer(
        f"👋 <b>مرحباً بك في بوت بودكاست</b>\n\n"
        f"🎙️ <i>تحويل فيديوهات البودكاست الدينية لتسهيل نشرها في مواقع التواصل الاجتماعي</i>\n\n"
        f"📤 أرسل رابط الفيديو الآن وسأقوم بقص أهم الفوائد "
        f"(دعاء، حديث، حكمة) لك!\n\n"
        f"🔍 الكلمات المفتاحية المدعومة:\n"
        f"{', '.join(Config.KEYWORDS[:10])}...",
        reply_markup=get_main_keyboard()
    )

@dp.message(Command("stats"))
async def stats_command(message: Message):
    """معالجة أمر /stats - للإدمن فقط"""
    if message.from_user.id != Config.ADMIN_ID:
        await message.answer("⛔ هذا الأمر مخصص للإدمن فقط")
        return
    
    users_count, clips_count = db.get_stats()
    
    stats_text = (
        f"📊 <b>إحصائيات البوت</b>\n\n"
        f"👥 عدد المستخدمين: <b>{users_count}</b>\n"
        f"🎬 المقاطع المستخرجة: <b>{clips_count}</b>\n"
        f"📅 آخر تحديث: <b>{datetime.now().strftime('%Y-%m-%d %H:%M')}</b>"
    )
    
    await message.answer(stats_text)

@dp.message(Command("help"))
async def help_command(message: Message):
    """معالجة أمر /help"""
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

@dp.message()
async def handle_url(message: Message):
    """معالجة الروابط المرسلة"""
    user = message.from_user
    
    # التحقق من الاشتراك
    if not await check_subscription(user.id):
        await message.answer(
            "⚠️ يرجى الاشتراك في قناتنا أولاً @uec_u",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📢 اشترك الآن",
                        url="https://t.me/uec_u"
                    )
                ]
            ])
        )
        return
    
    # التحقق من الرابط
    url = message.text.strip()
    if not (url.startswith('http://') or url.startswith('https://')):
        await message.answer(
            "❌ يرجى إرسال رابط صحيح للفيديو من يوتيوب"
        )
        return
    
    # إرسال رسالة المعالجة
    processing_msg = await message.answer(
        "🔄 جاري تحميل وتحليل الفيديو...\n"
        "⏳ قد يستغرق هذا بعض الوقت"
    )
    
    try:
        # معالجة الفيديو
        segments, clips = await processor.process_video(url, Config.KEYWORDS)
        
        if not segments:
            await processing_msg.edit_text(
                "❌ لم يتم العثور على كلمات مفتاحية دينية في هذا الفيديو"
            )
            return
        
        # إرسال النتائج
        await processing_msg.edit_text(
            f"✅ تم العثور على {len(segments)} مقطع ديني!\n"
            f"🎥 جاري تحميل المقاطع..."
        )
        
        # إرسال المقاطع
        for i, (segment, clip_path) in enumerate(zip(segments, clips)):
            caption = (
                f"🎬 <b>المقطع {i+1}</b>\n\n"
                f"🔑 الكلمة المفتاحية: <b>{segment['keyword']}</b>\n"
                f"⏱️ التوقيت: {segment['start']:.2f} - {segment['end']:.2f} ثانية\n\n"
                f"📝 النص:\n<code>{segment['text'][:200]}...</code>"
            )
            
            # إرسال المقطع الصوتي
            with open(clip_path, 'rb') as audio:
                await message.answer_audio(
                    audio,
                    caption=caption,
                    performer="بودكاست",
                    title=f"مقطع ديني {i+1}"
                )
            
            # تنظيف الملفات
            os.remove(clip_path)
            
            # تحديث الإحصائيات
            db.increment_clips(user.id)
            db.add_clip(user.id, url, clip_path, [segment['keyword']])
        
        await processing_msg.edit_text(
            "✅ تم الانتهاء من استخراج جميع المقاطع!\n"
            "🔗 يمكنك مشاركتها في مواقع التواصل الاجتماعي"
        )
        
    except Exception as e:
        logger.error(f"Processing error: {e}")
        await processing_msg.edit_text(
            f"❌ حدث خطأ أثناء المعالجة:\n<code>{str(e)}</code>\n\n"
            "يرجى المحاولة مرة أخرى أو الاتصال بالدعم"
        )

# معالجات الكولباك
@dp.callback_query()
async def handle_callback(callback: CallbackQuery):
    """معالجة ضغطات الأزرار"""
    user = callback.from_user
    
    if callback.data == "check_subscription":
        if await check_subscription(user.id):
            await callback.message.delete()
            await start_command(callback.message)
        else:
            await callback.answer(
                "⚠️ لم يتم الاشتراك بعد، يرجى الاشتراك أولاً",
                show_alert=True
            )
    
    elif callback.data == "stats":
        if user.id == Config.ADMIN_ID:
            await stats_command(callback.message)
        else:
            await callback.answer("⛔ هذا الأمر مخصص للإدمن فقط")
    
    elif callback.data == "help":
        await help_command(callback.message)
    
    elif callback.data == "profile":
        user_data = f"""
👤 <b>بيانات المستخدم</b>

🆔 ID: <code>{user.id}</code>
📛 الاسم: {user.first_name} {user.last_name or ''}
👤 المعرف: @{user.username or 'غير موجود'}
📅 تاريخ الانضمام: {datetime.now().strftime('%Y-%m-%d %H:%M')}
        """
        await callback.message.answer(user_data)
    
    elif callback.data.startswith("keyword_"):
        keyword = callback.data.replace("keyword_", "")
        await callback.answer(
            f"🔍 تم اختيار الكلمة: {keyword}\n"
            "أرسل رابط فيديو لبدء المعالجة",
            show_alert=True
        )
    
    elif callback.data == "refresh_keywords":
        keyboard = get_keyword_keyboard()
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await callback.answer("🔄 تم تحديث قائمة الكلمات")
    
    await callback.answer()

# تشغيل البوت
async def main():
    """تشغيل البوت"""
    logger.info("Starting bot...")
    
    # إنشاء مجلد للملفات المؤقتة
    os.makedirs('temp', exist_ok=True)
    
    # تشغيل البوت
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
