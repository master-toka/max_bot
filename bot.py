import asyncio
import logging
import sqlite3
import datetime
from typing import Optional

from maxapi import Bot, Dispatcher
from maxapi.types import BotStarted, MessageCreated, Command
from maxapi.keyboard import InlineKeyboardMarkup, InlineKeyboardButton

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Конфигурация
BOT_TOKEN = "f9LHodD0cOKqO72B63ZwBm7ZGWNy6t4ecg5gZjzenII-X_aXDT9MfUTgeNRt-THuq-ciU7Z5OVxFKTV2Yftt"  # Замените на ваш токен
ADMIN_ID = 6271996  # Замените на ваш MAX ID

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ---------- Работа с базой данных ----------
def init_db():
    """Инициализация базы данных SQLite"""
    conn = sqlite3.connect('applications.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            full_name TEXT,
            message TEXT,
            status TEXT DEFAULT 'new',
            created_at TIMESTAMP,
            response TEXT,
            responded_at TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def add_application(user_id: int, username: str, full_name: str, message_text: str) -> int:
    """Добавление новой заявки в БД"""
    conn = sqlite3.connect('applications.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO applications (user_id, username, full_name, message, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, username, full_name, message_text, 'new', datetime.datetime.now()))
    conn.commit()
    app_id = cursor.lastrowid
    conn.close()
    return app_id

def update_application_status(app_id: int, status: str, response_text: Optional[str] = None):
    """Обновление статуса заявки"""
    conn = sqlite3.connect('applications.db')
    cursor = conn.cursor()
    if response_text:
        cursor.execute('''
            UPDATE applications 
            SET status = ?, response = ?, responded_at = ? 
            WHERE id = ?
        ''', (status, response_text, datetime.datetime.now(), app_id))
    else:
        cursor.execute('''
            UPDATE applications 
            SET status = ? 
            WHERE id = ?
        ''', (status, app_id))
    conn.commit()
    conn.close()

def get_user_applications(user_id: int):
    """Получение последних заявок пользователя"""
    conn = sqlite3.connect('applications.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, status, created_at, response 
        FROM applications 
        WHERE user_id = ? 
        ORDER BY created_at DESC 
        LIMIT 5
    ''', (user_id,))
    apps = cursor.fetchall()
    conn.close()
    return apps

def get_new_applications():
    """Получение всех новых заявок (для админа)"""
    conn = sqlite3.connect('applications.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, user_id, username, full_name, message, created_at 
        FROM applications 
        WHERE status = 'new'
        ORDER BY created_at DESC
    ''')
    apps = cursor.fetchall()
    conn.close()
    return apps

# ---------- Обработчики событий ----------
@dp.bot_started()
async def on_bot_started(event: BotStarted):
    """
    Приветствие новых пользователей при нажатии кнопки "Начать"
    """
    welcome_text = (
        "👋 Добро пожаловать в сервис приема заявок!\n\n"
        "Я помогу вам оставить заявку, и наш менеджер свяжется с вами.\n\n"
        "Доступные команды:\n"
        "/start - Главное меню\n"
        "/new - Оставить новую заявку\n"
        "/status - Проверить статус заявки\n"
        "/help - Получить помощь"
    )
    
    # Создаем клавиатуру с командами
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Новая заявка", callback_data="new_application")],
        [InlineKeyboardButton(text="📊 Статус заявок", callback_data="check_status")],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="help")]
    ])
    
    await bot.send_message(
        chat_id=event.chat_id,
        text=welcome_text,
        reply_markup=keyboard
    )

@dp.message_created(Command('start'))
async def cmd_start(event: MessageCreated):
    """
    Обработчик команды /start
    """
    await on_bot_started(BotStarted(chat_id=event.message.sender.id))

@dp.message_created(Command('help'))
async def cmd_help(event: MessageCreated):
    """
    Обработчик команды /help
    """
    help_text = (
        "🆘 Помощь по использованию бота\n\n"
        "Как оставить заявку:\n"
        "1. Нажмите кнопку '📝 Новая заявка'\n"
        "2. Отправьте текст вашей заявки\n"
        "3. Дождитесь ответа от администратора\n\n"
        "Как проверить статус:\n"
        "• Нажмите кнопку '📊 Статус заявок'\n"
        "• Вы увидите последние 5 заявок\n\n"
        "Если у вас возникли проблемы, напишите администратору"
    )
    await event.message.answer(help_text)

@dp.message_created(Command('new'))
async def cmd_new(event: MessageCreated):
    """
    Обработчик команды /new - начало создания заявки
    """
    await event.message.answer(
        "📋 Опишите вашу заявку подробно.\n"
        "Напишите сообщение, и мы обработаем его в ближайшее время."
    )
    # Сохраняем состояние пользователя (ожидание текста заявки)
    # В простой реализации можно использовать FSM, но здесь используем костыль
    event.message.state = "awaiting_application"

@dp.message_created()
async def process_application(event: MessageCreated):
    """
    Обработка текста заявки от пользователя
    """
    # Проверяем, ожидаем ли мы заявку от этого пользователя
    # В реальном проекте используйте FSM из maxapi.fsm
    if not hasattr(event.message, 'state') or event.message.state != "awaiting_application":
        # Если не ожидаем заявку, предлагаем меню
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Новая заявка", callback_data="new_application")],
        ])
        await event.message.answer(
            "Используйте кнопку 'Новая заявка' для создания обращения.",
            reply_markup=keyboard
        )
        return
    
    # Получаем данные пользователя
    user = event.message.sender
    user_id = user.id
    username = user.username or "Нет username"
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    app_text = event.message.body.text
    
    # Сохраняем заявку
    app_id = add_application(user_id, username, full_name, app_text)
    
    # Автоответ пользователю
    auto_response = (
        f"✅ Заявка №{app_id} успешно принята!\n\n"
        f"Ваше сообщение: {app_text}\n\n"
        "⏳ Ожидайте ответа от администратора. Мы свяжемся с вами в ближайшее время."
    )
    await event.message.answer(auto_response)
    
    # Сбрасываем состояние
    event.message.state = None
    
    # Уведомление администратору
    admin_message = (
        f"🔔 НОВАЯ ЗАЯВКА №{app_id}\n\n"
        f"От: {full_name}\n"
        f"Username: @{username}\n"
        f"ID: {user_id}\n"
        f"Время: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"Текст заявки:\n{app_text}\n\n"
        f"Для ответа используйте команду:\n"
        f"/reply {app_id} [текст ответа]"
    )
    
    # Создаем клавиатуру для быстрого ответа
    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"✏️ Ответить на заявку №{app_id}", 
            callback_data=f"reply_{app_id}"
        )],
        [InlineKeyboardButton(text="📋 Все новые заявки", callback_data="admin_new_apps")]
    ])
    
    await bot.send_message(
        chat_id=ADMIN_ID,
        text=admin_message,
        reply_markup=admin_keyboard
    )

@dp.message_created(Command('status'))
async def cmd_status(event: MessageCreated):
    """
    Проверка статуса заявок
    """
    applications = get_user_applications(event.message.sender.id)
    
    if not applications:
        await event.message.answer("У вас еще нет заявок.")
        return
    
    response_text = "📊 Ваши последние заявки:\n\n"
    for app in applications:
        app_id, status, created_at, response = app
        status_emoji = {
            'new': '🟡',
            'in_progress': '🔵',
            'completed': '🟢',
            'rejected': '🔴'
        }.get(status, '⚪')
        
        created_date = datetime.datetime.fromisoformat(created_at).strftime('%d.%m.%Y %H:%M')
        response_info = f"\nОтвет: {response}" if response else ""
        
        response_text += (
            f"{status_emoji} Заявка №{app_id} от {created_date}\n"
            f"Статус: {status}\n"
            f"{response_info}\n\n"
        )
    
    await event.message.answer(response_text)

# ---------- Админ-команды ----------
@dp.message_created(Command('reply'))
async def admin_reply(event: MessageCreated):
    """
    Ответ на заявку (только для админа)
    """
    if event.message.sender.id != ADMIN_ID:
        await event.message.answer("У вас нет прав для этой команды.")
        return
    
    try:
        # Парсим команду: /reply 123 Текст ответа
        parts = event.message.body.text.split(maxsplit=2)
        if len(parts) < 3:
            await event.message.answer("Использование: /reply [номер_заявки] [текст ответа]")
            return
        
        app_id = int(parts[1])
        reply_text = parts[2]
        
        # Получаем информацию о заявке из БД
        conn = sqlite3.connect('applications.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, message FROM applications WHERE id = ?', (app_id,))
        app_info = cursor.fetchone()
        conn.close()
        
        if not app_info:
            await event.message.answer(f"Заявка №{app_id} не найдена.")
            return
        
        user_id, original_message = app_info
        
        # Обновляем статус
        update_application_status(app_id, 'completed', reply_text)
        
        # Отправляем ответ пользователю
        user_response = (
            f"📬 Ответ на заявку №{app_id}\n\n"
            f"Ваша заявка: {original_message}\n\n"
            f"Ответ администратора:\n{reply_text}\n\n"
            "Спасибо за обращение!"
        )
        
        await bot.send_message(chat_id=user_id, text=user_response)
        await event.message.answer(f"✅ Ответ на заявку №{app_id} отправлен пользователю")
        
    except ValueError:
        await event.message.answer("Неверный формат номера заявки.")
    except Exception as e:
        await event.message.answer(f"Ошибка: {str(e)}")

@dp.message_created(Command('new_apps'))
async def admin_new_apps(event: MessageCreated):
    """
    Просмотр всех новых заявок (админ)
    """
    if event.message.sender.id != ADMIN_ID:
        await event.message.answer("У вас нет прав для этой команды.")
        return
    
    new_apps = get_new_applications()
    
    if not new_apps:
        await event.message.answer("Новых заявок нет.")
        return
    
    response = "🔴 НОВЫЕ ЗАЯВКИ:\n\n"
    for app in new_apps:
        app_id, user_id, username, full_name, msg, created_at = app
        created_date = datetime.datetime.fromisoformat(created_at).strftime('%d.%m.%Y %H:%M')
        response += (
            f"№{app_id} от {created_date}\n"
            f"От: {full_name} (@{username})\n"
            f"Текст: {msg[:50]}{'...' if len(msg) > 50 else ''}\n"
            f"Ответ: /reply {app_id} [текст]\n\n"
        )
    
    # Отправляем частями, если сообщение слишком длинное
    if len(response) > 4000:
        for i in range(0, len(response), 4000):
            await event.message.answer(response[i:i+4000])
    else:
        await event.message.answer(response)

# ---------- Обработка callback-кнопок ----------
@dp.callback()
async def handle_callbacks(cb):
    """
    Обработка нажатий на инлайн-кнопки
    """
    if cb.payload == "new_application":
        await bot.send_message(
            chat_id=cb.user.id,
            text="📋 Опишите вашу заявку подробно. Напишите сообщение, и мы обработаем его."
        )
        # Здесь нужно установить состояние через FSM
        # Для простоты предлагаем пользователю использовать команду /new
        
    elif cb.payload == "check_status":
        applications = get_user_applications(cb.user.id)
        if not applications:
            await bot.send_message(chat_id=cb.user.id, text="У вас еще нет заявок.")
            return
        
        response_text = "📊 Ваши заявки:\n\n"
        for app in applications[:3]:  # Показываем только 3 последних
            app_id, status, created_at, response = app
            status_emoji = {'new': '🟡', 'in_progress': '🔵', 'completed': '🟢', 'rejected': '🔴'}.get(status, '⚪')
            created_date = datetime.datetime.fromisoformat(created_at).strftime('%d.%m.%Y')
            response_text += f"{status_emoji} №{app_id} от {created_date}: {status}\n"
        
        await bot.send_message(chat_id=cb.user.id, text=response_text)
        
    elif cb.payload == "help":
        await bot.send_message(
            chat_id=cb.user.id,
            text="🆘 Используйте /help для получения подробной справки."
        )
        
    elif cb.payload == "admin_new_apps":
        if cb.user.id != ADMIN_ID:
            await cb.answer("У вас нет прав", notification=True)
            return
        
        new_apps = get_new_applications()
        if not new_apps:
            await bot.send_message(chat_id=cb.user.id, text="Новых заявок нет.")
            return
        
        response = "🔴 Новые заявки:\n"
        for app in new_apps[:5]:
            app_id, _, username, _, msg, created_at = app
            created_date = datetime.datetime.fromisoformat(created_at).strftime('%d.%m.%Y %H:%M')
            response += f"\n№{app_id} от {created_date}\n@{username}: {msg[:30]}..."
        
        await bot.send_message(chat_id=cb.user.id, text=response)
    
    elif cb.payload.startswith("reply_"):
        if cb.user.id != ADMIN_ID:
            await cb.answer("У вас нет прав", notification=True)
            return
        
        app_id = cb.payload.replace("reply_", "")
        await bot.send_message(
            chat_id=cb.user.id,
            text=f"Введите ответ на заявку №{app_id} в формате:\n/reply {app_id} [текст ответа]"
        )
    
    await cb.answer()  # Обязательно отвечаем на callback

# ---------- Запуск бота ----------
async def main():
    """Главная функция запуска"""
    print("🚀 Бот запускается...")
    init_db()
    print("✅ База данных инициализирована")
    
    # Устанавливаем команды бота
    await bot.set_my_commands([
        {"name": "start", "description": "Запустить бота"},
        {"name": "new", "description": "Оставить новую заявку"},
        {"name": "status", "description": "Проверить статус заявок"},
        {"name": "help", "description": "Получить помощь"},
        {"name": "new_apps", "description": "[Админ] Все новые заявки"},
    ])
    
    # Запускаем поллинг
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
