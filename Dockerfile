# استخدام صورة Python رسمية
FROM python:3.10-slim

# تعيين متغيرات البيئة
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Africa/Algiers

# تثبيت المتطلبات النظامية
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

# إنشاء مجلد العمل
WORKDIR /app

# نسخ ملفات المتطلبات أولاً (للاستفادة من الكاش)
COPY requirements.txt .

# تثبيت المتطلبات Python
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي الملفات
COPY . .

# إنشاء المجلدات المطلوبة
RUN mkdir -p temp logs

# تعيين متغيرات البيئة الافتراضية
ENV BOT_TOKEN=${BOT_TOKEN} \
    CHANNEL_ID=${CHANNEL_ID} \
    ADMIN_ID=${ADMIN_ID}

# تشغيل البوت
CMD ["python", "bot.py"]
