import asyncio
import sqlite3
import datetime
from aiogram import Bot, Dispatcher
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.types import CallbackQuery, FSInputFile
from outline_vpn.outline_vpn import OutlineVPN
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ContentType 

# Настройки VPN
TOKEN = "7741477291:AAEnUfLEzqtDBx4ve0F-G2fgGPOdyBowLKQ"
SERVER_HOST = "147.45.224.62"
SERVER_PORT = "65146"  
API_SECRET = "Kek-PEeOq-iXLyjmmuOtRQ"
CERT_SHA256 = "6c4d53ceb6fc4ba7c35c06cc6467f278b0234352626bb2fad23f3fe0b143a7cf"

API_URL = f"https://{SERVER_HOST}:{SERVER_PORT}/{API_SECRET}"
vpn_client = OutlineVPN(api_url=API_URL, cert_sha256=CERT_SHA256)

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()  # Создаем Router для регистрации обработчиков

ADMIN_ID = 845482806  # ID администратора Telegram
dp.include_router(router)

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect("vpn_users.sql")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER UNIQUE,
                        key_id TEXT,
                        key TEXT,
                        subscription_end INTEGER,
                        подписка BOOLEAN DEFAULT 0)''')
    conn.commit()
    conn.close()

# Подключение к БД
def connect_db():
    return sqlite3.connect("vpn_users.sql", check_same_thread=False)

# Функция для генерации VPN-ключа
async def generate_vpn_key(subscription: bool):
    try:
        new_key = vpn_client.create_key()
        key_id = new_key.key_id
        
        # Устанавливаем лимит 100 МБ, если подписка неактивна
        vpn_client.add_data_limit(key_id, 100 * 1024 * 1024)  

        return new_key.access_url, key_id
    except Exception as e:
        print(f"Ошибка при создании ключа: {e}")
        return None, None

# Команда "поддержка"
@dp.message(Command("support"))
async def support_command(message: Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Связаться с поддержкой",
                    url="https://t.me/MrGrouli"
                )
            ]
        ]
    )
    await message.answer(
        "📞 Если у вас возникли вопросы или проблемы, свяжитесь с нашей поддержкой по кнопке ниже:",
        reply_markup=keyboard
    )

# Команда старт
@dp.message(Command("start"))
async def start_command(message: Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Получить VPN-ключ", callback_data="get_vpn_key")]
        ]
    )
    await message.answer("👋 Привет!\n\n🗝 Нажмите на кнопку ниже, чтобы получить VPN-ключ", reply_markup=keyboard)

@dp.callback_query(lambda c: c.data == "get_vpn_key")
async def send_vpn_key(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id

    # Убираем кнопки из сообщения
    await callback_query.message.edit_reply_markup(reply_markup=None)

    # Подключение к базе
    conn = sqlite3.connect("vpn_users.sql")
    cursor = conn.cursor()

    # Проверяем, есть ли у пользователя уже ключ
    cursor.execute("SELECT key_id FROM users WHERE user_id = ?", (user_id,))
    existing_key = cursor.fetchone()

    if existing_key:
        await callback_query.message.answer("ℹ️Вы уже получили ключ. Обратитесь в поддержку.")
        conn.close()
        return  # ⬅ Прерываем выполнение

    # Генерация нового ключа
    new_key, key_id = await generate_vpn_key(subscription=False)  # Лимит 100 МБ

    if new_key and key_id:
        print(f"🆕 Выдан новый VPN-ключ. Сохранен key_id: {key_id}")

        # ⬇ ВАЖНО: Сохраняем `key_id`, а не `new_key`
        cursor.execute("INSERT INTO users (user_id, key_id, key, subscription_end, подписка) VALUES (?, ?, ?, ?, ?)",
                       (user_id, key_id, new_key, 30, False))
        conn.commit()
        conn.close()

        await callback_query.message.answer("ℹ️ Подключитесь через приложение Outline VPN.\n\n1. Скачать приложение Outline:\nСсылка для iOS: https://apps.apple.com/kz/app/outline-app/id1356177741\nСсылка для Android: https://play.google.com/store/apps/details?id=org.outline.android.client\n\n2. Скопировать ключ\n\n3. Открыть приложение Outline и вставить ключ")
        await callback_query.message.answer(f"🗝 Ваш VPN-ключ с лимитом 100мб:")
        await callback_query.message.answer(f"{new_key}")
        await callback_query.message.answer(f"ℹ️ Ваш тестовый ключ действует для все устройства")

        # Отправка видео
        video_path = "./Videos/iOS_automation.MP4"
        video = FSInputFile(video_path)
        await bot.send_document(
            chat_id=callback_query.from_user.id,
            document=video,
            caption="📌 Инструкция по настройке VPN на iOS для автоматического включения и выключения VPN для определенных приложений, без необходимости включать или выключать его вручную."
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Хочу безлимит", callback_data="set_vpn_key_free")]
            ]
        )
        await bot.send_message(
            user_id,
            "💳 Оплатите подписку для подключения безлимита VPN на все устройства.\n\n💰 Стоимость подписки: 199 рублей",
            reply_markup=keyboard
        )
    else:
        await callback_query.message.answer("❌ Ошибка при создании ключа. Попробуйте позже.")
        conn.close()

# Обработчик нажатия кнопки "Оплачено"
@dp.callback_query(lambda c: c.data == "get_vpn_key")
async def got_vpn_key(callback_query: CallbackQuery):
    # Убираем кнопки, редактируя сообщение
    await callback_query.message.edit_text(
        "✅ Вы получили VPN-ключ.",
    )  

@dp.callback_query(lambda c: c.data == "set_vpn_key_free")
async def request_payment(callback_query: CallbackQuery):
    # Убираем кнопки из сообщения
    await callback_query.message.edit_reply_markup(reply_markup=None)

    await callback_query.message.answer(
        # "💳 Оплатите подписку для подключения безлимита VPN на все устройства.\n\n💰 Стоимость подписки: 199 рублей\n\n"
        '‼️ Подписка оплачивается переводом на карту 2200 7013 3196 3378\n\n📌 После оплаты нажмите кнопку "Оплачено" и отправьте скриншот платежа или чека.\n\n👤 Администратор проверяет скриншот платежа\n\n✅ Вы получаете сообщение, что получили безлимитный доступ к VPN на 30 дней.',
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Оплачено", callback_data="payment_done")]
            # [InlineKeyboardButton(text="Отменить", callback_data="cancel_message")]
        ]
    )

    await bot.send_message(
        chat_id=callback_query.from_user.id,
        text='📌 Как только оплатите подписку, нажмите "Оплачено" и отправьте скриншот платежа или чека.',
        reply_markup=keyboard
    )

# Обработчик нажатия кнопки "Оплачено"
@dp.callback_query(lambda c: c.data == "payment_done")
async def payment_done(callback_query: CallbackQuery):
    # Убираем кнопки, редактируя сообщение
    await callback_query.message.answer("📷 Пришлите скриншот платежа или чека.")

# Обработчик получения фото для подтверждения оплаты
@router.message(lambda message: message.content_type == ContentType.PHOTO)
async def confirm_payment(message: Message):
    user_id = message.from_user.id

    # Получаем key_id пользователя из БД
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT key_id FROM users WHERE user_id = ?", (user_id,))
    key_data = cursor.fetchone()
    conn.close()

    key_id = key_data[0] if key_data else "Не найден"
    print(f"Отправка сообщения админу {ADMIN_ID}: Пользователь {user_id} оплатил подписку. Ключ: {key_id}")
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Оплата не прошла",
                    callback_data=f"payment_failed:{user_id}"
                )
            ]
        ]
    )

    # Отправляем сообщение админу с user_id и key_id
    await bot.send_message(
        ADMIN_ID,
        f"📩 Пользователь {user_id} оплатил подписку.\n🔑 Ключ пользователя: {key_id}.",
        reply_markup=keyboard
    )

    # Пересылаем фото админу
    await bot.send_photo(
        ADMIN_ID, message.photo[-1].file_id
    )

    await message.answer("✅ Ваше подтверждение отправлено администратору. Ожидайте проверки.")

@router.callback_query(lambda c: c.data.startswith("payment_failed"))
async def payment_failed(callback_query: CallbackQuery):
    # Получаем user_id из callback_data
    user_id = int(callback_query.data.split(":")[1])

    # Отправляем сообщение пользователю
    await bot.send_message(
        user_id,
        "❌ Не верный скриншот!\n\nЕсли вы произвели оплату, пришлите правильный скриншот. "
        "Если нет, то оплатите и пришлите скриншот перевода или чека."
    )

    # Подтверждаем нажатие кнопки администратору
    await callback_query.answer("Сообщение отправлено пользователю.")

# Функция для обновления подписок
async def update_subscriptions():
    while True:
        conn = sqlite3.connect("vpn_users.sql")
        cursor = conn.cursor()

        # Получаем пользователей
        cursor.execute("SELECT user_id, key_id, key, subscription_end, подписка FROM users")
        users = cursor.fetchall()

        for user_id, key_id, key, days_left, подписка in users:
            if days_left > 0:
                days_left -= 1
                cursor.execute("UPDATE users SET subscription_end = ? WHERE user_id = ?", (days_left, user_id))
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="Оплачено", callback_data="payment_done")]
                    ]
                )
                # Оповещения
                if days_left in [3, 2, 1]:
                    await bot.send_message(user_id, f'❗️ Через {days_left} дня(ей) ваша подписка на VPN закончится.\n\n😎 Продлите подписку\n\n‼️ Подписка оплачивается переводом на карту 2200 7013 3196 3378\n\n📌 После оплаты нажмите кнопку "Оплачено" и отправьте скриншот платежа или чека.\n\n👤 Администратор проверяет скриншот платежа\n\n✅ Вы получаете сообщение, что получили безлимитный доступ к VPN на 30 дней.', reply_markup=keyboard)
            
            # Окончание подписки
            if days_left <= 0 and подписка:
                cursor.execute("UPDATE users SET подписка = 0 WHERE user_id = ?", (user_id,))
                
                # Ставим лимит 100 МБ, но используем `key_id`, а не `key`
                vpn_client.add_data_limit(key_id, 0)


                await bot.send_message(user_id, "📉 Ваша подписка истекла. Лимит VPN теперь 0 МБ.\n\n😎 Продлите подписку")

        conn.commit()
        conn.close()
        
        # Запускаем обновление раз в день
        await asyncio.sleep(86400)

# Основная функция
async def main():
    init_db()
    asyncio.create_task(update_subscriptions())  # Запуск проверки подписок
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())