# ==========================================
# Этап 1: builder — здесь ставим compiler toolchain
# и компилируем C-расширения (asyncpg, argon2-cffi-bindings,
# cryptography и т.д.). Этот слой целиком отбрасывается.
# ==========================================
FROM python:3.13-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libkrb5-dev \
    comerr-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# ==========================================
# Этап 2: runtime — чистый slim-образ,
# без gcc/python3-dev/libkrb5-dev, non-root user
# ==========================================
FROM python:3.13-slim

# non-root пользователь, UID 1000 — стандартная практика,
# совпадает с большинством дефолтных UID на хосте (важно для volume-прав в dev)
RUN useradd --create-home --uid 1000 --shell /bin/bash appuser

WORKDIR /app

# Только скомпилированные пакеты, без компилятора
COPY --from=builder /root/.local /home/appuser/.local

# Код приложения
COPY . .

RUN chown -R appuser:appuser /app /home/appuser/.local

ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://localhost:8000/health').status == 200 else sys.exit(1)"

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]