import asyncio
import logging
import os
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, User

logging.basicConfig(level=logging.INFO)

TG_TOKEN = "9203209067:" + "AAHyqOIKyQm3KLtyyiBwizlxnsU_O3qNKdg"

ADMIN_ID = 252380544

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

# --- ЗАКРЫТИЕ ПРОГНОЗОВ (ДЛЯ АДМИНА) ---
async def update_last_forecast_status(message: types.Message, new_status: str):
    if message.from_user.id != ADMIN_ID:
        await message.answer("У вас нет прав для изменения статуса прогнозов.")
        return

    cursor.execute("SELECT id, text, status FROM forecasts ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()

    if not row:
        await message.answer("В базе пока нет ни одного прогноза.")
        return

    forecast_id, text, old_status = row
    cursor.execute("UPDATE forecasts SET status = ? WHERE id = ?", (new_status, forecast_id))
    conn.commit()

    await message.answer(
        f"Статус последнего прогноза (#{forecast_id}) обновлён!\n\n"
        f"📝 {text}\n"
        f"Было: {old_status} ➡️ Стало: **{new_status}**",
        parse_mode="Markdown"
    )

@dp.message(Command("win"))
async def cmd_win(message: types.Message):
    await update_last_forecast_status(message, "✅ Выигрыш")

@dp.message(Command("lose"))
async def cmd_lose(message: types.Message):
    await update_last_forecast_status(message, "❌ Проигрыш")

@dp.message(Command("refund"))
async def cmd_refund(message: types.Message):
    await update_last_forecast_status(message, "🔄 Возврат")


# --- ОБНОВЛЁННАЯ СТАТИСТИКА ---
@dp.message(F.text == "📊 Статистика")
async def show_stats(message: types.Message):
    cursor.execute("SELECT COUNT(*) FROM forecasts")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM forecasts WHERE status = '✅ Выигрыш'")
    wins = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM forecasts WHERE status = '❌ Проигрыш'")
    losses = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM forecasts WHERE status = '🔄 Возврат'")
    refunds = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM forecasts WHERE status = 'ожидает'")
    pending = cursor.fetchone()[0]

    settled = wins + losses
    win_rate = round((wins / settled) * 100, 1) if settled > 0 else 0.0

    stats_text = (
        f"📊 **Статистика прогнозов:**\n\n"
        f"📌 Всего опубликовано: **{total}**\n"
        f"✅ Выигрышей: **{wins}**\n"
        f"❌ Проигрышей: **{losses}**\n"
        f"🔄 Возвратов: **{refunds}**\n"
        f"⏳ Ожидают расчёта: **{pending}**\n\n"
        f"📈 Проходимость: **{win_rate}%**"
    )
    await message.answer(stats_text, parse_mode="Markdown")

from aiogram.utils.backoff import BackoffConfig

async def main():
    bot_id = 9203209067
    bot._me = User(id=bot_id, is_bot=True, first_name="ValueDetector", username="bot")
    # Настраиваем паузу в 40 секунд при лимитах Telegram, чтобы таймер успевал обнулиться
    backoff = BackoffConfig(min_delay=40.0, max_delay=60.0, factor=1.2, jitter=0.1)
    await dp.start_polling(bot, backoff_config=backoff)

if __name__ == "__main__":
    asyncio.run(main())
