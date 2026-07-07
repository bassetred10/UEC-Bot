import os
import subprocess
import tempfile
import asyncio
import logging
from typing import List, Tuple, Optional, Dict, Any
import json
import shutil

# 🔴 استخدم openai_whisper بدلاً من whisper
import openai_whisper as whisper
import ffmpeg
from pydub import AudioSegment

from config import Config

logger = logging.getLogger(__name__)


class VideoProcessor:
    """
    فئة معالجة الفيديو
    """
    
    def __init__(self, cookies_file: str = None):
        self.cookies_file = cookies_file if cookies_file else Config.COOKIES_FILE
        self.model = None
        self.temp_dir = Config.TEMP_DIR
        
        os.makedirs(self.temp_dir, exist_ok=True)
        self._load_model()
    
    def _load_model(self) -> None:
        """تحميل نموذج Whisper"""
        try:
            logger.info(f"Loading Whisper model: {Config.WHISPER_MODEL}")
            self.model = whisper.load_model(Config.WHISPER_MODEL)
            logger.info("✅ Whisper model loaded successfully")
        except Exception as e:
            logger.error(f"Error loading Whisper model: {e}")
            raise
    
    async def download_video(self, url: str) -> str:
        """تحميل الفيديو من يوتيوب"""
        temp_dir = tempfile.mkdtemp(dir=self.temp_dir)
        output_path = os.path.join(temp_dir, 'video.mp4')
        
        cmd = [
            'yt-dlp',
            '-f', 'bestaudio[ext=mp3]/bestaudio',
            '-o', output_path.replace('.mp4', '.%(ext)s'),
            '--no-playlist',
            '--extract-audio',
            '--audio-format', 'mp3',
            '--audio-quality', Config.AUDIO_QUALITY,
            '--quiet',
            '--no-warnings'
        ]
        
        if self.cookies_file and os.path.exists(self.cookies_file):
            cmd.extend(['--cookies', self.cookies_file])
            logger.info("Using cookies file for YouTube")
        
        cmd.append(url)
        
        try:
            logger.info(f"Downloading video: {url}")
            
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
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
            raise
    
    def extract_audio_text(self, audio_path: str) -> Dict[str, Any]:
        """استخراج النص من الصوت"""
        try:
            logger.info(f"Transcribing audio: {audio_path}")
            result = self.model.transcribe(
                audio_path,
                language='ar',
                task='transcribe'
            )
            logger.info(f"Transcription completed: {len(result['segments'])} segments")
            return result
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            raise Exception(f"فشل تحويل الصوت إلى نص: {e}")
    
    def find_keywords(self, transcription: Dict[str, Any], 
                     keywords: List[str]) -> List[Dict[str, Any]]:
        """البحث عن الكلمات المفتاحية"""
        found_segments = []
        segments = transcription.get('segments', [])
        duration = transcription.get('duration', 0)
        padding = Config.PADDING_TIME
        
        logger.info(f"Searching for keywords in {len(segments)} segments")
        
        for segment in segments:
            text = segment.get('text', '')
            start = segment.get('start', 0)
            end = segment.get('end', 0)
            
            matched_keywords = []
            for keyword in keywords:
                if keyword.lower() in text.lower():
                    matched_keywords.append(keyword)
            
            if matched_keywords:
                new_start = max(0, start - padding)
                new_end = min(duration, end + padding)
                
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
                
                logger.info(f"Found keyword '{matched_keywords[0]}' at {start:.2f}s")
        
        found_segments.sort(key=lambda x: x['start'])
        merged_segments = self._merge_segments(found_segments)
        
        logger.info(f"Found {len(merged_segments)} unique segments with keywords")
        return merged_segments
    
    def _merge_segments(self, segments: List[Dict]) -> List[Dict]:
        """دمج المقاطع المتداخلة"""
        if not segments:
            return []
        
        merged = []
        current = segments[0].copy()
        
        for next_seg in segments[1:]:
            if next_seg['start'] <= current['end'] + 2.0:
                current['keywords'] = list(set(current['keywords'] + next_seg['keywords']))
                current['text'] = current['text'] + " ... " + next_seg['text']
                current['end'] = max(current['end'], next_seg['end'])
                current['duration'] = current['end'] - current['start']
            else:
                merged.append(current)
                current = next_seg.copy()
        
        merged.append(current)
        return merged
    
    async def extract_clip(self, audio_path: str, start: float, end: float) -> str:
        """استخراج مقطع من الصوت"""
        try:
            temp_dir = tempfile.mkdtemp(dir=self.temp_dir)
            output_path = os.path.join(temp_dir, f'clip_{start:.2f}_{end:.2f}.mp3')
            
            logger.info(f"Extracting clip from {start:.2f}s to {end:.2f}s")
            
            (
                ffmpeg
                .input(audio_path, ss=start, to=end)
                .output(output_path, acodec='libmp3lame', ab='128k')
                .overwrite_output()
                .run(quiet=True, capture_stdout=True, capture_stderr=True)
            )
            
            logger.info(f"Clip extracted successfully: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Clip extraction error: {e}")
            raise Exception(f"فشل استخراج المقطع: {e}")
    
    async def process_video(self, url: str, keywords: List[str]) -> Tuple[List[Dict], List[str]]:
        """معالجة الفيديو بالكامل"""
        audio_path = None
        temp_dirs = []
        
        try:
            logger.info(f"Starting video processing for: {url}")
            audio_path = await self.download_video(url)
            temp_dirs.append(os.path.dirname(audio_path))
            
            transcription = self.extract_audio_text(audio_path)
            segments = self.find_keywords(transcription, keywords)
            
            if not segments:
                logger.info("No keywords found in the video")
                return [], []
            
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
                segments[i]['clip_path'] = clip_path
            
            logger.info(f"Successfully processed video, extracted {len(clips)} clips")
            return segments[:max_clips], clips
            
        except Exception as e:
            logger.error(f"Processing error: {e}")
            self._cleanup_temp_files(temp_dirs)
            raise
    
    def _cleanup_temp_files(self, temp_dirs: List[str]) -> None:
        """تنظيف الملفات المؤقتة"""
        for temp_dir in temp_dirs:
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    logger.info(f"Cleaned up temp directory: {temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up {temp_dir}: {e}")
    
    def cleanup_clip(self, clip_path: str) -> None:
        """تنظيف ملف مقطع بعد إرساله"""
        try:
            if os.path.exists(clip_path):
                os.remove(clip_path)
                logger.info(f"Cleaned up clip file: {clip_path}")
                
                parent_dir = os.path.dirname(clip_path)
                if os.path.exists(parent_dir) and not os.listdir(parent_dir):
                    os.rmdir(parent_dir)
                    logger.info(f"Cleaned up empty directory: {parent_dir}")
        except Exception as e:
            logger.warning(f"Failed to clean up clip {clip_path}: {e}")


def check_requirements() -> bool:
    """التحقق من تثبيت المتطلبات الأساسية"""
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
        return False
    
    return True
