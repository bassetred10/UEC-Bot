import asyncio
import os
import json
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramForbiddenError

TOKEN = os.getenv('TOKEN', '8290675844:AAEM4wRNEgIE1-feTaYcK_RsgZFywKWtZ0o')
CHANNEL_ID = "https://t.me/uec_u" # حط هنا يوزر قناتك
ADMIN_ID = 6046274404 # حط هنا الـ ID تاعك (الادمن)

bot = Bot(token=TOKEN)
dp = Dispatcher()
DATA_FILE = "stats.json"

# --- نظام الإحصائيات ---
def load_stats():
    if not os.path.exists(DATA_FILE): return {"users": [], "blocked": 0, "used": 0}
    with open(DATA_FILE, "r") as f: return json.load(f)

def save_stats(stats):
    with open(DATA_FILE, "w") as f: json.dump(stats, f)

# --- فحص الاشتراك ---
async def is_subscribed(user_id):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status not in ["left", "kicked"]
    except: return False

# --- Web Server ---
async def handle(request): return web.Response(text="Bot is running!")
async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()

@dp.message(Command("start"))
async def start(message: Message):
    stats = load_stats()
    if message.from_user.id not in stats["users"]:
        stats["users"].append(message.from_user.id)
        save_stats(stats)
    
    if not await is_subscribed(message.from_user.id):
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="اشترك في القناة 📢", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}")]])
        await message.answer("عذراً، يجب الاشتراك في القناة لاستخدام البوت:", reply_markup=kb)
        return
    
    await message.answer("مرحباً بك في بوت بودكاست الديني. أرسل رابط الفيديو للبدء! 🎥")

@dp.message(Command("stats"))
async def show_stats(message: Message):
    if message.from_user.id != ADMIN_ID: return
    stats = load_stats()
    await message.answer(f"📊 **إحصائيات البوت:**\n\n👥 عدد المستخدمين: {len(stats['users'])}\n🔥 عدد عمليات الاستخراج: {stats['used']}")

@dp.message(F.text.startswith("http"))
async def handle_url(message: Message):
    if not await is_subscribed(message.from_user.id):
        await message.answer("⚠️ اشترك في القناة أولاً!")
        return
    
    # تحديث الاستخدام
    stats = load_stats()
    stats["used"] += 1
    save_stats(stats)
    
    url = message.text
    builder = InlineKeyboardBuilder()
    for i in range(4):
        builder.button(text=f"▶️ المقطع {i+1}", callback_data=f"clip|{i*5}:00|{url}")
    builder.adjust(1)
    await message.answer("✅ تم استلام الرابط. اختر المقطع:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("clip"))
async def send_clip(callback: CallbackQuery):
    msg = await callback.message.edit_text("⏳ جاري المعالجة...")
    _, time, url = callback.data.split("|")
    # ... (باقي كود التحميل والمعالجة كما في الكود السابق) ...
    await callback.message.delete()

async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
