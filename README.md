# XLS Import Application

Веб-приложение для импорта XLS файлов в Google таблицы с автоматическим созданием листов по датам.

## Описание

Приложение позволяет:
- Загружать XLS файлы через веб-интерфейс
- Настраивать соответствие городов и Google таблиц
- Автоматически создавать новые листы с датой в формате DDMMYY
- Отслеживать прогресс обработки в реальном времени
- Отображать ошибки по каждому городу

## Структура проекта

```
├── frontend/           # React приложение
│   ├── src/
│   │   ├── components/
│   │   │   ├── Login.js
│   │   │   ├── Dashboard.js
│   │   │   └── Settings.js
│   │   ├── App.js
│   │   └── index.js
│   ├── package.json
│   └── README.md
├── backend/            # FastAPI сервер
│   ├── main.py
│   ├── requirements.txt
│   └── README.md
└── README.md
```

## Быстрый старт

### 1. Запуск бэкенда

```bash
cd backend
python -m venv venv
source venv/bin/activate  # На Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### 2. Запуск фронтенда

```bash
cd frontend
npm install
npm start
```

### 3. Доступ к приложению

- Фронтенд: http://localhost:3000
- Бэкенд: http://localhost:8000
- Логин: `admin`
- Пароль: `portcomfort`

## Настройка Google Sheets

1. Создайте проект в [Google Cloud Console](https://console.cloud.google.com/)
2. Включите Google Sheets API
3. Создайте сервисный аккаунт
4. Скачайте JSON файл с ключами
5. Разместите файл как `backend/service-account.json`
6. Раскомментируйте код в функции `get_google_sheets_client()` в `backend/main.py`

## Поддерживаемые города

- Балашиха
- Железнодорожный
- Жуковский
- Ивантеевка
- Казань
- Королев
- Люберцы
- Мытищи
- Ногинск
- Пушкино
- Раменское
- Сергиев Посад
- Фрязино
- Щелково
- Электросталь

## Технологии

### Фронтенд
- React 18
- React Router
- Axios
- CSS3

### Бэкенд
- FastAPI
- Python 3.8+
- xlrd (для парсинга XLS)
- gspread (для работы с Google Sheets)
- JWT авторизация

## API Endpoints

- `POST /api/login` - Авторизация
- `POST /api/upload` - Загрузка XLS файла
- `GET /api/status/{task_id}` - Статус обработки
- `GET /api/settings` - Получение настроек
- `POST /api/settings` - Сохранение настроек 