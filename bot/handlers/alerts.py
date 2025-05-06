# bot/handlers/alerts.py
from aiogram import Router
from aiogram.types import Message
import requests
import os



router = Router()
DJANGO_API_URL = os.getenv("DJANGO_API_URL")
async def send_alert(chat_id, alert_data):
    """
    Отправляет уведомление в Telegram.
    """
    text = (
        f"🚨 Новая тревога!\n"
        f"🔹 ID: {alert_data['aibox_alert_id']}\n"
        f"📅 Время: {alert_data['alert_time']}\n"
        f"📍 Устройство: {alert_data['device']['name']}\n"
        f"🎯 Алгоритм: {alert_data['alg']['name']}\n"
        f"⚠️ Уровень опасности: {alert_data['hazard_level']}\n"
    )

    await bot.send_message(chat_id, text)

async def fetch_alerts():
    """
    Получает новые алерты из Django API и отправляет их в Telegram.
    """
    response = requests.get(f"{DJANGO_API_URL}/alerts/")
    if response.status_code == 200:
        alerts = response.json()
        for alert in alerts:
            await send_alert(chat_id=777079324, alert_data=alert)
