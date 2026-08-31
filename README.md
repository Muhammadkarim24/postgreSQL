# Telegram Bot — aiogram + PostgreSQL

Telegram-бот с регистрацией пользователей, профилем, статистикой и админ-панелью. Данные хранятся в PostgreSQL, доступ к Telegram API — через SOCKS5-прокси.

## Стек

- Python 3, [aiogram](https://docs.aiogram.dev/) 3.x
- PostgreSQL + [asyncpg](https://github.com/MagicStack/asyncpg) (пул соединений)
- [APScheduler](https://apscheduler.readthedocs.io/) — под отложенные/периодические задачи
- SOCKS5-прокси для подключения к Telegram API (`aiohttp-socks`)

## Функционал

**Для пользователей**
- `/start` — регистрация, сохранение имени/username в БД
- `/profile` — карточка профиля (имя, username, роль, дата регистрации, последняя активность)
- `/users` — список активных пользователей
- `/stats` — общая статистика (всего пользователей, новых за 7 дней)

**Админ-панель** (`/admin`, доступна только `tg_id` из `ADMIN_IDS`)
- 📊 Статистика (всего / активных / забаненных / новых за неделю)
- 📢 Рассылка сообщения всем активным пользователям
- 🚫 Бан пользователя по `tg_id`
- ✅ Разбан пользователя
- 📋 Список забаненных

## Структура БД

Таблица **users**:

| Поле       | Тип         | Описание                          |
|------------|-------------|-------------------------------------|
| id         | SERIAL PK   | Внутренний ID                      |
| tg_id      | BIGINT      | Telegram ID пользователя (уникальный) |
| name       | TEXT        | Полное имя                          |
| username   | TEXT        | Telegram username                   |
| role       | TEXT        | Роль (по умолчанию `user`)          |
| is_active  | BOOLEAN     | `FALSE` = забанен                   |
| created_at | TIMESTAMPTZ | Дата регистрации                    |
| last_seen  | TIMESTAMPTZ | Последняя активность                |

## Установка

```bash
git clone <ссылка-на-репозиторий>
cd telegram-bot
pip install aiogram asyncpg apscheduler aiohttp-socks
```

Создайте файл `api_token.py`:

```python
TOKEN = "ваш_токен_бота_от_BotFather"
```

Настройте подключение к БД и прокси в начале `postgre.py`:

```python
DB_CONFIG = {
    "user": "postgres",
    "password": "ваш_пароль",
    "database": "имя_бд",
    "host": "127.0.0.1",
    "port": "5432"
}

PROXY_URL = "socks5://127.0.0.1:10808"  # укажите None, если прокси не нужен
```

Впишите свой Telegram ID в список администраторов:

```python
ADMIN_IDS = {ваш_tg_id}
```

## Запуск

```bash
python postgre.py
```

Таблица `users` создаётся автоматически при первом запуске (`init_db()`).

