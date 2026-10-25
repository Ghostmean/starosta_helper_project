# starosta_helper_project

Разработка Telegram-приложения для помощи старостам в ведении посещаемости.

## Проектирование

- [Схема базы данных и ER-диаграмма](docs/database-design.md)
- [SQL-схема MySQL 8.0.16+](database/schema.sql)

## Технологии

- Backend и Telegram-бот: Python, FastAPI, aiogram, SQLAlchemy, Alembic.
- База данных: MySQL 8.0.16+.
- Telegram Mini App: React, TypeScript и Vite.
- Node.js и npm используются для сборки фронтенда.

## Подготовка Python backend

Из корня проекта создайте виртуальное окружение и установите зависимости:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
```

Виртуальное окружение и локальные секреты исключены из Git через `.gitignore`.

## Парсер расписания

Парсер поддерживает Excel-файлы `.xls` в формате приложенного расписания деканата: находит лист курса и три столбца группы (дисциплина, преподаватель, аудитория). Для проверки конкретной группы:

```powershell
.\.venv\Scripts\python.exe backend\schedule_parser.py путь\к\расписанию.xls 02121-ДБ
```

В приложенном формате занятие, занимающее весь четырёхстрочный блок пары, считается еженедельным; записи в верхней и нижней позициях блока распознаются как верхняя и нижняя недели. Результат выводится в JSON. Для `.xlsx` потребуется отдельная поддержка; файл расписания пока не загружается в базу автоматически.

## Telegram-бот расписания

1. Создайте бота через [@BotFather](https://t.me/BotFather) и скопируйте токен.
2. Скопируйте `.env.example` в `.env` и укажите `TELEGRAM_BOT_TOKEN` и полный путь к вашему `.xls` в `SCHEDULE_XLS_PATH`.
3. Запустите бота из корня проекта:

```powershell
.\.venv\Scripts\python.exe -m backend.bot
```

Напишите боту `/start` или `/schedule`, затем выберите курс, группу и день. Бот отправит текст со временем пар, предметом, преподавателем, аудиторией и типом недели. `/cancel` отменяет текущий выбор. Токен хранится только в локальном `.env` и не добавляется в Git.

## Тестовый Telegram Mini App

Mini App показывает расписание группы `02371-ДБ` с листа `3 курс`. Пока это read-only MVP: отметки посещаемости не сохраняются.

Локальный запуск backend и интерфейса в двух терминалах:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.api:app --reload
```

```powershell
Set-Location frontend
npm run dev
```

Откройте адрес Vite, указанный в терминале. Для локальной проверки скопируйте `.env.example` в `.env` и проверьте, что `SCHEDULE_XLS_PATH` указывает на Excel-файл.

### Развёртывание на Ubuntu 24.04

1. Вы выбрали корневой домен `ghostmead.com`; его текущий сайт Squarespace будет заменён. Замените DNS A-записи домена на публичный IP VPS `78.17.110.183`, удалите старые A-записи Squarespace и разрешите входящие порты TCP 80/443. Если есть устаревшая AAAA-запись, удалите её или укажите корректный IPv6 VPS. Caddy автоматически выпустит HTTPS-сертификат после обновления DNS.
2. На VPS клонируйте репозиторий и загрузите Excel расписание в корень проекта как `schedule.xls`. Файлы `.xls` исключены из Git.
3. Создайте `deploy/.env` из `deploy/.env.example`; укажите домен Mini App и новый токен бота, полученный через @BotFather. Не добавляйте секреты в репозиторий.
4. Установите Docker и разверните приложение:

```bash
sudo bash deploy/install-docker.sh
bash deploy/deploy.sh
```

После настройки DNS Mini App будет доступен на `https://ghostmead.com/`. В @BotFather задайте домен командой `/setdomain`. Бот настроит кнопку запуска Mini App при старте. Без токена бот пропускается, веб-приложение при этом работает.
