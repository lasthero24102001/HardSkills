# Используем официальный образ Python
FROM python:3.13-alpine

# Устанавливаем рабочую директорию
WORKDIR /app

# Обновляем список пакетов
RUN apk update

# Устанавливаем официальный пакет pygame и его зависимости
RUN apk add --no-cache py3-pygame

# Копируем файл с зависимостями (убедитесь, что requirements.txt существует!)
COPY requirements.txt .

# Устанавливаем остальные зависимости Python, которых нет в пакете (FastAPI, SQLAlchemy и т.д.)
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь остальной код в контейнер
COPY . .

# Команда для запуска Uvicorn
CMD ["uvicorn", "db1.main:app", "--host", "0.0.0.0", "--port", "8000"]
