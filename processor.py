import os
import subprocess
import tempfile
import asyncio
import logging
from typing import List, Tuple, Optional, Dict, Any
import json
import shutil

import whisper
import ffmpeg
from pydub import AudioSegment

from config import Config

logger = logging.getLogger(__name__)


class VideoProcessor:
    """
    فئة معالجة الفيديو
    تقوم بتحميل الفيديو، تحويله إلى نص، واستخراج المقاطع بناءً على الكلمات المفتاحية
    """
    
    def __init__(self, cookies_file: str = None):
        """
        تهيئة معالج الفيديو
        
        Args:
            cookies_file: مسار ملف الكوكيز لتجاوز حظر يوتيوب
        """
        self.cookies_file = cookies_file if cookies_file else Config.COOKIES_FILE
        self.model = None
        self.temp_dir = Config.TEMP_DIR
        
        # إنشاء مجلد الملفات المؤقتة
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # تحميل نموذج Whisper
        self._load_model()
    
    def _load_model(self) -> None:
        """
        تحميل نموذج Whisper لتحويل الصوت إلى نص
        """
        try:
            logger.info(f"Loading Whisper model: {Config.WHISPER_MODEL}")
            self.model = whisper.load_model(Config.WHISPER_MODEL)
            logger.info("Whisper model loaded successfully")
        except Exception as e:
            logger.error(f"Error loading Whisper model: {e}")
            raise
    
    async def download_video(self, url: str) -> str:
        """
        تحميل الفيديو من يوتيوب واستخراج الصوت
        
        Args:
            url: رابط الفيديو
        
        Returns:
            str: مسار ملف الصوت المستخرج
        
        Raises:
            Exception: عند فشل التحميل
        """
        # إنشاء مجلد مؤقت
        temp_dir = tempfile.mkdtemp(dir=self.temp_dir)
        output_path = os.path.join(temp_dir, 'video.mp4')
        
        # بناء أمر yt-dlp
        cmd = [
            'yt-dlp',
            '-f', 'bestaudio[ext=mp3]/bestaudio',  # أفضل جودة صوت
            '-o', output_path.replace('.mp4', '.%(ext)s'),
            '--no-playlist',
            '--extract-audio',
            '--audio-format', 'mp3',
            '--audio-quality', Config.AUDIO_QUALITY,
            '--quiet',  # تقليل الإخراج
            '--no-warnings'
        ]
        
        # إضافة ملف الكوكيز إذا كان موجوداً
        if self.cookies_file and os.path.exists(self.cookies_file):
            cmd.extend(['--cookies', self.cookies_file])
            logger.info("Using cookies file for YouTube")
        
        cmd.append(url)
        
        try:
            logger.info(f"Downloading video: {url}")
            
            # تشغيل عملية التحميل
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error(f"yt-dlp failed: {error_msg}")
                raise Exception(f"فشل تحميل الفيديو: {error_msg}")
            
            # البحث عن ملف الصوت المستخرج
            audio_file = None
            for file in os.listdir(temp_dir):
                if file.endswith('.mp3'):
                    audio_file = os.path.join(temp_dir, file)
                    break
            
            if not audio_file:
                raise Exception("لم يتم العثور على ملف الصوت المستخرج")
            
            logger.info(f"Video downloaded successfully: {audio_file}")
            return audio_file
            
        except Exception as e:
            logger.error(f"Download error: {e}")
            # تنظيف الملفات المؤقتة في حالة الفشل
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
            raise
    
    def extract_audio_text(self, audio_path: str) -> Dict[str, Any]:
        """
        استخراج النص من الصوت مع التوقيت
        
        Args:
            audio_path: مسار ملف الصوت
        
        Returns:
            Dict: نتائج التحويل (نص، مقاطع، توقيت)
        
        Raises:
            Exception: عند فشل تحويل الصوت إلى نص
        """
        try:
            logger.info(f"Transcribing audio: {audio_path}")
            result = self.model.transcribe(
                audio_path,
                language='ar',  # اللغة العربية
                task='transcribe',
                fp16=False  # استخدام CPU
            )
            logger.info(f"Transcription completed: {len(result['segments'])} segments")
            return result
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            raise Exception(f"فشل تحويل الصوت إلى نص: {e}")
    
    def find_keywords(self, transcription: Dict[str, Any], 
                     keywords: List[str]) -> List[Dict[str, Any]]:
        """
        البحث عن الكلمات المفتاحية في النص
        
        Args:
            transcription: نتائج تحويل الصوت إلى نص
            keywords: قائمة الكلمات المفتاحية للبحث
        
        Returns:
            List[Dict]: قائمة المقاطع التي تحتوي على كلمات مفتاحية
        """
        found_segments = []
        segments = transcription.get('segments', [])
        duration = transcription.get('duration', 0)
        padding = Config.PADDING_TIME
        
        logger.info(f"Searching for keywords in {len(segments)} segments")
        
        for segment in segments:
            text = segment.get('text', '')
            start = segment.get('start', 0)
            end = segment.get('end', 0)
            
            # البحث عن الكلمات المفتاحية في النص
            matched_keywords = []
            for keyword in keywords:
                if keyword.lower() in text.lower():
                    matched_keywords.append(keyword)
            
            # إذا تم العثور على كلمات مفتاحية
            if matched_keywords:
                # إضافة وقت إضافي قبل وبعد المقطع
                new_start = max(0, start - padding)
                new_end = min(duration, end + padding)
                
                # تمديد المقطع إذا كان في البداية أو النهاية
                if start == 0:
                    new_start = 0
                if end == duration:
                    new_end = duration
                
                found_segments.append({
                    'keywords': matched_keywords,
                    'text': text.strip(),
                    'start': new_start,
                    'end': new_end,
                    'duration': new_end - new_start,
                    'original_start': start,
                    'original_end': end
                })
                
                logger.info(f"Found keyword '{matched_keywords[0]}' at {start:.2f}s - {end:.2f}s")
        
        # ترتيب المقاطع حسب التوقيت
        found_segments.sort(key=lambda x: x['start'])
        
        # دمج المقاطع المتداخلة
        merged_segments = self._merge_segments(found_segments)
        
        logger.info(f"Found {len(merged_segments)} unique segments with keywords")
        return merged_segments
    
    def _merge_segments(self, segments: List[Dict]) -> List[Dict]:
        """
        دمج المقاطع المتداخلة أو المتقاربة
        
        Args:
            segments: قائمة المقاطع المرشحة
        
        Returns:
            List[Dict]: قائمة المقاطع المدمجة
        """
        if not segments:
            return []
        
        merged = []
        current = segments[0].copy()
        
        for next_seg in segments[1:]:
            # إذا كان المقطع التالي متداخلاً أو قريباً جداً
            if next_seg['start'] <= current['end'] + 2.0:  # 2 ثانية فارق
                # دمج الكلمات المفتاحية
                current['keywords'] = list(set(current['keywords'] + next_seg['keywords']))
                # دمج النص
                current['text'] = current['text'] + " ... " + next_seg['text']
                # تحديث وقت النهاية
                current['end'] = max(current['end'], next_seg['end'])
                current['duration'] = current['end'] - current['start']
            else:
                merged.append(current)
                current = next_seg.copy()
        
        merged.append(current)
        return merged
    
    async def extract_clip(self, audio_path: str, start: float, end: float) -> str:
        """
        استخراج مقطع من الصوت
        
        Args:
            audio_path: مسار ملف الصوت الأصلي
            start: وقت البداية (بالثواني)
            end: وقت النهاية (بالثواني)
        
        Returns:
            str: مسار المقطع المستخرج
        
        Raises:
            Exception: عند فشل استخراج المقطع
        """
        try:
            # إنشاء مجلد مؤقت للمقطع
            temp_dir = tempfile.mkdtemp(dir=self.temp_dir)
            output_path = os.path.join(temp_dir, f'clip_{start:.2f}_{end:.2f}.mp3')
            
            logger.info(f"Extracting clip from {start:.2f}s to {end:.2f}s")
            
            # استخدام ffmpeg لقص المقطع
            (
                ffmpeg
                .input(audio_path, ss=start, to=end)
                .output(output_path, acodec='libmp3lame', ab='192k')
                .overwrite_output()
                .run(quiet=True, capture_stdout=True, capture_stderr=True)
            )
            
            logger.info(f"Clip extracted successfully: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Clip extraction error: {e}")
            raise Exception(f"فشل استخراج المقطع: {e}")
    
    async def process_video(self, url: str, keywords: List[str]) -> Tuple[List[Dict], List[str]]:
        """
        معالجة الفيديو بالكامل (تحميل، تحويل، بحث، استخراج)
        
        Args:
            url: رابط الفيديو
            keywords: قائمة الكلمات المفتاحية
        
        Returns:
            Tuple[List[Dict], List[str]]: (قائمة المقاطع المكتشفة, قائمة مسارات المقاطع المستخرجة)
        
        Raises:
            Exception: عند فشل أي خطوة في المعالجة
        """
        audio_path = None
        temp_dirs = []
        
        try:
            # 1. تحميل الفيديو واستخراج الصوت
            logger.info(f"Starting video processing for: {url}")
            audio_path = await self.download_video(url)
            temp_dirs.append(os.path.dirname(audio_path))
            
            # 2. تحويل الصوت إلى نص
            transcription = self.extract_audio_text(audio_path)
            
            # 3. البحث عن الكلمات المفتاحية
            segments = self.find_keywords(transcription, keywords)
            
            if not segments:
                logger.info("No keywords found in the video")
                return [], []
            
            # 4. استخراج المقاطع (حد أقصى Config.MAX_CLIPS)
            clips = []
            max_clips = min(len(segments), Config.MAX_CLIPS)
            
            for i in range(max_clips):
                segment = segments[i]
                clip_path = await self.extract_clip(
                    audio_path,
                    segment['start'],
                    segment['end']
                )
                clips.append(clip_path)
                temp_dirs.append(os.path.dirname(clip_path))
                
                # تحديث معلومات المقطع
                segments[i]['clip_path'] = clip_path
            
            logger.info(f"Successfully processed video, extracted {len(clips)} clips")
            return segments[:max_clips], clips
            
        except Exception as e:
            logger.error(f"Processing error: {e}")
            # تنظيف الملفات المؤقتة في حالة الفشل
            self._cleanup_temp_files(temp_dirs)
            raise
        
        # ملاحظة: لا نقوم بتنظيف الملفات هنا لأنها ستستخدم لإرسالها للمستخدم
        # سيتم التنظيف بعد إرسال المقاطع
    
    def _cleanup_temp_files(self, temp_dirs: List[str]) -> None:
        """
        تنظيف الملفات والمجلدات المؤقتة
        
        Args:
            temp_dirs: قائمة المجلدات المراد حذفها
        """
        for temp_dir in temp_dirs:
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    logger.info(f"Cleaned up temp directory: {temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up {temp_dir}: {e}")
    
    def cleanup_clip(self, clip_path: str) -> None:
        """
        تنظيف ملف مقطع بعد إرساله
        
        Args:
            clip_path: مسار المقطع
        """
        try:
            if os.path.exists(clip_path):
                # حذف الملف
                os.remove(clip_path)
                logger.info(f"Cleaned up clip file: {clip_path}")
                
                # حذف المجلد الأب إذا كان فارغاً
                parent_dir = os.path.dirname(clip_path)
                if os.path.exists(parent_dir) and not os.listdir(parent_dir):
                    os.rmdir(parent_dir)
                    logger.info(f"Cleaned up empty directory: {parent_dir}")
        except Exception as e:
            logger.warning(f"Failed to clean up clip {clip_path}: {e}")


# التحقق من تثبيت المتطلبات
def check_requirements() -> bool:
    """
    التحقق من تثبيت المتطلبات الأساسية
    
    Returns:
        bool: هل جميع المتطلبات مثبتة
    """
    requirements = {
        'ffmpeg': 'ffmpeg -version',
        'yt-dlp': 'yt-dlp --version'
    }
    
    missing = []
    for name, cmd in requirements.items():
        try:
            subprocess.run(cmd.split(), capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            missing.append(name)
    
    if missing:
        logger.error(f"Missing requirements: {', '.join(missing)}")
        print(f"\n❌ المتطلبات التالية غير مثبتة: {', '.join(missing)}")
        print("يرجى تثبيتها باستخدام:")
        print("sudo apt-get install ffmpeg")
        print("pip install yt-dlp")
        return False
    
    return True
