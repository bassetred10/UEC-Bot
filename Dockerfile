FROM python:3.10-slim

# تحديث النظام وتثبيت الأدوات اللازمة للـ build
RUN apt-get update && apt-get install -y \
    ffmpeg \
    gcc \
    g++ \
    curl \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

# إضافة rust للـ PATH
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /app
COPY . .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

CMD ["python", "bot.py"]
