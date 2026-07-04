import asyncio
import aiohttp
import logging
from datetime import datetime
from typing import Optional

from config import Config

logger = logging.getLogger(__name__)


class KeepAliveManager:
    """
    مدير Keep-Alive لمنع البوت من النوم
    """
    
    def __init__(self):
        """تهيئة مدير Keep-Alive"""
        self.is_running = False
        self.interval = Config.KEEP_ALIVE_INTERVAL
        self.url = Config.KEEP_ALIVE_URL
        self.task: Optional[asyncio.Task] = None
        
        logger.info(f"🔄 Keep-Alive Manager initialized (interval: {self.interval}s)")
    
    async def start(self):
        """بدء تشغيل Keep-Alive"""
        if self.is_running:
            logger.warning("Keep-Alive already running")
            return
        
        self.is_running = True
        self.task = asyncio.create_task(self._keep_alive_loop())
        logger.info("✅ Keep-Alive started")
    
    async def stop(self):
        """إيقاف Keep-Alive"""
        self.is_running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("⏹️ Keep-Alive stopped")
    
    async def _keep_alive_loop(self):
        """حلقة Keep-Alive الرئيسية"""
        while self.is_running:
            try:
                await self._ping()
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Keep-Alive error: {e}")
                await asyncio.sleep(60)  # انتظار دقيقة قبل المحاولة مرة أخرى
    
    async def _ping(self):
        """
        إرسال طلب Ping للحفاظ على البوت نشطاً
        """
        if not self.url:
            # محاولة الحصول على الرابط من متغيرات البيئة
            import os
            self.url = os.getenv('RENDER_EXTERNAL_URL', '')
            
            if not self.url:
                logger.warning("⚠️ No URL for Keep-Alive, skipping")
                return
        
        try:
            # محاولة الوصول إلى Health Check
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.url}/health",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        logger.info(f"🔄 Keep-Alive ping successful at {datetime.now().strftime('%H:%M:%S')}")
                    else:
                        logger.warning(f"⚠️ Keep-Alive ping failed with status {response.status}")
        except asyncio.TimeoutError:
            logger.warning("⚠️ Keep-Alive timeout")
        except Exception as e:
            logger.error(f"⚠️ Keep-Alive error: {e}")
    
    async def ping_health_check(self):
        """
        دالة مساعدة لعمل Ping يدوي
        """
        await self._ping()


# إنشاء كائن Keep-Alive العالمي
keep_alive_manager = KeepAliveManager()
