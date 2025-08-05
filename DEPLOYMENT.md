# Инструкция по деплою

## 🔐 Настройка Google Sheets API

### 1. Создание нового Service Account

1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте новый проект или выберите существующий
3. Включите Google Sheets API и Google Drive API
4. Создайте Service Account:
   - IAM & Admin → Service Accounts → Create Service Account
   - Название: `import-pickup`
   - Роль: `Editor`

### 2. Создание ключа

1. В созданном Service Account нажмите "Keys" → "Add Key" → "Create new key"
2. Выберите "JSON"
3. Скачайте файл `service-account.json`

### 3. Настройка GitHub Secrets

1. Перейдите в ваш GitHub репозиторий
2. Settings → Secrets and variables → Actions
3. Нажмите "New repository secret"
4. Создайте секрет:
   - **Name:** `GOOGLE_CREDENTIALS`
   - **Value:** Содержимое файла `service-account.json` (весь JSON)

### 4. Настройка Render.com

1. В настройках сервиса на Render.com
2. Environment Variables → Add Environment Variable
3. Создайте переменную:
   - **Key:** `GOOGLE_CREDENTIALS`
   - **Value:** Содержимое файла `service-account.json`

### 5. Предоставление доступа к таблицам

1. Откройте Google таблицы
2. Нажмите "Share" (Поделиться)
3. Добавьте email из service account: `import-pickup@import-pickup.iam.gserviceaccount.com`
4. Дайте права "Editor"

## 🚀 Деплой

После настройки GitHub Secrets и переменных окружения:

1. Запушьте изменения в репозиторий
2. GitHub Actions автоматически соберет и задеплоит приложение
3. Render.com автоматически обновит сервис

## 📝 Примечания

- **НЕ коммитьте** `service-account.json` в репозиторий
- **НЕ коммитьте** `settings.json` в репозиторий
- Используйте только GitHub Secrets и переменные окружения
- Регулярно обновляйте ключи Service Account 