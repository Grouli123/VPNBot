from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import os
from outline_vpn.outline_vpn import OutlineVPN
from aiogram import Bot
import threading
import asyncio

# Настройки VPN API
SERVER_HOST = "147.45.224.62"
SERVER_PORT = "65146"  
API_SECRET = "Kek-PEeOq-iXLyjmmuOtRQ"
CERT_SHA256 = "6c4d53ceb6fc4ba7c35c06cc6467f278b0234352626bb2fad23f3fe0b143a7cf"

API_URL = f"https://{SERVER_HOST}:{SERVER_PORT}/{API_SECRET}"
vpn_client = OutlineVPN(api_url=API_URL, cert_sha256=CERT_SHA256)

TOKEN = "7741477291:AAEnUfLEzqtDBx4ve0F-G2fgGPOdyBowLKQ"
bot = Bot(token=TOKEN)

app = Flask(__name__)
app.secret_key = 'supersecretkey'

event_loop = asyncio.new_event_loop()
threading.Thread(target=event_loop.run_forever, daemon=True).start()

# Функция для подключения к базе данных
def connect_db():
    db_name = "vpn_users.sql"
    if not os.path.exists(db_name):
        raise FileNotFoundError(f"Database {db_name} does not exist.")
    return sqlite3.connect(db_name, check_same_thread=False)

# Главная страница
@app.route('/')
def index():
    session.pop('logged_in', None)
    return render_template('login.html')

# Обработка входа
@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')

    if username == 'admin' and password == 'admin123':
        session['logged_in'] = True
        return redirect(url_for('dashboard'))
    else:
        return render_template('login.html', error="Неверный логин или пароль")

# Панель управления
@app.route('/dashboard')
def dashboard():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('index'))
    return render_template('dashboard.html')

# API для получения данных из БД
@app.route('/api/data', methods=['GET'])
def get_data():
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        conn = connect_db()
        cursor = conn.cursor()

        # Проверяем, есть ли данные в БД
        cursor.execute("SELECT id, user_id, key_id, key, subscription_end, подписка FROM users")
        records = cursor.fetchall()

        if not records:
            print("⚠ База данных пуста или нет пользователей!")
            return jsonify({"error": "No users found"}), 404

        # Преобразуем данные в JSON
        data = []
        for row in records:
            record_id, user_id, key_id, key, subscription_end, подписка = row
            data.append({
                "id": record_id,
                "user_id": user_id,
                "key_id": key_id,
                "key": key,
                "subscription_end": subscription_end,
                "подписка": подписка,
                "is_active": bool(подписка)  # Ползунок справа (True) или слева (False)
            })

        conn.close()  # Закрываем соединение перед возвратом данных
        print(f"✅ Найдено {len(data)} пользователей в БД")  # Лог для проверки

        return jsonify({"records": data})  # Возвращаем правильные данные
    except Exception as e:
        print(f"❌ Ошибка при получении данных из БД: {e}")
        return jsonify({"error": str(e)}), 500


# Функция для извлечения key_id из VPN-ключа
def extract_key_id(vpn_key):
    if vpn_key:
        print(f"🔑 Найден key_id: {vpn_key}")
        return vpn_key  # Теперь в БД уже хранится key_id
    print("❌ Ошибка: key_id отсутствует в БД")
    return None


# API для управления подписками
@app.route('/api/subscription', methods=['POST'])
def update_subscription():
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        user_id = request.args.get('user_id')
        action = request.args.get('action')

        if not user_id or not action:
            return jsonify({"error": "Missing 'user_id' or 'action' parameter"}), 400

        new_status = 1 if action == 'activate' else 0
        new_subscription_end = 30 if new_status == 1 else 0

        conn = connect_db()
        cursor = conn.cursor()

        # Обновляем статус подписки в базе данных
        cursor.execute("UPDATE users SET подписка = ?, subscription_end = ? WHERE id = ?", (new_status, new_subscription_end, user_id))

        # Получаем ключ VPN пользователя
        cursor.execute("SELECT key_id, user_id FROM users WHERE id = ?", (user_id,))
        key_data = cursor.fetchone()
        conn.commit()
        conn.close()

        if key_data and key_data[0]:
            key_id = key_data[0]  # Извлекаем `key_id`
            telegram_user_id = key_data[1]  # ID пользователя в Telegram
            if key_id:
                print(f"🔑 Найден ключ для user_id {user_id}: {key_id}")

                # Если подписка активирована (1) → устанавливаем условный "безлимит"
                if new_status == 1:
                    max_limit = 10**15
                    vpn_client.add_data_limit(key_id, max_limit)
                    print(f"✅ Условный безлимит установлен для user_id {user_id}")

                    # Отправляем сообщение пользователю
                    send_message_sync(telegram_user_id, "✅ Ваша подписка активирована на 30 дней!")
                else:
                    vpn_client.add_data_limit(key_id, 100 * 1024 * 1024)
                    print(f"⛔ Лимит 100 МБ установлен для user_id {user_id}")

                    # Отправляем сообщение пользователю
                    send_message_sync(telegram_user_id, "❌ Ваша подписка закончилась.")
            else:
                print(f"⚠ Ошибка: Не удалось извлечь key_id для user_id {user_id}")
                return jsonify({"error": "Failed to extract key_id"}), 500
        else:
            print(f"⚠ Ошибка: Ключ не найден в БД для user_id {user_id}")
            return jsonify({"error": "No VPN key found"}), 404

        return jsonify({"success": True, "new_status": new_status})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Функция для отправки сообщений через Telegram Bot
async def send_message(chat_id, text):
    try:
        await bot.send_message(chat_id, text)
        print(f"📤 Уведомление отправлено пользователю {chat_id}")
    except Exception as e:
        print(f"❌ Ошибка при отправке уведомления пользователю {chat_id}: {e}")

# Функция для безопасного вызова асинхронного метода отправки сообщения
def send_message_sync(chat_id, text):
    future = asyncio.run_coroutine_threadsafe(send_message(chat_id, text), event_loop)
    try:
        future.result()  # Ждем завершения отправки сообщения
    except Exception as e:
        print(f"Ошибка при отправке сообщения: {e}")

# Функция для отправки сообщений через Telegram Bot
async def send_message(chat_id, text):
    try:
        await bot.send_message(chat_id, text)
        print(f"📤 Уведомление отправлено пользователю {chat_id}")
    except Exception as e:
        print(f"❌ Ошибка при отправке уведомления пользователю {chat_id}: {e}")

@app.route('/api/broadcast', methods=['POST'])
def broadcast_message():
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        data = request.get_json()
        message = data.get('message')

        if not message:
            return jsonify({"error": "Message is empty"}), 400

        conn = connect_db()
        cursor = conn.cursor()

        # Получаем все user_id из базы данных
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()
        conn.close()

        if not users:
            return jsonify({"error": "No users found in the database"}), 404

        # Отправляем сообщение каждому пользователю
        for (user_id,) in users:
            send_message_sync(user_id, message)

        print(f"✅ Сообщение отправлено {len(users)} пользователям.")
        return jsonify({"success": True, "sent_to": len(users)})
    except Exception as e:
        print(f"❌ Ошибка при отправке сообщения: {e}")
        return jsonify({"error": str(e)}), 500

# Выход из системы
@app.route('/logout', methods=['POST'])
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
