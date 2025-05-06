from fastapi import FastAPI
from bot.schemas import AlertSchema
from bot.utils.telegram import send_alert_to_telegram, send_alert_to_telegram_v2
import logging

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)

app = FastAPI()

@app.post("/alerts/")
async def receive_alert(alert: AlertSchema):
    """Получает данные о тревоге от Django и отправляет их в Telegram."""

    # Отправляем тревогу в Telegram
    print(alert)
    await send_alert_to_telegram_v2(alert)

    return {"error_code": 0, "message": "Alert received successfully", "data": None}
