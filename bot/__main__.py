import asyncio
import logging
import os
import requests
import uvicorn
import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from dotenv import load_dotenv
from bot.api import app as fastapi_app
from bot.utils.telegram import setup_telegram, register_user

# Загружаем переменные окружения
load_dotenv()

# Получаем токены из .env
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = "777079324"  # ID чата для отправки тревог
DJANGO_API_URL = os.getenv("DJANGO_API_URL")

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)

# Создаем объекты бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Инициализируем `utils.telegram`
setup_telegram(bot, CHAT_ID, DJANGO_API_URL)


# Обработчик команды /start
@dp.message(CommandStart())
async def start_handler(message: Message):
    args = message.text.split()  # Получаем аргументы команды

    if len(args) > 1 and args[1].startswith("register_"):
        token = args[1].replace("register_", "")
        await register_user(message, token)
    else:
        await message.answer("Привет! Используйте специальную ссылку для регистрации.")


# 📌 Обработчик подтверждения тревоги
@dp.callback_query(F.data.startswith("confirm_"))
async def confirm_alert_handler(callback):
    alert_id = callback.data.split(":")[1]
    url = f"{DJANGO_API_URL}api/algorithms/v1/alerts/{alert_id}/send-action/"

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json={"action": "confirm"})

    if response.status_code == 200:
        await callback.answer("✅ Тревога подтверждена!", show_alert=True)
        await callback.message.delete_reply_markup()
        alert_data = response.json()
        executive_users = alert_data.get("executive_users", [])
        if executive_users:
            await send_alert_to_executives(alert_data)
    else:
        await callback.answer("❌ Ошибка подтверждения тревоги!", show_alert=True)


# 📌 Обработчик отклонения тревоги
@dp.callback_query(F.data.startswith("reject_"))
async def reject_alert_handler(callback):
    alert_id = callback.data.split(":")[1]

    # Асинхронно отправляем отклонение в Django
    url = f"{DJANGO_API_URL}api/algorithms/v1/alerts/{alert_id}/send-action/"

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json={"action": "reject"})

    if response.status_code == 200:
        await callback.answer("🚫 Тревога отклонена!", show_alert=True)
        await callback.message.delete_reply_markup()
    else:
        await callback.answer("❌ Ошибка отклонения тревоги!", show_alert=True)

# 📌 Отправка учредителям
async def send_alert_to_executives(alert_data):
    """Отправляет тревогу учредителям после подтверждения СБ."""
    executive_ids = alert_data.get("executive_users", [])
    message_text = f"⚠️ <b>Подтвержденная тревога!</b>\n\n{alert_data.get('message', '')}"

    tasks = []
    for user_id in executive_ids:
        tasks.append(bot.send_message(chat_id=user_id, text=message_text, parse_mode="HTML"))

    await asyncio.gather(*tasks, return_exceptions=True)

@dp.message(Command("id"))
async def send_chat_id(message: Message):
    await message.answer(f"Ваш chat_id: {message.chat.id}")


@dp.message(Command("stats"))
async def send_statistics(message: Message):
    try:
        url = f"{DJANGO_API_URL}api/algorithms/alert-stats/"  # Убедись, что URL корректный
        async with httpx.AsyncClient() as client:
            response = await client.get(url)

        if response.status_code != 200:
            await message.answer("❌ Не удалось получить статистику.")
            return

        data = response.json()
        text = (
            f"📊 <b>Статистика тревог</b>\n\n"
            f"🔢 Всего тревог: <b>{data['total_alerts']}</b>\n"
            f"✅ Подтверждено: <b>{data['confirmed_alerts']}</b>\n\n"
            f"📌 <b>По алгоритмам:</b>\n"
        )

        for alg in data["algorithms"]:
            text += (
                f"▪️ <b>{alg['name']}</b>: {alg['total']} всего, {alg['confirmed']} подтверждено\n"
            )

        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Ошибка при получении статистики: {e}")
        await message.answer("⚠️ Ошибка при получении статистики.")

# Обработчик всех остальных сообщений
@dp.message()
async def echo_handler(message: Message):
    await message.answer("Бот работает!")

async def start_fastapi():
    """Запускаем FastAPI сервер параллельно боту."""
    config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=8002, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    """Запускает бота и FastAPI сервер одновременно."""
    await asyncio.gather(dp.start_polling(bot), start_fastapi())

if __name__ == "__main__":
    asyncio.run(main())
