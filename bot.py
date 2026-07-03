import asyncio
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

TOKEN = '8290675844:AAEM4wRNEgIE1-feTaYcK_RsgZFywKWtZ0o'
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- Web Server (الخدعة باش ما يطفاش السيرفر) ---
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
    text = "مرحبا بك في بوت بودكاست\n\nتحويل فيديوهات البودكاست الدينية لتسهيل نشرها في مواقع التواصل الاجتماعي.\n\nأرسل رابط الفيديو الآن للبدء! 🎥"
    await message.answer(text)

@dp.message(F.text.startswith("http"))
async def handle_url(message: Message):
    url = message.text
    builder = InlineKeyboardBuilder()
    builder.button(text="▶️ المقطع الأول", callback_data=f"clip|00:00:00|{url}")
    builder.button(text="▶️ المقطع الثاني", callback_data=f"clip|00:05:00|{url}")
    builder.button(text="▶️ المقطع الثالث", callback_data=f"clip|00:10:00|{url}")
    builder.button(text="▶️ المقطع الرابع", callback_data=f"clip|00:15:00|{url}")
    builder.adjust(1)
    await message.answer("✅ تم استلام الرابط بنجاح.\nاختر المقطع المطلوب:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("clip"))
async def send_clip(callback: CallbackQuery):
    msg = await callback.message.edit_text("⏳ انتظر قليلاً من فضلك...")
    try:
        _, time, url = callback.data.split("|")
        
        # تحميل بجودة متوسطة لضمان السرعة
        download_cmd = f'yt-dlp -f "best[ext=mp4][height<=720]" -o "raw.mp4" "{url}"'
        if os.system(download_cmd) != 0:
            raise Exception("رابط غير صالح")

        # معالجة قوية بضغط عالي (CRF 30 = حجم صغير جداً وسرعة خيالية)
        os.system(f'ffmpeg -i raw.mp4 -ss {time} -t 60 -vf scale=1280:720 -c:v libx264 -preset ultrafast -crf 30 -c:a aac -b:a 96k final.mp4 -y')
        
        await callback.message.answer_video(
            video=FSInputFile("final.mp4"), 
            caption="🎥 تم استخراج المقطع بنجاح، نسأل الله أن ينفع به."
        )
        await msg.delete()
        
        if os.path.exists("raw.mp4"): os.remove("raw.mp4")
        if os.path.exists("final.mp4"): os.remove("final.mp4")
        
    except Exception as e:
        await msg.edit_text("❌ خطأ: ارسل رابط صحيح أو تأكد من جودة الفيديو.")

async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
