import os, random, asyncio, subprocess, logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile

# --- الإعدادات ---
TOKEN = "8290675844:AAEM4wRNEgIE1-feTaYcK_RsgZFywKWtZ0o"
ADMIN_ID = 6046274404 
CHANNEL_ID = "@uec_u"

# --- الحماية: تفعيل السجلات (Logging) ---
logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- دالة الحماية من الأوامر غير المصرح بها ---
def is_admin(user_id):
    return user_id == ADMIN_ID

# --- نظام الحماية ضد "الفلود" (الطلبات الكثيرة) ---
user_last_action = {}
async def rate_limit(user_id):
    if user_id in user_last_action:
        if asyncio.get_event_loop().time() - user_last_action[user_id] < 5:
            return False
    user_last_action[user_id] = asyncio.get_event_loop().time()
    return True

# --- كود البوت المحسن ---
@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer("مرحباً بك في UEC NETWORK.\nأرسل رابط يوتيوب لتحميل وقص الفيديو بجودة HD.")

@dp.message(F.text.startswith("http"))
async def handle_link(msg: types.Message):
    # تطبيق حماية السرعة
    if not await rate_limit(msg.from_user.id):
        await msg.answer("❌ مهلاً! أنت ترسل طلبات بسرعة كبيرة، انتظر قليلاً.")
        return

    # فحص الاشتراك
    try:
        m = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=msg.from_user.id)
        if m.status not in ["member", "administrator", "creator"]:
            await msg.answer(f"❌ اشترك في القناة أولاً: {CHANNEL_ID}")
            return
    except: return

    url = msg.text
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ البداية", callback_data=f"c:start:{url}"),
         InlineKeyboardButton(text="🔹 ربع أول", callback_data=f"c:q1:{url}")],
        [InlineKeyboardButton(text="🔸 ربع ثاني", callback_data=f"c:q2:{url}"),
         InlineKeyboardButton(text="⏹ النهاية", callback_data=f"c:end:{url}")]
    ])
    await msg.answer("🎬 اختر الجزء:", reply_markup=kb)

@dp.callback_query(F.data.startswith("c:"))
async def cutter(call: types.CallbackQuery):
    _, part, url = call.data.split(":", 2)
    # حماية من التلاعب بالبيانات: التحقق من الرابط
    if "youtube.com" not in url and "youtu.be" not in url:
        await call.answer("❌ رابط غير صالح!")
        return

    status = await call.message.edit_text("⏳ جاري المعالجة...")
    try:
        # تنفيذ العملية بذكاء
        cmd = f"yt-dlp -f 'bestvideo[height<=1080]+bestaudio' --merge-output-format mp4 -o - '{url}' | ffmpeg -y -i pipe:0 -ss 00:00:05 -t 15 -c:v libx264 -preset ultrafast -crf 20 -c:a copy out.mp4"
        subprocess.run(cmd, shell=True)
        await call.message.answer_video(video=FSInputFile("out.mp4"), caption="✅ UEC NETWORK")
        os.remove("out.mp4")
        await status.delete()
    except:
        await status.edit_text("❌ حدث خطأ داخلي.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
