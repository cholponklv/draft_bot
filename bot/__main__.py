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
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.api import app as fastapi_app
from bot.utils.telegram import setup_telegram, register_user
from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from fpdf import FPDF
from tempfile import NamedTemporaryFile
import traceback
from aiogram.types import FSInputFile
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

period_map = {
    "day": "Сегодня",
    "week": "Неделя",
    "month": "Месяц",
    "all": "Всё время"
}

class StatsStates(StatesGroup):
    awaiting_dates = State()

class PDFStatsStates(StatesGroup):
    awaiting_dates = State()

@dp.message(Command("stats"))
async def show_stats_periods(message: types.Message):
    kb = InlineKeyboardBuilder()
    
    kb.button(text="Сегодня", callback_data="stats_period:day")
    kb.button(text="Неделя", callback_data="stats_period:week")
    kb.button(text="Месяц", callback_data="stats_period:month")
    kb.button(text="Всё время", callback_data="stats_period:all")
    kb.button(text="📅 Выбрать даты", callback_data="stats_period:custom")

    kb.adjust(2, 2, 1)

    await message.answer("📊 Выберите период:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("stats_period:"))
async def send_statistics(callback: types.CallbackQuery, state: FSMContext):
    period = callback.data.split(":")[1]

    if period == "custom":
        await callback.message.answer("🗓 Введите даты в формате:\n<code>2025-05-05 2025-05-24</code>")
        await state.set_state(StatsStates.awaiting_dates)
        return

    try:
        url = f"{DJANGO_API_URL}api/algorithms/alert-stats/?period={period}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)

        if response.status_code != 200:
            await callback.message.answer("❌ Не удалось получить статистику.")
            return

        data = response.json()
        await callback.message.answer(format_stats(data, period_map.get(period, "Период")), parse_mode="HTML")
    except Exception:
        await callback.message.answer("⚠️ Ошибка при получении статистики.")

@dp.message(StatsStates.awaiting_dates)
async def handle_custom_dates(message: types.Message, state: FSMContext):
    try:
        start_str, end_str = message.text.strip().split()
        url = f"{DJANGO_API_URL}api/algorithms/alert-stats/?start_date={start_str}&end_date={end_str}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)

        if response.status_code != 200:
            await message.answer("❌ Не удалось получить статистику.")
            return

        data = response.json()
        await message.answer(format_stats(data, f"{start_str} – {end_str}"), parse_mode="HTML")
    except Exception:
        await message.answer("⚠️ Неверный формат. Введите даты в виде: 2025-05-05 2025-05-24")
    finally:
        await state.clear()

@dp.message(Command("pdf"))
async def show_pdf_periods(message: types.Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="Сегодня", callback_data="pdf_period:day")
    kb.button(text="Неделя", callback_data="pdf_period:week")
    kb.button(text="Месяц", callback_data="pdf_period:month")
    kb.button(text="Всё время", callback_data="pdf_period:all")
    kb.button(text="📅 Выбрать даты", callback_data="pdf_period:custom")
    kb.adjust(2, 2, 1)
    await message.answer("📄 Выберите период для PDF:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("pdf_period:"))
async def generate_pdf_stats(callback: types.CallbackQuery, state: FSMContext):
    period = callback.data.split(":")[1]
    if period == "custom":
        await callback.message.answer("🗓 Введите даты в формате:\n<code>2025-05-05 2025-05-24</code>")
        await state.set_state(PDFStatsStates.awaiting_dates)
        return
    await fetch_and_send_pdf(callback.message, period)

@dp.message(PDFStatsStates.awaiting_dates)
async def handle_pdf_custom_dates(message: types.Message, state: FSMContext):
    try:
        start_str, end_str = message.text.strip().split()
        await fetch_and_send_pdf(message, "custom", start_str, end_str)
    except Exception:
        await message.answer("⚠️ Неверный формат. Введите даты в виде: 2025-05-05 2025-05-24")
    finally:
        await state.clear()

async def fetch_and_send_pdf(message: types.Message, period: str, start=None, end=None):
    try:
        if period == "custom":
            url = f"{DJANGO_API_URL}api/algorithms/alert-stats/?start_date={start}&end_date={end}"
            label = f"{start} – {end}"
        else:
            url = f"{DJANGO_API_URL}api/algorithms/alert-stats/?period={period}"
            label = period_map.get(period, "Период")

        async with httpx.AsyncClient() as client:
            response = await client.get(url)

        if response.status_code != 200:
            await message.answer("❌ Не удалось получить данные.")
            return

        data = response.json()
        pdf_path = create_stats_pdf(data, label)

        # ✅ используем FSInputFile для корректной отправки
        document = FSInputFile(path=pdf_path, filename="alert_stats.pdf")
        await message.answer_document(document)
        os.remove(pdf_path)  # очищаем временный файл
    except Exception as e:
        print("‼️ Ошибка в fetch_and_send_pdf:", e)
        traceback.print_exc()
        await message.answer("⚠️ Ошибка при создании PDF.")

def create_stats_pdf(data: dict, period: str) -> str:
    try:
        pdf = FPDF()
        pdf.add_page()
        font_path = os.path.join(os.path.dirname(__file__), "DejaVuSans.ttf")
        pdf.add_font("DejaVu", "", font_path, uni=True)
        pdf.set_font("DejaVu", size=12)

        pdf.cell(200, 10, txt=f"Статистика тревог ({period})", ln=True, align="C")
        pdf.ln(10)
        pdf.cell(200, 10, txt=f"Всего тревог: {data['total_alerts']}", ln=True)
        pdf.cell(200, 10, txt=f"Подтверждено: {data['confirmed_alerts']}", ln=True)
        pdf.ln(10)
        pdf.cell(200, 10, txt="По алгоритмам:", ln=True)

        for alg in data["algorithms"]:
            line = f"{alg['name']}: {alg['total']} всего, {alg['confirmed']} подтверждено"
            pdf.cell(200, 10, txt=line, ln=True)

        tmp = NamedTemporaryFile(delete=False, suffix=".pdf")
        pdf.output(tmp.name)
        return tmp.name
    except Exception as e:
        print("‼️ Ошибка в create_stats_pdf():", e)
        traceback.print_exc()
        raise


def format_stats(data: dict, period: str) -> str:
    text = (
        f"📊 <b>Статистика тревог ({period})</b>\n\n"
        f"🔢 Всего тревог: <b>{data['total_alerts']}</b>\n"
        f"✅ Подтверждено: <b>{data['confirmed_alerts']}</b>\n\n"
        f"📌 <b>По алгоритмам:</b>\n"
    )
    for alg in data["algorithms"]:
        text += f"▪️ <b>{alg['name']}</b>: {alg['total']} всего, {alg['confirmed']} подтверждено\n"
    return text
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
