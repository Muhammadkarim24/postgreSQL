import asyncpg
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from api_token import TOKEN, ADMIN_IDS
from aiogram.client.session.aiohttp import AiohttpSession
from apscheduler.schedulers.asyncio import AsyncIOScheduler

DB_CONFIG = {
    "user": "postgres",
    "password": "314159265",
    "database": "testdb_1",
    "host": "127.0.0.1",
    "port": "5432"
}

PROXY_URL = "socks5://127.0.0.1:10808"
_session = AiohttpSession(proxy=PROXY_URL) if PROXY_URL else None

bot = Bot(token=TOKEN, session=_session)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

db_pool: asyncpg.Pool | None = None




def is_admin(tg_id: int) -> bool:
    return tg_id in ADMIN_IDS


class AdminStates(StatesGroup):
    waiting_broadcast_text = State()
    waiting_ban_id = State()
    waiting_unban_id = State()


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🚫 Забанить", callback_data="admin_ban")],
        [InlineKeyboardButton(text="✅ Разбанить", callback_data="admin_unban")],
        [InlineKeyboardButton(text="📋 Список забаненных", callback_data="admin_banned_list")],
    ])


async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(**DB_CONFIG)

    await db_pool.execute("""
    CREATE TABLE IF NOT EXISTS users_1(
        id SERIAL PRIMARY KEY,
        tg_id BIGINT UNIQUE,
        name TEXT,
        username TEXT,
        role TEXT NOT NULL DEFAULT 'user',
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)


@dp.message(CommandStart())
async def cmd_start(message: Message):
    async with db_pool.acquire() as conn:
        banned = await conn.fetchval(
            "SELECT TRUE FROM users_1 WHERE tg_id = $1 AND is_active = FALSE",
            message.from_user.id
        )
        if banned:
            await message.answer("Вы заблокированы и не можете пользоваться ботом.")
            return

        await conn.execute("""
            INSERT INTO users_1(tg_id, name, username)
            VALUES ($1, $2, $3)
            ON CONFLICT (tg_id) DO UPDATE
                SET name = EXCLUDED.name,
                    username = EXCLUDED.username,
                    last_seen = NOW()
        """, message.from_user.id, message.from_user.full_name, message.from_user.username)

    await message.answer(
        f"Assalamu Aleikum, {message.from_user.full_name}!\n"
        f"Вы сохранены в базе данных!"
    )


@dp.message(Command("profile"))
async def cmd_profile(message: Message):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT name, username, role, created_at, last_seen FROM users_1 WHERE tg_id = $1",
            message.from_user.id
        )

    if not row:
        await message.answer("Вы ещё не зарегистрированы. Отправьте /start")
        return

    username = f"@{row['username']}" if row["username"] else "—"
    await message.answer(
        "Ваш профиль:\n"
        f"Имя: {row['name']}\n"
        f"Username: {username}\n"
        f"Роль: {row['role']}\n"
        f"Дата регистрации: {row['created_at']:%d.%m.%Y %H:%M}\n"
        f"Последняя активность: {row['last_seen']:%d.%m.%Y %H:%M}"
    )


@dp.message(Command("users"))
async def cmd_users(message: Message):
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT name FROM users_1 WHERE is_active = TRUE")

    if rows:
        users_list = "\n".join(row["name"] for row in rows)
        await message.answer("Список пользователей:\n" + users_list)
    else:
        await message.answer("База данных пока пуста!")


@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    async with db_pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM users_1 WHERE is_active = TRUE")
        new_week = await conn.fetchval(
            "SELECT COUNT(*) FROM users_1 WHERE created_at > NOW() - INTERVAL '7 days'"
        )

    await message.answer(
        "Статистика:\n"
        f"Всего пользователей: {total}\n"
        f"Новых за последние 7 дней: {new_week}"
    )


@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к этой команде.")
        return
    await message.answer("Админ-панель:", reply_markup=admin_panel_keyboard())


@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    async with db_pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM users_1")
        active = await conn.fetchval("SELECT COUNT(*) FROM users_1 WHERE is_active = TRUE")
        banned = await conn.fetchval("SELECT COUNT(*) FROM users_1 WHERE is_active = FALSE")
        new_week = await conn.fetchval(
            "SELECT COUNT(*) FROM users_1 WHERE created_at > NOW() - INTERVAL '7 days'"
        )

    await callback.message.answer(
        "Статистика:\n"
        f"Всего пользователей: {total}\n"
        f"Активных: {active}\n"
        f"Забаненных: {banned}\n"
        f"Новых за 7 дней: {new_week}"
    )
    await callback.answer()


@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.message.answer("Отправьте текст рассылки (или /cancel для отмены):")
    await state.set_state(AdminStates.waiting_broadcast_text)
    await callback.answer()


@dp.message(StateFilter(AdminStates.waiting_broadcast_text), Command("cancel"))
async def admin_broadcast_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Рассылка отменена.")


@dp.message(StateFilter(AdminStates.waiting_broadcast_text))
async def admin_broadcast_send(message: Message, state: FSMContext):
    await state.clear()

    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT tg_id FROM users_1 WHERE is_active = TRUE")

    sent, failed = 0, 0
    for row in rows:
        try:
            await bot.send_message(row["tg_id"], message.text)
            sent += 1
        except Exception:
            failed += 1

    await message.answer(f"Рассылка завершена.\nДоставлено: {sent}\nНе доставлено: {failed}")


@dp.callback_query(F.data == "admin_ban")
async def admin_ban_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.message.answer("Отправьте tg_id пользователя для бана (или /cancel):")
    await state.set_state(AdminStates.waiting_ban_id)
    await callback.answer()


@dp.callback_query(F.data == "admin_unban")
async def admin_unban_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.message.answer("Отправьте tg_id пользователя для разбана (или /cancel):")
    await state.set_state(AdminStates.waiting_unban_id)
    await callback.answer()


@dp.message(StateFilter(AdminStates.waiting_ban_id, AdminStates.waiting_unban_id), Command("cancel"))
async def admin_ban_unban_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Действие отменено.")


@dp.message(StateFilter(AdminStates.waiting_ban_id))
async def admin_ban_apply(message: Message, state: FSMContext):
    await state.clear()
    try:
        target_id = int(message.text.strip())
    except ValueError:
        await message.answer("Некорректный tg_id, ожидалось число.")
        return

    async with db_pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE users_1 SET is_active = FALSE WHERE tg_id = $1", target_id
        )

    if result.endswith("0"):
        await message.answer("Пользователь с таким tg_id не найден.")
    else:
        await message.answer(f"Пользователь {target_id} забанен.")


@dp.message(StateFilter(AdminStates.waiting_unban_id))
async def admin_unban_apply(message: Message, state: FSMContext):
    await state.clear()
    try:
        target_id = int(message.text.strip())
    except ValueError:
        await message.answer("Некорректный tg_id, ожидалось число.")
        return

    async with db_pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE users_1 SET is_active = TRUE WHERE tg_id = $1", target_id
        )

    if result.endswith("0"):
        await message.answer("Пользователь с таким tg_id не найден.")
    else:
        await message.answer(f"Пользователь {target_id} разбанен.")


@dp.callback_query(F.data == "admin_banned_list")
async def admin_banned_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT tg_id, name FROM users_1 WHERE is_active = FALSE ORDER BY name"
        )

    if rows:
        text = "\n".join(f"{row['tg_id']} — {row['name']}" for row in rows)
        await callback.message.answer("Забаненные пользователи:\n" + text)
    else:
        await callback.message.answer("Забаненных пользователей нет.")
    await callback.answer()


@dp.message()
async def track_activity(message: Message):
    # обновляем last_seen на любое входящее сообщение от известного пользователя
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE users_1 SET last_seen = NOW() WHERE tg_id = $1",
            message.from_user.id
        )


async def main():
    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())






# import asyncpg
# from aiogram import Bot, Dispatcher, types
# from aiogram.types import Message
# import asyncio
# from aiogram.filters import CommandStart, Command
# from api_token import TOKEN
# from aiogram.client.session.aiohttp import AiohttpSession
# from apscheduler.schedulers.asyncio import AsyncIOScheduler

# DB_CONFIG = {
#     "user": "postgres",
#     "password": "314159265",
#     "database": "testdb_1",
#     "host": "127.0.0.1",
#     "port": "5432"
# }

# PROXY_URL = "socks5://127.0.0.1:10808"
# _session = AiohttpSession(proxy=PROXY_URL) if PROXY_URL else None

# bot = Bot(token=TOKEN, session=_session)
# dp = Dispatcher()
# scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

# db_pool: asyncpg.Pool | None = None

# ADMIN_IDS = {1234567896134320496}  # свой tg_id


# async def init_db():
#     global db_pool
#     db_pool = await asyncpg.create_pool(**DB_CONFIG)

#     await db_pool.execute("""
#     CREATE TABLE IF NOT EXISTS users_1(
#         id SERIAL PRIMARY KEY,
#         tg_id BIGINT UNIQUE,
#         name TEXT,
#         username TEXT,
#         role TEXT NOT NULL DEFAULT 'user',
#         is_active BOOLEAN NOT NULL DEFAULT TRUE,
#         created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
#         last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW()
#     )
#     """)


# @dp.message(CommandStart())
# async def cmd_start(message: Message):
#     async with db_pool.acquire() as conn:
#         await conn.execute("""
#             INSERT INTO users_1(tg_id, name, username)
#             VALUES ($1, $2, $3)
#             ON CONFLICT (tg_id) DO UPDATE
#                 SET name = EXCLUDED.name,
#                     username = EXCLUDED.username,
#                     is_active = TRUE,
#                     last_seen = NOW()
#         """, message.from_user.id, message.from_user.full_name, message.from_user.username)

#     await message.answer(
#         f"Assalamu Aleikum, {message.from_user.full_name}!\n"
#         f"Вы сохранены в базе данных!"
#     )


# @dp.message(Command("profile"))
# async def cmd_profile(message: Message):
#     async with db_pool.acquire() as conn:
#         row = await conn.fetchrow(
#             "SELECT name, username, role, created_at, last_seen FROM users_1 WHERE tg_id = $1",
#             message.from_user.id
#         )

#     if not row:
#         await message.answer("Вы ещё не зарегистрированы. Отправьте /start")
#         return

#     username = f"@{row['username']}" if row["username"] else "—"
#     await message.answer(
#         "Ваш профиль:\n"
#         f"Имя: {row['name']}\n"
#         f"Username: {username}\n"
#         f"Роль: {row['role']}\n"
#         f"Дата регистрации: {row['created_at']:%d.%m.%Y %H:%M}\n"
#         f"Последняя активность: {row['last_seen']:%d.%m.%Y %H:%M}"
#     )


# @dp.message(Command("users"))
# async def cmd_users(message: Message):
#     async with db_pool.acquire() as conn:
#         rows = await conn.fetch("SELECT name FROM users_1 WHERE is_active = TRUE")

#     if rows:
#         users_list = "\n".join(row["name"] for row in rows)
#         await message.answer("Список пользователей:\n" + users_list)
#     else:
#         await message.answer("База данных пока пуста!")


# @dp.message(Command("stats"))
# async def cmd_stats(message: Message):
#     async with db_pool.acquire() as conn:
#         total = await conn.fetchval("SELECT COUNT(*) FROM users_1 WHERE is_active = TRUE")
#         new_week = await conn.fetchval(
#             "SELECT COUNT(*) FROM users_1 WHERE created_at > NOW() - INTERVAL '7 days'"
#         )

#     await message.answer(
#         "Статистика:\n"
#         f"Всего пользователей: {total}\n"
#         f"Новых за последние 7 дней: {new_week}"
#     )


# @dp.message()
# async def track_activity(message: Message):
#     # обновляем last_seen на любое входящее сообщение от известного пользователя
#     async with db_pool.acquire() as conn:
#         await conn.execute(
#             "UPDATE users_1 SET last_seen = NOW() WHERE tg_id = $1",
#             message.from_user.id
#         )


# async def main():
#     await init_db()
#     await dp.start_polling(bot)


# if __name__ == "__main__":
#     asyncio.run(main())