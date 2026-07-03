import asyncio
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

# إعدادات البوت
TOKEN = '8290675844:AAEM4wRNEgIE1-feTaYcK_RsgZFywKWtZ0o'
bot = Bot(token=TOKEN)
dp = Dispatcher()

# الواجهة الرسمية (نظيفة واحترافية)
HEADER = (
    "🎙️ **Smart Islamic Clips**\n\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "🤍 **أهلاً بك!**\n\n"
    "حوّل أي بودكاست أو محاضرة إلى مقطع قصير\n"
    "جاهز للنشر على TikTok وInstagram Reels\n"
    "وYouTube Shorts.\n\n"
    "⚡ **سرعة عالية**\n"
    "🎥 **جودة تصل إلى 1080P**\n"
    "✂️ **استخراج خلال ثوانٍ**\n"
    "📤 **إرسال مباشر داخل تيليجرام**\n\n"
    "اختر أحد الخيارات بالأسفل."
)

# --- Web Server لـ Render ---
async def handle(request): return web.Response(text="Bot is active and running!")
async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(HEADER)

@dp.message(F.text.startswith("http"))
async def handle_url(message: Message):
    url = message.text
    builder = InlineKeyboardBuilder()
    builder.button(text="🎬 المقطع (00:00)", callback_data=f"clip|00:00:00|{url}")
    builder.button(text="🎬 المقطع (05:00)", callback_data=f"clip|00:05:00|{url}")
    builder.button(text="🎬 المقطع (10:00)", callback_data=f"clip|00:10:00|{url}")
    builder.button(text="🎬 المقطع (15:00)", callback_data=f"clip|00:15:00|{url}")
    builder.adjust(1)
    await message.answer("✅ **تم العثور على الفيديو، اختر توقيت البداية:**", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("clip"))
async def send_clip(callback: CallbackQuery):
    msg = await callback.message.edit_text("📥 **جاري تحميل الفيديو...**")
    _, time, url = callback.data.split("|")
    
    await msg.edit_text("🎥 **تحسين الجودة...**")
    # تحميل سريع جداً
    os.system(f'yt-dlp -f "best[ext=mp4]" -o "raw.mp4" "{url}"')
    
    await msg.edit_text("✂️ **جاري استخراج المقطع...**")
    # معالجة فورية بجودة 1080p
    os.system(f'ffmpeg -i raw.mp4 -ss {time} -t 60 -vf scale=1920:1080 -c:v libx264 -preset ultrafast -crf 20 final.mp4 -y')
    
    await callback.message.answer_video(
        video=FSInputFile("final.mp4"), 
        caption=f"{HEADER}\n\n✅ **تم استخراج المقطع بنجاح.**\n\n🎥 **الجودة:** Full HD\n⏱️ **المدة:** 60 ثانية\n⚡ **تمت المعالجة بسرعة.**\n\nنسأل الله أن ينفع به."
    )
    await callback.message.delete()
    
    # تنظيف
    if os.path.exists("raw.mp4"): os.remove("raw.mp4")
    if os.path.exists("final.mp4"): os.remove("final.mp4")

async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
