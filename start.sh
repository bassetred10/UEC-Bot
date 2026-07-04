#!/bin/bash

# script للبدء على Render

echo "Starting Islamic Podcast Bot..."

# التحقق من وجود المتغيرات المطلوبة
if [ -z "$BOT_TOKEN" ]; then
    echo "ERROR: BOT_TOKEN not set"
    exit 1
fi

if [ -z "$CHANNEL_ID" ]; then
    echo "ERROR: CHANNEL_ID not set"
    exit 1
fi

if [ -z "$ADMIN_ID" ]; then
    echo "ERROR: ADMIN_ID not set"
    exit 1
fi

# إنشاء المجلدات المطلوبة
mkdir -p temp logs

# تثبيت المتطلبات (في حال عدم استخدام Docker)
pip install -r requirements.txt --quiet

# تشغيل البوت
python bot.py
