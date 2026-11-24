import asyncio
import logging
import os
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, User

logging.basicConfig(level=logging.INFO)

TG_TOKEN = os.getenv("9203209067:AAH1vmLcl0vBNdDHN4oos5cI6QubH8PM4QM")
ADMIN_ID = int(os.getenv("252380544", "0"))

bot = Bot(token=TG_TOKEN)
dp = Dispatcher()

# Сохраняем базу данных в постоянную папку хостинга /app/data
data_dir = os.getenv("DATA_DIR", ".")
os.makedirs(data_dir, exist_ok=True)
db_path = os.path.join(data_dir, "bot_data.db")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS forecasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT,
        status TEXT DEFAULT 'ожидает'
    )
""")
conn.commit()

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔥 Актуальный прогноз")],
        [KeyboardButton(text="📊 Статистика")]
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
    conn.commit()
    await message.answer(
        "Добро пожаловать! Здесь публикуются ежедневные прогнозы.\n"
        "Используйте кнопки меню ниже.",
        reply_markup=main_kb
    )

@dp.message(Command("post"))
async def cmd_post(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("У вас нет прав для публикации прогнозов.")
        return
    
    forecast_text = message.text.replace("/post", "").strip()
    if not forecast_text:
        await message.answer("Напишите текст прогноза после команды. Пример:\n/post Футбол. Зенит — Спартак: П1 за 1.85")
        return

    cursor.execute("INSERT INTO forecasts (text) VALUES (?)", (forecast_text,))
    conn.commit()

    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()

    sent_count = 0
    for (user_id,) in users:
        try:
            await bot.send_message(user_id, f"📢 **Новый прогноз:**\n\n{forecast_text}", parse_mode="Markdown")
            sent_count += 1
        except Exception:
            pass

    await message.answer(f"✅ Прогноз опубликован и отправлен {sent_count} подписчикам.")

@dp.message(F.text == "🔥 Актуальный прогноз")
async def show_last_forecast(message: types.Message):
    cursor.execute("SELECT text, status FROM forecasts ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    if row:
        text, status = row
        await message.answer(f"📌 **Последний прогноз:**\n\n{text}\n\nСтатус: {status}", parse_mode="Markdown")
    else:
        await message.answer("Прогнозов пока нет.")

@dp.message(F.text == "📊 Статистика")
async def show_stats(message: types.Message):
    cursor.execute("SELECT COUNT(*) FROM forecasts")
    total = cursor.fetchone()[0]
    await message.answer(f"📈 Всего опубликовано прогнозов: {total}")

async def main():
    # Отключаем запрос getMe, который блокируется на общем IP
    bot_id = int(BOT_TOKEN.split(":")[0])
    bot._me = User(id=bot_id, is_bot=True, first_name="ValueDetector", username="bot")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
