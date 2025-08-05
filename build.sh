#!/usr/bin/env bash
# exit on error
set -o errexit

# Устанавливаем зависимости для бэкенда
pip install -r backend/requirements.txt

# Собираем фронтенд
cd frontend
npm install
npm run build
cd ..

# Копируем собранный фронтенд в папку backend для монтирования
cp -r frontend/build backend/ 