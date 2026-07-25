FROM python:3.13-slim

# Устанавливаем системные зависимости, необходимые для компиляции gssapi и других пакетов
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libkrb5-dev \
    comerr-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]