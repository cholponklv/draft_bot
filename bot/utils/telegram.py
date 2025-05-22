import asyncio
import tempfile
import logging
import aiohttp
from io import BytesIO
from aiogram.types import FSInputFile
import requests
from aiogram import Bot, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import FSInputFile
from urllib.parse import urlparse
from bot.schemas import AlertSchema
import os
BASE_DIR = "/Users/cholponklv/python/visionaibox"
bot: Bot = None
chat_id: str = None
django_api_url: str = None

def setup_telegram(bot_instance: Bot, chat_id_instance: str, api_url: str):
    """Инициализация бота один раз при запуске."""
    global bot, chat_id, django_api_url
    bot = bot_instance
    chat_id = chat_id_instance
    django_api_url = api_url



async def send_alert_to_telegram(alert: AlertSchema):
    """Формирует сообщение о тревоге и отправляет его в Telegram всем указанным пользователям параллельно."""

    if not bot:
        raise RuntimeError("Бот не инициализирован. Вызовите setup_telegram() в __main__.py.")
    print(alert.users_telegram_id)
    telegram_ids = alert.users_telegram_id
    print(alert.users_telegram_id)
    if not telegram_ids:
        print(f"Пропущена отправка тревоги {alert.id} — нет пользователей")
        logging.warning(f"Пропущена отправка тревоги {alert.id} — нет пользователей")
        return

    message_text = (
        f"🚨 <b>Тревога обнаружена!</b>\n\n"
        f"📍 <b>Устройство:</b> {alert.device.name or 'Неизвестно'}\n"
        f"🎥 <b>Камера:</b> {alert.source.source_id} ({alert.source.ipv4})\n"        f"⏰ <b>Время:</b> {alert.alert_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"🤖 <b>Алгоритм:</b> {alert.alg.name}\n"
    )

    image_url = str(alert.image) if alert.image else None

    tasks = []  # Список задач для asyncio.gather()

    for telegram_id in telegram_ids:
        if image_url:
            # Загружаем изображение через aiohttp
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(image_url) as resp:
                        if resp.status == 200:
                            image_bytes = BytesIO(await resp.read())
                            image_bytes.name = f"alert_{alert.id}.jpg"
                            print("suc1")
                            tasks.append(
                                bot.send_photo(
                                    chat_id=telegram_id,
                                    photo=image_bytes,
                                    caption=message_text,
                                    parse_mode="HTML",
                                    reply_markup=reply_markup
                                )
                            )
                        else:
                            logging.error(f"Не удалось загрузить изображение: {resp.status}")
                            tasks.append(
                                bot.send_message(
                                    chat_id=telegram_id,
                                    text=message_text + "\n⚠️ Изображение недоступно.",
                                    parse_mode="HTML",
                                    reply_markup=reply_markup
                                )
                            )
                except Exception as e:
                    logging.error(f"Ошибка при получении изображения: {e}")
                    tasks.append(
                        bot.send_message(
                            chat_id=telegram_id,
                            text=message_text + "\n⚠️ Ошибка при получении изображения.",
                            parse_mode="HTML",
                            reply_markup=reply_markup
                        )
                    )
        else:
            tasks.append(
                bot.send_message(
                    chat_id=telegram_id,
                    text=message_text,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
            )
    # Запускаем отправку сообщений параллельно
    results = await asyncio.gather(*tasks, return_exceptions=True)
    print(results)
    print(alert.image)
    for user_id, result in zip(telegram_ids, results):
        if isinstance(result, Exception):
            print(f"Ошибка отправки тревоги {alert.id} пользователю {user_id}: {result}")
            logging.error(f"Ошибка отправки тревоги {alert.id} пользователю {user_id}: {result}")
        else:
            print(f"Тревога {alert.id} успешно отправлена пользователю {user_id}")
            logging.info(f"Тревога {alert.id} успешно отправлена пользователю {user_id}")


async def send_alert_to_telegram_v2(alert: AlertSchema):
    """Отправляет тревогу в Telegram.
    - Если `for_security=True`, добавляет кнопки подтверждения и отклонения.
    - Если `for_security=False`, отправляет только сообщение без кнопок.
    """

    if not bot:
        raise RuntimeError("Бот не инициализирован. Вызовите setup_telegram() в __main__.py.")
    print(alert.users_telegram_id)
    telegram_ids = alert.users_telegram_id
    print(alert.users_telegram_id)
    if not telegram_ids:
        logging.warning(f"Пропущена отправка тревоги {alert.id} — нет пользователей")
        return

    message_text = (
        f"🚨 <b>Тревога обнаружена!</b>\n\n"
        f"📍 <b>Устройство:</b> {alert.device.name or 'Неизвестно'}\n"
        f"🎥 <b>Камера:</b> {alert.source.source_id} ({alert.source.ipv4})\n"
        f"⏰ <b>Время:</b> {alert.alert_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"🤖 <b>Алгоритм:</b> {alert.alg.name}\n"
        f"🤖 <b>ID тревоги:</b> {alert.aibox_alert_id}\n"
    )

    image_url = str(alert.image) if alert.image else None
    tasks = []  # Список задач для asyncio.gather()
    print(image_url)
    # Добавляем кнопки, если это сообщение для сотрудников службы безопасности
    if alert.for_security:
        keyboard = InlineKeyboardBuilder()
        keyboard.button(
            text="✅ Подтвердить",
            callback_data=f"confirm_alert:{alert.id}"
        )
        keyboard.button(
            text="❌ Отклонить",
            callback_data=f"reject_alert:{alert.id}"
        )
        keyboard.adjust(2)  # Делаем две кнопки в ряд
        reply_markup = keyboard.as_markup()
    else:
        reply_markup = None

    for telegram_id in telegram_ids:
        if image_url:
            url_parts = urlparse(image_url)
            if url_parts.hostname in ("127.0.0.1", "localhost"):
                relative_path = url_parts.path.lstrip("/")
                local_path = os.path.join(BASE_DIR, relative_path)
                if not os.path.exists(local_path):
                    logging.error(f"Файл изображения не найден: {local_path}")
                    continue
                photo = FSInputFile(local_path)
                tasks.append(
                    bot.send_photo(
                        chat_id=telegram_id,
                        photo=photo,
                        caption=message_text,
                        parse_mode="HTML",
                        reply_markup=reply_markup
                    )
                )
            else:
                async def fetch_and_send():
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(image_url) as resp:
                                if resp.status != 200:
                                    raise Exception(f"Ошибка загрузки изображения: {resp.status}")
                                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
                                    tmp_file.write(await resp.read())
                                    tmp_file_path = tmp_file.name
                        photo = FSInputFile(tmp_file_path)
                        await bot.send_photo(
                            chat_id=telegram_id,
                            photo=photo,
                            caption=message_text,
                            parse_mode="HTML",
                            reply_markup=reply_markup
                        )
                        os.remove(tmp_file_path)
                    except Exception as e:
                        logging.error(f"Ошибка отправки тревоги {alert.id} пользователю {telegram_id}: {e}")

                tasks.append(fetch_and_send())
        else:
            tasks.append(
                bot.send_message(
                    chat_id=telegram_id,
                    text=message_text,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
            )
 # Загружаем изображение через aiohttp
            # Запускаем отправку сообщений параллельно
    results = await asyncio.gather(*tasks, return_exceptions=True)
    print(23421)
    for user_id, result in zip(telegram_ids, results):
        if isinstance(result, Exception):
            logging.error(f"Ошибка отправки тревоги {alert.id} пользователю {user_id}: {result}")
        else:
            print(121313)
            logging.info(f"Тревога {alert.id} успешно отправлена пользователю {user_id}")

async def register_user(message: types.Message, token: str):
    """
    Отправляет токен пользователя в Django API для привязки Telegram ID.
    """
    try:
        print(1111)
        url = f"{django_api_url}/api/users/v1/register_telegram/"
        print(2222222)
        response = requests.post(url, json={"telegram_id": message.chat.id, "token": token})
        print(response.status_code)
        data = response.json()
        print(response.status_code)
        if response.status_code == 200:
            print(3333)
            user_info = data.get("user", {})
            company_name = user_info.get("company_name", "Неизвестная компания")
            telegram_username = message.from_user.full_name  # Получаем имя из Telegram

            await message.answer(
                f"✅ <b>{telegram_username}</b>, ваш Telegram успешно привязан!\n"
                f"🏢 <b>Компания:</b> {company_name}",
                parse_mode="HTML"
            )
        else:
            await message.answer(f"❌ Ошибка: {data.get('error', 'Попробуйте позже.')}")
    except requests.RequestException as e:
        logging.error(f"Ошибка при отправке данных в Django API: {e}")
        await message.answer("❌ Не удалось связаться с сервером. Попробуйте позже.")
