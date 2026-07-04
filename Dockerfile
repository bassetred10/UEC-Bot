# استخدام نسخة Python 3.10 وهي الأكثر استقراراً مع whisper
FROM python:3.10-slim

# تثبيت المكتبات الأساسية
RUN apt-get update && apt-get install -y \
    ffmpeg \
    gcc \
    g++ \
    curl \
    python3-dev \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

# إضافة rust للـ PATH
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /app

# تثبيت setuptools و pip أولاً لحل مشكلة pkg_resources
RUN pip install --upgrade pip setuptools wheel

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
