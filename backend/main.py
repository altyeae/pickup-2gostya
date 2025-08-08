from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import json
import os
import uuid
from datetime import datetime, timedelta
import asyncio
from typing import Dict, List, Optional, Tuple
import gspread
from google.oauth2.service_account import Credentials
import re
import xml.etree.ElementTree as ET
import logging
import time
from functools import lru_cache

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="XLS Import API", 
    version="1.0.0",
    # Увеличиваем лимиты для загрузки больших файлов
    docs_url=None,
    redoc_url=None
)

# Настройка CORS
cors_origins = [
    "http://localhost:3000",
    "https://pickup-2gostya.onrender.com"
]

# Добавляем CORS_ORIGIN из переменной окружения, если она установлена
cors_origin_env = os.getenv('CORS_ORIGIN')
if cors_origin_env:
    cors_origins.append(cors_origin_env)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400,  # Кэшируем preflight на 24 часа
)

# Глобальный кэш для клиента Google Sheets
_google_client_cache = None
_last_client_creation = 0
CLIENT_CACHE_TTL = 300  # 5 минут

# Настройки для работы с Google API
GOOGLE_API_DELAY = float(os.getenv('GOOGLE_API_DELAY', '1.0'))  # Задержка между запросами в секундах
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))  # Максимальное количество попыток
RETRY_DELAY = float(os.getenv('RETRY_DELAY', '2.0'))  # Задержка между попытками

# Простой health check эндпоинт для Render.com
@app.get("/health")
async def health_check():
    """Простой health check для Render.com"""
    return {"status": "healthy", "message": "Backend is running", "timestamp": datetime.now().isoformat()}

@app.get("/")
async def root():
    """Корневой эндпоинт для проверки доступности"""
    return {"status": "ok", "message": "XLS Import API is running", "timestamp": datetime.now().isoformat()}

# Обработчик для OPTIONS запросов (CORS preflight)
@app.options("/{full_path:path}")
async def options_handler(full_path: str):
    """Обработчик для CORS preflight запросов"""
    return {"message": "OK"}

# Тестовый эндпоинт для проверки CORS


# Настройки безопасности
SECRET_KEY = "your-secret-key-here"  # В продакшене использовать переменную окружения
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Данные для авторизации
USERS = {
    "admin": "portcomfort"
}

# Хранение статусов задач
task_status = {}

# Путь к файлу настроек
SETTINGS_FILE = "settings.json"

# Модели данных
class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    token: str

class SettingsResponse(BaseModel):
    settings: Dict[str, str]

class TaskStatus(BaseModel):
    task_id: str
    status: str
    progress: Optional[Dict[str, int]] = None
    errors: Optional[List[Dict[str, str]]] = None
    success: Optional[List[str]] = None

# Функции для работы с настройками
def load_settings() -> Dict[str, str]:
    """Загружает настройки из файла"""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_settings_to_file(settings: Dict[str, str]):
    """Сохраняет настройки в файл"""
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

# Функции для работы с токенами
def create_access_token(data: dict):
    from jose import JWTError, jwt
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    from jose import JWTError, jwt
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return username
    except JWTError:
        return None

# Зависимость для проверки авторизации
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Получает текущего пользователя из токена"""
    try:
        username = verify_token(credentials.credentials)
        if username is None:
            logger.warning("Попытка доступа с неверным токеном")
            raise HTTPException(status_code=401, detail="Неверный токен")
        return username
    except Exception as e:
        logger.error(f"Ошибка при проверке токена: {str(e)}")
        raise HTTPException(status_code=401, detail="Ошибка проверки токена")

# Функции для работы с Google Sheets
def clear_google_client_cache():
    """Очищает кэш клиента Google Sheets"""
    global _google_client_cache, _last_client_creation
    _google_client_cache = None
    _last_client_creation = 0
    logger.info("Кэш клиента Google Sheets очищен")

@lru_cache(maxsize=1)
def get_google_sheets_client():
    """Получает клиент для работы с Google Sheets"""
    global _google_client_cache, _last_client_creation
    current_time = time.time()
    
    if _google_client_cache and (current_time - _last_client_creation) < CLIENT_CACHE_TTL:
        return _google_client_cache
    
    for attempt in range(MAX_RETRIES):
        try:
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # Сначала пробуем получить из переменной окружения
            google_credentials = os.getenv('GOOGLE_CREDENTIALS')
            if google_credentials:
                import json
                credentials_dict = json.loads(google_credentials)
                credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
            else:
                credentials = Credentials.from_service_account_file('service-account.json', scopes=scopes)
            
            client = gspread.authorize(credentials)
            
            _google_client_cache = client
            _last_client_creation = current_time
            return client
            
        except FileNotFoundError:
            logger.error("Файл service-account.json не найден")
            raise Exception("Файл service-account.json не найден")
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                logger.warning(f"Попытка {attempt + 1} создания клиента не удалась, повторяем через {RETRY_DELAY} сек: {str(e)}")
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"Ошибка при создании клиента Google Sheets после {MAX_RETRIES} попыток: {str(e)}")
                raise Exception(f"Ошибка при создании клиента Google Sheets после {MAX_RETRIES} попыток: {str(e)}")

def extract_sheet_id_from_url(url: str) -> str:
    """Извлекает ID таблицы из URL"""
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', url)
    if not match:
        raise Exception("Неверный формат URL Google Sheets")
    return match.group(1)

def create_or_replace_sheet_with_date(sheet_url: str, date_str: str) -> str:
    """Создает новый лист с датой или заменяет существующий"""
    for attempt in range(MAX_RETRIES):
        try:
            client = get_google_sheets_client()
            sheet_id = extract_sheet_id_from_url(sheet_url)
            spreadsheet = client.open_by_key(sheet_id)
            
            # Задержка между запросами
            time.sleep(GOOGLE_API_DELAY)
            
            # Получаем все листы
            worksheets = spreadsheet.worksheets()
            if not worksheets:
                raise Exception("В таблице нет листов")
            
            # Проверяем, существует ли уже лист с такой датой
            existing_sheet = None
            for worksheet in worksheets:
                if worksheet.title == date_str:
                    existing_sheet = worksheet
                    break
            
            if existing_sheet:
                # Удаляем существующий лист
                spreadsheet.del_worksheet(existing_sheet)
                
                # Задержка между запросами
                time.sleep(GOOGLE_API_DELAY)
            
            # Копируем последний лист (который не является удаленным)
            remaining_worksheets = spreadsheet.worksheets()
            if not remaining_worksheets:
                raise Exception("Нет доступных листов для копирования")
            
            last_sheet = remaining_worksheets[-1]
            new_sheet = spreadsheet.duplicate_sheet(last_sheet.id, insert_sheet_index=len(remaining_worksheets))
            new_sheet.update_title(date_str)
            
            return date_str
            
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                logger.warning(f"Попытка {attempt + 1} не удалась, повторяем через {RETRY_DELAY} сек: {str(e)}")
                time.sleep(RETRY_DELAY)
            else:
                raise Exception(f"Ошибка при создании/замене листа после {MAX_RETRIES} попыток: {str(e)}")

def create_sheet_with_date(sheet_url: str, date_str: str) -> str:
    """Создает новый лист с датой и возвращает его название (устаревшая функция)"""
    return create_or_replace_sheet_with_date(sheet_url, date_str)

def parse_date(date_str: str) -> Optional[datetime]:
    """Парсит дату в формате DD.MM.YYYY"""
    if not date_str:
        return None
    
    date_str = date_str.strip()
    
    try:
        # Основной формат DD.MM.YYYY
        return datetime.strptime(date_str, "%d.%m.%Y")
    except ValueError:
        pass
    
    try:
        # Формат DD.MM.YY
        return datetime.strptime(date_str, "%d.%m.%y")
    except ValueError:
        pass
    
    try:
        # Формат YYYY-MM-DD
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        pass
    
    return None

def get_city_from_object_name(object_name: str, settings: Dict[str, str]) -> Optional[str]:
    """Извлекает город из названия объекта и сопоставляет с настройками"""
    if not object_name:
        return None
    
    # Берём первое слово
    first_word = object_name.split()[0].strip()
    
    # Специальная обработка для "Сергиев Посад"
    if first_word == "Сергиев":
        return "Сергиев Посад"
    
    # Ищем город в настройках
    for city in settings.keys():
        if city.startswith(first_word):
            return city
    
    return None

def calculate_room_nights_and_income(check_in: str, check_out: str, total_amount: str) -> List[Tuple[datetime, int, float]]:
    """Рассчитывает КН и Доход для каждого дня между заездом и выездом"""
    try:
        check_in_date = parse_date(check_in)
        check_out_date = parse_date(check_out)
        
        if not check_in_date or not check_out_date:
            return []
        
        if check_in_date >= check_out_date:
            return []
        
        # Проверяем сумму на None и пустые значения
        if not total_amount or total_amount is None:
            return []
        
        # Парсим сумму
        amount = float(total_amount.replace(',', '.').replace(' ', ''))
        
        # Считаем количество ночей
        nights = (check_out_date - check_in_date).days
        
        if nights <= 0:
            return []
        
        # Доход за ночь
        income_per_night = amount / nights
        
        result = []
        current_date = check_in_date
        
        # Для каждой ночи (кроме дня выезда)
        for i in range(nights):
            result.append((current_date, 1, income_per_night))
            current_date += timedelta(days=1)
        
        # День выезда - 0 КН, 0 Доход
        result.append((check_out_date, 0, 0))
        
        return result
    except (ValueError, TypeError):
        return []

def find_date_row_in_sheet(sheet, target_date: datetime) -> Optional[int]:
    """Находит строку с датой в столбце B (индекс 1)"""
    try:
        # Получаем все значения из столбца B
        column_b = sheet.col_values(2)  # Столбец B = индекс 1
        
        for row_idx, date_str in enumerate(column_b, start=1):
            if not date_str:
                continue
            
            # Парсим дату из ячейки
            parsed_date = parse_date(date_str)
            if parsed_date and parsed_date.date() == target_date.date():
                return row_idx
        
        return None
    except Exception as e:
        logger.error(f"Ошибка при поиске даты: {str(e)}")
        return None

def write_data_to_sheet(sheet_url: str, sheet_name: str, processed_data: Dict[datetime, Dict[str, float]]):
    """Записывает обработанные данные в Google Sheets"""
    for attempt in range(MAX_RETRIES):
        try:
            client = get_google_sheets_client()
            sheet_id = extract_sheet_id_from_url(sheet_url)
            spreadsheet = client.open_by_key(sheet_id)
            
            # Задержка между запросами
            time.sleep(GOOGLE_API_DELAY)
            
            sheet = spreadsheet.worksheet(sheet_name)
            
            # Получаем все значения из столбца B одним запросом
            column_b = sheet.col_values(2)  # Столбец B = индекс 1
            
            # Задержка между запросами
            time.sleep(GOOGLE_API_DELAY)
            
            # Создаем словарь для быстрого поиска дат
            date_to_row = {}
            for row_idx, date_str in enumerate(column_b, start=1):
                if not date_str:
                    continue
                
                parsed_date = parse_date(date_str)
                if parsed_date:
                    date_to_row[parsed_date.date()] = row_idx
            
            # Подготавливаем данные для массового обновления
            updates = []
            
            # Для каждой даты ищем строку и подготавливаем обновления
            for date, data in processed_data.items():
                target_date = date.date()
                if target_date in date_to_row:
                    row_idx = date_to_row[target_date]
                    
                    # Добавляем обновления в список
                    updates.append({
                        'range': f'E{row_idx}',
                        'values': [[data['kn']]]
                    })
                    updates.append({
                        'range': f'H{row_idx}',
                        'values': [[data['income']]]
                    })
            
            # Выполняем массовое обновление
            if updates:
                sheet.batch_update(updates)
            
            return  # Успешно завершили
                
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                logger.warning(f"Попытка {attempt + 1} не удалась, повторяем через {RETRY_DELAY} сек: {str(e)}")
                time.sleep(RETRY_DELAY)
            else:
                raise Exception(f"Ошибка при записи данных в таблицу после {MAX_RETRIES} попыток: {str(e)}")

def process_xls_data(data: List[List[str]], settings: Dict[str, str]) -> Dict[str, Dict[datetime, Dict[str, float]]]:
    """Обрабатывает данные XLS и группирует по городам"""
    city_data = {}
    warnings = []
    
    for row_idx, row in enumerate(data, start=1):
        if len(row) < 8:  # Нужно минимум 8 столбцов
            continue
        
        # Извлекаем данные из строки
        object_name = row[0] if len(row) > 0 and row[0] else ""  # 1 столбец - объект
        check_in = row[1] if len(row) > 1 and row[1] else ""     # 2 столбец - заезд
        check_out = row[2] if len(row) > 2 and row[2] else ""    # 3 столбец - выезд
        total_amount = row[6] if len(row) > 6 and row[6] else "" # 7 столбец - сумма
        
        # Проверяем, что все необходимые поля заполнены
        if not object_name or not check_in or not check_out or not total_amount:
            warnings.append(f"Строка {row_idx}: Пропущена - не все поля заполнены")
            continue
        
        # Получаем город из названия объекта
        city = get_city_from_object_name(object_name, settings)
        
        if not city:
            continue  # Пропускаем строки без города из настроек
        
        # Проверяем формат дат
        if not parse_date(check_in) or not parse_date(check_out):
            warnings.append(f"Строка {row_idx}: Неверный формат даты (заезд: {check_in}, выезд: {check_out})")
            continue
        
        # Рассчитываем КН и Доход
        calculations = calculate_room_nights_and_income(check_in, check_out, total_amount)
        if not calculations:
            warnings.append(f"Строка {row_idx}: Ошибка расчёта КН/Дохода")
            continue
        
        # Группируем данные по городу и дате
        if city not in city_data:
            city_data[city] = {}
        
        for date, kn, income in calculations:
            if date not in city_data[city]:
                city_data[city][date] = {'kn': 0, 'income': 0}
            
            city_data[city][date]['kn'] += kn
            city_data[city][date]['income'] += income
    
    return city_data, warnings

# Функция для обработки только XML Spreadsheet 2003

def parse_excel_xml_2003(file_path: str) -> list:
    """Парсит Excel XML Spreadsheet 2003 и возвращает данные как двумерный массив"""
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        # Пространство имён для XML Spreadsheet 2003
        ns = {'ss': 'urn:schemas-microsoft-com:office:spreadsheet'}
        # Берём первый Worksheet
        worksheet = root.find('.//ss:Worksheet', ns)
        if worksheet is None:
            raise Exception('Worksheet не найден')
        table = worksheet.find('.//ss:Table', ns)
        if table is None:
            raise Exception('Table не найдена')
        data = []
        for row in table.findall('ss:Row', ns):
            row_data = []
            for cell in row.findall('ss:Cell', ns):
                data_elem = cell.find('ss:Data', ns)
                value = data_elem.text if data_elem is not None else ''
                row_data.append(value)
            data.append(row_data)
        return data
    except Exception as e:
        raise Exception(f"Ошибка при парсинге XML Spreadsheet 2003: {str(e)}")

# Фоновая задача для обработки файла
async def process_file_task(task_id: str, file_path: str):
    """Фоновая задача для обработки XLS файла"""
    import asyncio
    
    try:
        # Обновляем статус при начале обработки
        task_status[task_id]["success"].append("Начинаем обработку файла...")
        
        # Загружаем настройки
        settings = load_settings()
        task_status[task_id]["success"].append("Загружены настройки системы")
        
        # Парсим Excel файл
        data = parse_excel_xml_2003(file_path)
        task_status[task_id]["success"].append(f"Файл Excel обработан - {len(data)} строк данных")
        
        # Обрабатываем данные XLS
        city_data, warnings = process_xls_data(data, settings)
        task_status[task_id]["success"].append(f"Данные сгруппированы по городам - найдено {len(city_data)} городов с данными")
        
        # Получаем текущую дату в формате DDMMYY
        date_str = datetime.now().strftime("%d%m%y")
        
        # Список городов
        cities = [
            'Балашиха', 'Железнодорожный', 'Жуковский', 'Ивантеевка', 'Казань',
            'Королев', 'Люберцы', 'Мытищи', 'Ногинск', 'Пушкино',
            'Раменское', 'Сергиев Посад', 'Фрязино', 'Щелково', 'Электросталь'
        ]
        
        total_cities = len(cities)
        current_progress = 0
        errors = []
        
        # Добавляем предупреждения в ошибки
        for warning in warnings:
            errors.append({"city": "Общие", "message": warning})
        
        # Обновляем статус
        task_status[task_id]["progress"]["current"] = current_progress
        task_status[task_id]["errors"] = errors
        
        # Обрабатываем каждый город
        for i, city in enumerate(cities, 1):
            try:
                if city in settings and settings[city]:
                    # Проверяем, есть ли данные для этого города
                    if city in city_data and city_data[city]:
                        logger.info(f"Начинаем обработку города: {city}")
                        task_status[task_id]["success"].append(f"Начинаем обработку города: {city}")
                        
                        # Обновляем статус после каждого шага
                        task_status[task_id]["progress"]["current"] = current_progress
                        task_status[task_id]["progress"]["current_city"] = city
                        task_status[task_id]["errors"] = errors
                        
                        # Создаем лист с датой
                        sheet_name = create_sheet_with_date(settings[city], date_str)
                        task_status[task_id]["success"].append(f"Создан лист {sheet_name} для города {city}")
                        
                        # Записываем обработанные данные
                        write_data_to_sheet(settings[city], sheet_name, city_data[city])
                        
                        logger.info(f"Город {city} обработан успешно - {len(city_data[city])} дат")
                        task_status[task_id]["success"].append(f"Город {city} обработан успешно - {len(city_data[city])} дат")
                    else:
                        logger.info(f"Город {city} - нет данных для обработки")
                        task_status[task_id]["success"].append(f"Город {city} - нет данных для обработки")
                else:
                    logger.warning(f"Город {city} - ссылка на таблицу не настроена")
                    errors.append({"city": city, "message": "Ссылка на таблицу не настроена"})
            except Exception as e:
                logger.error(f"Ошибка при обработке города {city}: {str(e)}")
                errors.append({"city": city, "message": str(e)})
                
                # Добавляем дополнительную задержку при ошибке
                await asyncio.sleep(RETRY_DELAY)
            
            current_progress += 1
            task_status[task_id]["progress"]["current"] = current_progress
            task_status[task_id]["progress"]["total"] = total_cities
            task_status[task_id]["progress"]["current_city"] = city
            task_status[task_id]["errors"] = errors

            
            # Добавляем задержку между обработкой городов для избежания превышения квоты
            if i < len(cities):  # Не делаем задержку после последнего города
                await asyncio.sleep(GOOGLE_API_DELAY * 3)  # Увеличиваем задержку
        
        # Завершаем задачу
        task_status[task_id]["success"].append("Обработка всех городов завершена")
        task_status[task_id]["status"] = "completed"

        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Критическая ошибка в задаче {task_id}: {error_details}")
        task_status[task_id] = {
            "status": "failed",
            "error": str(e),
            "error_details": error_details,
            "success": task_status.get(task_id, {}).get("success", []) + [f"Ошибка: {str(e)}"]
        }
    finally:
        # Удаляем временный файл
        if os.path.exists(file_path):
            os.remove(file_path)

# API endpoints
@app.post("/api/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Авторизация пользователя"""
    try:
        if request.username in USERS and USERS[request.username] == request.password:
            token = create_access_token(data={"sub": request.username})
            logger.info(f"Успешная авторизация пользователя: {request.username}")
            return LoginResponse(token=token)
        else:
            logger.warning(f"Неудачная попытка авторизации для пользователя: {request.username}")
            raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при авторизации: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка при авторизации")

@app.post("/api/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user)
):
    """Загрузка Excel файла"""
    try:

        
        if not (file.filename.endswith('.xls') or file.filename.endswith('.xlsx')):
            logger.warning(f"Попытка загрузки неподдерживаемого файла: {file.filename}")
            raise HTTPException(status_code=400, detail="Поддерживаются только файлы .xls и .xlsx")
        
        # Создаем уникальный ID задачи
        task_id = str(uuid.uuid4())
        
        # Сохраняем файл временно с правильным расширением
        file_extension = '.xlsx' if file.filename.endswith('.xlsx') else '.xls'
        file_path = f"temp_{task_id}{file_extension}"
        
        try:
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
        except Exception as e:
            logger.error(f"Ошибка при сохранении файла {file.filename}: {str(e)}")
            raise HTTPException(status_code=500, detail="Ошибка при сохранении файла")
        
        # Инициализируем статус задачи
        task_status[task_id] = {
            "status": "processing",
            "progress": {"current": 0, "total": 15},
            "errors": [],
            "success": ["Задача создана, ожидание начала обработки..."]
        }
        
        logger.info(f"Создана задача {task_id} для файла {file.filename}")
        
        # Запускаем фоновую задачу в отдельном потоке
        import asyncio
        asyncio.create_task(process_file_task(task_id, file_path))
        
        return {"task_id": task_id, "message": "Файл загружен и начата обработка"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Неожиданная ошибка при загрузке файла: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

@app.get("/api/status/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: str = Depends(get_current_user)
):
    """Получение статуса обработки задачи"""
    try:
        # Быстрая проверка без блокировки
        if task_id not in task_status:
            logger.warning(f"Запрос статуса для несуществующей задачи {task_id}")
            raise HTTPException(status_code=404, detail="Задача не найдена")
        
        # Возвращаем копию статуса, чтобы избежать блокировки
        status_copy = task_status[task_id].copy()
        return status_copy
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении статуса задачи {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка при получении статуса задачи")



@app.get("/api/settings")
async def get_settings(current_user: str = Depends(get_current_user)):
    """Получение настроек"""
    try:
        settings = load_settings()
        return settings
    except Exception as e:
        logger.error(f"Ошибка при загрузке настроек: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка при загрузке настроек")

@app.post("/api/settings")
async def save_settings(
    settings: Dict[str, str],
    current_user: str = Depends(get_current_user)
):
    try:
        logger.info(f"Сохранение настроек пользователем {current_user}")
        save_settings_to_file(settings)
        return {"message": "Настройки сохранены"}
    except Exception as e:
        logger.error(f"Ошибка при сохранении настроек: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка при сохранении настроек")

@app.post("/api/clear-cache")
async def clear_cache(current_user: str = Depends(get_current_user)):
    """Очищает кэш клиента Google Sheets"""
    try:
        clear_google_client_cache()
        return {"message": "Кэш очищен"}
    except Exception as e:
        logger.error(f"Ошибка при очистке кэша: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка при очистке кэша")

@app.post("/api/clear-today-sheets")
async def clear_today_sheets(current_user: str = Depends(get_current_user)):
    """Удаляет все листы с сегодняшней датой во всех таблицах"""
    try:
        settings = load_settings()
        date_str = datetime.now().strftime("%d%m%y")
        
        results = []
        for city, sheet_url in settings.items():
            try:
                client = get_google_sheets_client()
                sheet_id = extract_sheet_id_from_url(sheet_url)
                spreadsheet = client.open_by_key(sheet_id)
                
                # Задержка между запросами
                time.sleep(GOOGLE_API_DELAY)
                
                # Ищем лист с сегодняшней датой
                worksheets = spreadsheet.worksheets()
                for worksheet in worksheets:
                    if worksheet.title == date_str:
                        spreadsheet.del_worksheet(worksheet)
                        results.append(f"✅ {city}: лист {date_str} удален")
                        break
                else:
                    results.append(f"ℹ️ {city}: лист {date_str} не найден")
                    
            except Exception as e:
                logger.error(f"Ошибка при очистке листа для города {city}: {str(e)}")
                results.append(f"❌ {city}: ошибка - {str(e)}")
        
        return {
            "message": f"Очистка листов с датой {date_str} завершена",
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Ошибка при очистке листов: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при очистке листов: {str(e)}")

# Убираем SPA fallback роут, так как фронтенд теперь отдельный сервис

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        loop="asyncio",
        timeout_keep_alive=120,  # Увеличиваем keep-alive таймаут
        timeout_graceful_shutdown=30  # Увеличиваем graceful shutdown таймаут
    ) 