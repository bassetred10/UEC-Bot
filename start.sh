#!/bin/bash

echo "=========================================="
echo "🚀 Starting Islamic Podcast Bot"
echo "=========================================="
echo "Time: $(date)"
echo "Python: $(python --version)"
echo "=========================================="

if [ -z "$BOT_TOKEN" ]; then
    echo "❌ ERROR: BOT_TOKEN is not set"
    exit 1
fi

if [ -z "$CHANNEL_ID" ]; then
    echo "❌ ERROR: CHANNEL_ID is not set"
    exit 1
fi

if [ -z "$ADMIN_ID" ]; then
    echo "❌ ERROR: ADMIN_ID is not set"
    exit 1
fi

echo "✅ All environment variables are set"

mkdir -p temp logs
echo "✅ Created directories: temp, logs"

if command -v ffmpeg &> /dev/null; then
    echo "✅ ffmpeg is installed"
else
    echo "⚠️  ffmpeg is not installed, installing..."
    apt-get update && apt-get install -y ffmpeg
fi

echo "=========================================="
echo "📊 System Information:"
echo "   - CPU: $(nproc) cores"
echo "   - Memory: $(free -m | awk '/Mem:/ {print $2}') MB"
echo "=========================================="

echo "🔄 Starting Health Check server..."
python health.py &
HEALTH_PID=$!
echo "✅ Health Check started (PID: $HEALTH_PID)"

sleep 2

echo "=========================================="
echo "🤖 Starting Telegram Bot..."
echo "=========================================="

python bot.py

kill $HEALTH_PID 2>/dev/null
