import yt_dlp
import whisper
import ffmpeg
import os
from config import Config

class VideoProcessor:
    def __init__(self):
        # تحميل نموذج whisper للتحويل من صوت إلى نص
        self.model = whisper.load_model("base")

    def download_video(self, url, output_path):
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': output_path,
            'cookiefile': Config.COOKIES_FILE,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

    def transcribe(self, audio_path):
        # تحويل الصوت إلى نص
        result = self.model.transcribe(audio_path)
        return result["text"]

    def extract_audio(self, video_path, audio_path):
        # استخراج الصوت من الفيديو
        stream = ffmpeg.input(video_path)
        stream = ffmpeg.output(stream, audio_path)
        ffmpeg.run(stream, overwrite_output=True)
