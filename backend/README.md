# XLS Import Backend

FastAPI бэкенд для обработки XLS файлов и интеграции с Google Sheets.

## Установка и запуск

1. Создайте виртуальное окружение:
```bash
python -m venv venv
source venv/bin/activate  # На Windows: venv\Scripts\activate
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Запустите сервер:
```bash
python main.py
```

Сервер будет доступен по адресу: http://localhost:8000

## API Endpoints

### Авторизация
- `POST /api/login` - Вход в систему (admin/portcomfort)

### Загрузка и обработка файлов
- `POST /api/upload` - Загрузка XLS файла
- `GET /api/status/{task_id}` - Получение статуса обработки

### Настройки
- `GET /api/settings` - Получение настроек город-ссылка
- `POST /api/settings` - Сохранение настроек

## Настройка Google Sheets

Для работы с Google Sheets необходимо:

1. Создать проект в Google Cloud Console
2. Включить Google Sheets API
3. Создать сервисный аккаунт
4. Скачать JSON файл с ключами
5. Разместить файл как `service-account.json` в папке backend
6. Раскомментировать код в функции `get_google_sheets_client()`

## Структура проекта

```
backend/
├── main.py              # Главный файл FastAPI приложения
├── requirements.txt     # Зависимости Python
├── settings.json        # Файл с настройками (создается автоматически)
└── README.md           # Этот файл
```

## Функциональность

- **Авторизация**: JWT токены
- **Загрузка файлов**: Поддержка .xls файлов
- **Фоновая обработка**: Асинхронная обработка файлов
- **Google Sheets интеграция**: Создание листов и запись данных
- **Настройки**: Сохранение ссылок на таблицы для каждого города
- **Отслеживание прогресса**: Реальное время статуса обработки 