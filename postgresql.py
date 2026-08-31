# import psycopg2
import asyncpg
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
import asyncio
from aiogram.filters import CommandStart, Command
from api_token import TOKEN, ADMIN_IDS, DB_CONFIG
from aiogram.client.session.aiohttp import AiohttpSession
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram.client.session.aiohttp import AiohttpSession

# conn = psycopg2.connect(


PROXY_URL = proxy="socks5://127.0.0.1:10808"

_session = AiohttpSession(PROXY_URL) if PROXY_URL else None


bot = Bot(token = TOKEN, session = _session)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

async def init_db():
    conn = await asyncpg.connect(**DB_CONFIG)
    await conn.execute("""
    CREATE TABLE IF NOT EXISTS users(
    id SERIAL PRIMARY KEY, 
    tg_id BIGINT UNIQUE,
    name TEXT
    )
    """)
    await conn.close()

@dp.message(CommandStart())
async def cmd_start(message: Message):
    conn = await asyncpg.connect(**DB_CONFIG)

    await conn.execute("""
        INSERT INTO users(tg_id, name)
        VALUES ($1, $2)
        ON CONFLICT (tg_id) DO NOTHING
""", message.from_user.id, message.from_user.full_name)
    await conn.close()

    await message.answer(f"Assalamu Aleikum, {message.from_user.full_name}!" 
                         f"You are saved in databases!")


@dp.message(Command("users"))
async def cmd_users(message:Message):
    conn = await asyncpg.connect(**DB_CONFIG)
    rows = await conn.fetch("SELECT name FROM users")  
    await conn.close()  

    if rows:
        users_list = "\n".join([row["name"] for row in rows])
        await message.answer("The list of users:\n" + users_list)
    else:
        await message.answer("The database is currently empty yet!")    

async def main():
    await init_db()
    print("Bot started!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())


# cursor = conn.cursor()
# cursor.execute("""
# CREATE TABLE IF NOT EXISTS clients(
# id SERIAL PRIMARY KEY,
# name TEXT,
# phone INTEGER
# )
# """)


# cursor.execute("INSERT INTO clients(name, phone) VALUES (%s, %s)", ("Anis", 992324512)),
# cursor.execute("INSERT INTO clients(name, phone) VALUES (%s, %s)", ("Safar", 992323412)),
# cursor.execute("INSERT INTO clients(name, phone) VALUES (%s, %s)", ("Irshod", 992214512)),
# cursor.execute("INSERT INTO clients(name, phone) VALUES (%s, %s)", ("Faridun", 988324512)),
# cursor.execute("INSERT INTO clients(name, phone) VALUES (%s, %s)", ("Murod", 992324554))

# conn.commit()
# cursor.execute("SELECT * FROM clients")
# rows = cursor.fetchall()
# for row in rows:
#     print(row)
# conn.close()