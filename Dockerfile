FROM python:3.11-slim

WORKDIR /app

# Копируем только backend и requirements
COPY backend/ ./backend/
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Открываем порт
EXPOSE 8000

# Команда запуска
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "120", "--timeout-graceful-shutdown", "30"]
