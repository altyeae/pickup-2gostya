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
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="XLS Import API", version="1.0.0")

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Монтируем статические файлы фронтенда (если папка существует)
import os
if os.path.exists("build/static"):
    app.mount("/static", StaticFiles(directory="build/static"), name="static")

# Обработчик для корневого маршрута
@app.get("/")
async def serve_index():
    """Обработчик для корневого маршрута"""
    try:
        if os.path.exists("build/index.html"):
            with open("build/index.html", "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        else:
            return HTMLResponse(content="<h1>Приложение загружается...</h1>")
    except Exception as e:
        return HTMLResponse(content=f"<h1>Ошибка загрузки: {str(e)}</h1>")





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
    username = verify_token(credentials.credentials)
    if username is None:
        raise HTTPException(status_code=401, detail="Неверный токен")
    return username

# Функции для работы с Google Sheets
def get_google_sheets_client():
    """Получает клиент для работы с Google Sheets"""
    try:
        print("DEBUG: Создаем клиент Google Sheets")
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        print(f"DEBUG: Используем scopes: {scopes}")
        
        # Сначала пробуем получить из переменной окружения
        google_credentials = os.getenv('GOOGLE_CREDENTIALS')
        if google_credentials:
            print("DEBUG: Используем credentials из переменной окружения")
            import json
            credentials_dict = json.loads(google_credentials)
            credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
        else:
            print("DEBUG: Используем файл service-account.json")
            credentials = Credentials.from_service_account_file('service-account.json', scopes=scopes)
        
        print(f"DEBUG: Учетные данные созданы: {credentials.service_account_email}")
        
        client = gspread.authorize(credentials)
        print("DEBUG: Клиент Google Sheets создан успешно")
        return client
    except FileNotFoundError:
        print("DEBUG: Файл service-account.json не найден")
        raise Exception("Файл service-account.json не найден")
    except Exception as e:
        print(f"DEBUG: Ошибка при создании клиента: {str(e)}")
        raise Exception(f"Ошибка при создании клиента Google Sheets: {str(e)}")

def extract_sheet_id_from_url(url: str) -> str:
    """Извлекает ID таблицы из URL"""
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', url)
    if not match:
        raise Exception("Неверный формат URL Google Sheets")
    return match.group(1)

def create_sheet_with_date(sheet_url: str, date_str: str) -> str:
    """Создает новый лист с датой и возвращает его название"""
    try:
        client = get_google_sheets_client()
        sheet_id = extract_sheet_id_from_url(sheet_url)
        spreadsheet = client.open_by_key(sheet_id)
        
        # Получаем все листы и находим последний по дате
        worksheets = spreadsheet.worksheets()
        if not worksheets:
            raise Exception("В таблице нет листов")
        
        # Копируем последний лист
        last_sheet = worksheets[-1]
        new_sheet = spreadsheet.duplicate_sheet(last_sheet.id, insert_sheet_index=len(worksheets))
        new_sheet.update_title(date_str)
        
        return date_str
    except Exception as e:
        raise Exception(f"Ошибка при создании листа: {str(e)}")

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
    
    print(f"DEBUG: Не удалось распарсить дату: '{date_str}'")
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
        
        print(f"DEBUG: Ищем дату {target_date.strftime('%d.%m.%Y')} в {len(column_b)} строках столбца B")
        
        for row_idx, date_str in enumerate(column_b, start=1):
            if not date_str:
                continue
            
            print(f"DEBUG: Строка {row_idx}: проверяем '{date_str}'")
            
            # Парсим дату из ячейки
            parsed_date = parse_date(date_str)
            if parsed_date and parsed_date.date() == target_date.date():
                print(f"DEBUG: Найдено совпадение в строке {row_idx}")
                return row_idx
        
        print(f"DEBUG: Дата {target_date.strftime('%d.%m.%Y')} не найдена")
        return None
    except Exception as e:
        print(f"DEBUG: Ошибка при поиске даты: {str(e)}")
        return None

def write_data_to_sheet(sheet_url: str, sheet_name: str, processed_data: Dict[datetime, Dict[str, float]]):
    """Записывает обработанные данные в Google Sheets"""
    try:
        print(f"DEBUG: Записываем данные в {sheet_name} для {len(processed_data)} дат")
        
        client = get_google_sheets_client()
        sheet_id = extract_sheet_id_from_url(sheet_url)
        spreadsheet = client.open_by_key(sheet_id)
        sheet = spreadsheet.worksheet(sheet_name)
        
        # Получаем все значения из столбца B одним запросом
        column_b = sheet.col_values(2)  # Столбец B = индекс 1
        print(f"DEBUG: Получен столбец B с {len(column_b)} строками")
        
        # Подробная отладка столбца B
        print("DEBUG: Содержимое столбца B:")
        for i, value in enumerate(column_b[:20], 1):  # Показываем первые 20 строк
            print(f"  Строка {i}: '{value}' (тип: {type(value)})")
        
        # Создаем словарь для быстрого поиска дат
        date_to_row = {}
        for row_idx, date_str in enumerate(column_b, start=1):
            if not date_str:
                continue
            
            print(f"DEBUG: Обрабатываем строку {row_idx}: '{date_str}'")
            parsed_date = parse_date(date_str)
            if parsed_date:
                print(f"DEBUG: Успешно распарсили дату: {parsed_date.strftime('%d.%m.%Y')}")
                date_to_row[parsed_date.date()] = row_idx
            else:
                print(f"DEBUG: Не удалось распарсить дату: '{date_str}'")
        
        print(f"DEBUG: Найдено {len(date_to_row)} дат в столбце B")
        print(f"DEBUG: Доступные даты: {list(date_to_row.keys())}")
        
        # Подготавливаем данные для массового обновления
        updates = []
        
        # Для каждой даты ищем строку и подготавливаем обновления
        for date, data in processed_data.items():
            target_date = date.date()
            print(f"DEBUG: Ищем дату {target_date} (из {date.strftime('%d.%m.%Y')})")
            if target_date in date_to_row:
                row_idx = date_to_row[target_date]
                print(f"DEBUG: Найдена строка {row_idx} для даты {date.strftime('%d.%m.%Y')}, записываем КН={data['kn']}, Доход={data['income']}")
                
                # Добавляем обновления в список
                updates.append({
                    'range': f'E{row_idx}',
                    'values': [[data['kn']]]
                })
                updates.append({
                    'range': f'H{row_idx}',
                    'values': [[data['income']]]
                })
            else:
                print(f"DEBUG: Дата {date.strftime('%d.%m.%Y')} (дата: {target_date}) не найдена в столбце B")
        
        # Выполняем массовое обновление
        if updates:
            print(f"DEBUG: Выполняем {len(updates)} обновлений")
            sheet.batch_update(updates)
        else:
            print("DEBUG: Нет данных для обновления")
                
    except Exception as e:
        print(f"DEBUG: Ошибка при записи данных: {str(e)}")
        raise Exception(f"Ошибка при записи данных в таблицу: {str(e)}")

def process_xls_data(data: List[List[str]], settings: Dict[str, str]) -> Dict[str, Dict[datetime, Dict[str, float]]]:
    """Обрабатывает данные XLS и группирует по городам"""
    city_data = {}
    warnings = []
    
    print(f"DEBUG: Обрабатываем {len(data)} строк данных")
    print(f"DEBUG: Настройки городов: {list(settings.keys())}")
    
    for row_idx, row in enumerate(data, start=1):
        if len(row) < 8:  # Нужно минимум 8 столбцов
            continue
        
        # Извлекаем данные из строки
        object_name = row[0] if len(row) > 0 and row[0] else ""  # 1 столбец - объект
        check_in = row[1] if len(row) > 1 and row[1] else ""     # 2 столбец - заезд
        check_out = row[2] if len(row) > 2 and row[2] else ""    # 3 столбец - выезд
        total_amount = row[6] if len(row) > 6 and row[6] else "" # 7 столбец - сумма
        
        print(f"DEBUG: Строка {row_idx}: объект='{object_name}', заезд='{check_in}', выезд='{check_out}', сумма='{total_amount}'")
        
        # Проверяем, что все необходимые поля заполнены
        if not object_name or not check_in or not check_out or not total_amount:
            warnings.append(f"Строка {row_idx}: Пропущена - не все поля заполнены")
            continue
        
        # Получаем город из названия объекта
        city = get_city_from_object_name(object_name, settings)
        print(f"DEBUG: Строка {row_idx}: найден город '{city}' для объекта '{object_name}'")
        
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
        
        print(f"DEBUG: Строка {row_idx}: рассчитано {len(calculations)} дней для города {city}")
        
        # Группируем данные по городу и дате
        if city not in city_data:
            city_data[city] = {}
        
        for date, kn, income in calculations:
            if date not in city_data[city]:
                city_data[city][date] = {'kn': 0, 'income': 0}
            
            city_data[city][date]['kn'] += kn
            city_data[city][date]['income'] += income
    
    print(f"DEBUG: Итоговые данные по городам: {list(city_data.keys())}")
    for city, dates in city_data.items():
        print(f"DEBUG: {city}: {len(dates)} дат")
    
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
    try:
        # Инициализируем статус
        task_status[task_id] = {
            "status": "processing",
            "progress": {"current": 0, "total": 15},
            "errors": [],
            "success": []
        }
        
        # Загружаем настройки
        settings = load_settings()
        
        # Парсим Excel файл
        data = parse_excel_xml_2003(file_path)
        
        # Обрабатываем данные XLS
        city_data, warnings = process_xls_data(data, settings)
        
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
        success = []
        
        # Добавляем предупреждения в ошибки
        for warning in warnings:
            errors.append({"city": "Общие", "message": warning})
        
        # Обновляем статус
        task_status[task_id]["progress"]["current"] = current_progress
        task_status[task_id]["errors"] = errors
        task_status[task_id]["success"] = success
        
        # Обрабатываем каждый город
        for i, city in enumerate(cities, 1):
            try:
                if city in settings and settings[city]:
                    # Проверяем, есть ли данные для этого города
                    if city in city_data and city_data[city]:
                        # Создаем лист с датой
                        sheet_name = create_sheet_with_date(settings[city], date_str)
                        
                        # Записываем обработанные данные
                        write_data_to_sheet(settings[city], sheet_name, city_data[city])
                        
                        success.append(f"✅ {city} - обработано {len(city_data[city])} дат")
                    else:
                        success.append(f"ℹ️ {city} - нет данных для обработки")
                else:
                    errors.append({"city": city, "message": "❌ Ссылка на таблицу не настроена"})
            except Exception as e:
                errors.append({"city": city, "message": f"❌ {str(e)}"})
            
            current_progress += 1
            task_status[task_id]["progress"]["current"] = current_progress
            task_status[task_id]["errors"] = errors
            task_status[task_id]["success"] = success
        
        # Завершаем задачу
        task_status[task_id]["status"] = "completed"
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Ошибка в задаче {task_id}: {error_details}")  # Логируем для отладки
        task_status[task_id] = {
            "status": "failed",
            "error": str(e),
            "error_details": error_details
        }
    finally:
        # Удаляем временный файл
        if os.path.exists(file_path):
            os.remove(file_path)

# API endpoints
@app.post("/api/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Авторизация пользователя"""
    if request.username in USERS and USERS[request.username] == request.password:
        token = create_access_token(data={"sub": request.username})
        return LoginResponse(token=token)
    else:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")

@app.post("/api/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user)
):
    """Загрузка Excel файла"""
    if not (file.filename.endswith('.xls') or file.filename.endswith('.xlsx')):
        raise HTTPException(status_code=400, detail="Поддерживаются только файлы .xls и .xlsx")
    
    # Создаем уникальный ID задачи
    task_id = str(uuid.uuid4())
    
    # Сохраняем файл временно с правильным расширением
    file_extension = '.xlsx' if file.filename.endswith('.xlsx') else '.xls'
    file_path = f"temp_{task_id}{file_extension}"
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    # Инициализируем статус задачи
    task_status[task_id] = {
        "status": "processing",
        "progress": {"current": 0, "total": 15},
        "errors": [],
        "success": []
    }
    
    print(f"DEBUG: Создана задача {task_id}")
    print(f"DEBUG: Всего задач: {len(task_status)}")
    
    # Запускаем фоновую задачу
    background_tasks.add_task(process_file_task, task_id, file_path)
    
    return {"task_id": task_id, "message": "Файл загружен и начата обработка"}

@app.get("/api/status/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: str = Depends(get_current_user)
):
    """Получение статуса обработки задачи"""
    print(f"DEBUG: Запрос статуса для задачи {task_id}")
    print(f"DEBUG: Доступные задачи: {list(task_status.keys())}")
    
    if task_id not in task_status:
        print(f"DEBUG: Задача {task_id} не найдена")
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    print(f"DEBUG: Возвращаем статус для задачи {task_id}: {task_status[task_id]}")
    return task_status[task_id]

@app.get("/api/settings")
async def get_settings(current_user: str = Depends(get_current_user)):
    """Получение настроек"""
    settings = load_settings()
    return settings

@app.post("/api/settings")
async def save_settings(
    settings: Dict[str, str],
    current_user: str = Depends(get_current_user)
):
    logging.basicConfig(level=logging.INFO)
    logging.info(f"Получены настройки: {settings}")
    save_settings_to_file(settings)
    return {"message": "Настройки сохранены"}

# Обработчик для всех остальных маршрутов (SPA fallback) - должен быть последним
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """Обработчик для SPA - возвращает index.html для всех не-API маршрутов"""
    # Возвращаем index.html для всех остальных маршрутов
    try:
        if os.path.exists("build/index.html"):
            with open("build/index.html", "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        else:
            return HTMLResponse(content="<h1>Приложение загружается...</h1>")
    except Exception as e:
        return HTMLResponse(content=f"<h1>Ошибка загрузки: {str(e)}</h1>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 