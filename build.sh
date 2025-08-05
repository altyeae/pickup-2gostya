#!/usr/bin/env bash
# exit on error
set -o errexit

echo "Starting build process..."

# Устанавливаем зависимости для бэкенда
echo "Installing Python dependencies..."
pip install -r backend/requirements.txt

# Собираем фронтенд
echo "Building frontend..."
cd frontend
npm install
npm run build
cd ..

# Создаем папку build в backend если её нет
echo "Copying frontend build to backend..."
mkdir -p backend/build

# Копируем собранный фронтенд в папку backend для монтирования
cp -r frontend/build/* backend/build/

echo "Build completed successfully!" 