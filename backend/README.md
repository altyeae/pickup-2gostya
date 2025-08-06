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
- `POST /api/clear-cache` - Очистка кэша Google Sheets клиента
- `POST /api/clear-today-sheets` - Удаление всех листов с сегодняшней датой

## Настройка Google Sheets

Для работы с Google Sheets необходимо:

1. Создать проект в Google Cloud Console
2. Включить Google Sheets API
3. Создать сервисный аккаунт
4. Скачать JSON файл с ключами
5. Разместить файл как `service-account.json` в папке backend
6. Раскомментировать код в функции `get_google_sheets_client()`

## Оптимизация Google API

Для избежания превышения квоты Google API реализованы следующие оптимизации:

### Настройки через переменные окружения:
```bash
GOOGLE_API_DELAY=1.0      # Задержка между запросами (сек)
MAX_RETRIES=3             # Количество попыток
RETRY_DELAY=2.0           # Задержка между попытками (сек)
```

### Рекомендации для продакшена:
```bash
GOOGLE_API_DELAY=2.0
MAX_RETRIES=2
RETRY_DELAY=5.0
```

### Тестирование:
```bash
# Тест Google API лимитов
python test_api_limits.py

# Тест управления листами
python test_sheet_management.py
```

Подробная документация: [GOOGLE_API_OPTIMIZATION.md](../GOOGLE_API_OPTIMIZATION.md)

## Структура проекта

```
backend/
├── main.py                    # Главный файл FastAPI приложения
├── requirements.txt           # Зависимости Python
├── settings.json              # Файл с настройками (создается автоматически)
├── test_api_limits.py         # Тест Google API лимитов
├── test_sheet_management.py   # Тест управления листами
└── README.md                  # Этот файл
```

## Функциональность

- **Авторизация**: JWT токены
- **Загрузка файлов**: Поддержка .xls файлов
- **Фоновая обработка**: Асинхронная обработка файлов
- **Google Sheets интеграция**: Создание листов и запись данных
- **Настройки**: Сохранение ссылок на таблицы для каждого города
- **Отслеживание прогресса**: Реальное время статуса обработки 