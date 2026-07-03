import asyncio
import os
import json
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

TOKEN = os.getenv('TOKEN', '8290675844:AAEM4wRNEgIE1-feTaYcK_RsgZFywKWtZ0o')
CHANNEL_ID = -1004304853750  # الـ ID اللي عطيتوهولي
ADMIN_ID = 765432109        # حط الـ ID تاعك هنا

bot = Bot(token=TOKEN)
dp = Dispatcher()
DATA_FILE = "stats.json"

def load_stats():
    if not os.path.exists(DATA_FILE): return {"users": [], "used": 0}
    with open(DATA_FILE, "r") as f: return json.load(f)

def save_stats(stats):
    with open(DATA_FILE, "w") as f: json.dump(stats, f)

async def is_subscribed(user_id):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except: return False

@dp.message(Command("start"))
async def start(message: Message):
    stats = load_stats()
    if message.from_user.id not in stats["users"]:
        stats["users"].append(message.from_user.id)
        save_stats(stats)
    
    if not await is_subscribed(message.from_user.id):
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="اشترك في القناة 📢", url="https://t.me/uec_u")]])
        await message.answer("⚠️ يجب الاشتراك في القناة لاستخدام البوت:", reply_markup=kb)
        return
    
    await message.answer("أهلاً بك يا أبو جرير! أرسل رابط الفيديو للبدء. 🎥")

@dp.message(Command("stats"))
async def show_stats(message: Message):
    if message.from_user.id != ADMIN_ID: return
    stats = load_stats()
    await message.answer(f"📊 **إحصائيات البوت:**\n👥 عدد المستخدمين: {len(stats['users'])}\n🔥 عدد عمليات التحميل: {stats['used']}")

@dp.message(F.text.startswith("http"))
async def handle_url(message: Message):
    if not await is_subscribed(message.from_user.id):
        await message.answer("⚠️ اشترك في القناة أولاً لتتمكن من التحميل!")
        return
    
    stats = load_stats()
    stats["used"] += 1
    save_stats(stats)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="▶️ استخراج المقطع", callback_data=f"clip|00:00:00|{message.text}")
    await message.answer("✅ تم قبول الرابط، اضغط للبدء:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("clip"))
async def send_clip(callback: CallbackQuery):
    await callback.message.edit_text("⏳ جاري المعالجة...")
    _, time, url = callback.data.split("|")
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    download_cmd = f'yt-dlp --user-agent "{user_agent}" -f "best[ext=mp4][height<=720]" -o "raw.mp4" "{url}"'
    
    if os.system(download_cmd) == 0:
        os.system(f'ffmpeg -i raw.mp4 -ss {time} -t 60 -vf scale=1280:720 -preset ultrafast -c:v libx264 -c:a aac -y final.mp4')
        await callback.message.answer_video(video=FSInputFile("final.mp4"), caption="🎥 تم المقطع!")
        await callback.message.delete()
    else:
        await callback.message.edit_text("❌ خطأ في تحميل الفيديو.")

async def main():
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="Bot is running!"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', 10000).start()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
