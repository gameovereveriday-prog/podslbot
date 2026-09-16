import telebot
import os
import re
from telebot import types

# ===== НАСТРОЙКИ =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 957705940        # ← ваш ID
CHANNEL_ID = -1004300683892 # ← ID канала

if not BOT_TOKEN:
    print("❌ ОШИБКА: Переменная BOT_TOKEN не найдена!")
    exit(1)

bot = telebot.TeleBot(BOT_TOKEN)
last_message = {}

# ===== СПИСОК ЗАПРЕЩЁННЫХ СЛОВ =====
# Пишите в нижнем регистре. Бот ищет вхождения по частям слова.
BAD_WORDS = [
    # мат (примеры, дополните своими)
    "хуй", "хуя", "хую", "хуе", "хуи",
    "пизд", "бля", "блят", "бляд",
    "ебал", "ебал", "ебат", "ебан", "ебуч", "ёб",
    "сука", "суки", "сучк",
    "мудак", "мудил", "мраз",
    "гандон", "гондон",
    "долбоеб", "долбоёб",
    "пидор", "пидар", "пидр",
    "шлюх", "проститут",
    "нах", "нахуй", "нахуя",
    # оскорбления / травля — добавьте свои
    "дебил", "дурак", "идиот", "кретин",
    # реклама / спам — можно добавить
    "подписывайтесь", "казино", "ставки", "заработок",
]

def contains_bad_words(text: str) -> list:
    """Возвращает список найденных запрещённых слов."""
    if not text:
        return []
    text_lower = text.lower()
    # Убираем лишние символы, чтобы не обходили через "х*й", "х.у.й" и т.п.
    cleaned = re.sub(r'[^\w\s]', '', text_lower)
    cleaned = re.sub(r'\s+', '', cleaned)  # убираем пробелы: "х у й" → "хуй"
    
    found = []
    for word in BAD_WORDS:
        if word in cleaned:
            found.append(word)
    return found

# ===== ПРИВЕТСТВИЕ =====
@bot.message_handler(commands=['start'])
def send_welcome(message):
    if message.chat.type != 'private':
        return
    bot.reply_to(
        message,
        "Привет! Это анонимный чат-бот подслушано ФМиИТ.\n"
        "Что вы хотите сообщить ФМиИТовцам?"
    )

# ===== ОБРАБОТКА СООБЩЕНИЙ ОТ ПОЛЬЗОВАТЕЛЕЙ =====
@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.from_user.id != ADMIN_ID)
def handle_anonymous_message(message):
    user = message.from_user
    
    # Собираем текст для проверки (обычный текст + подпись к медиа)
    text_to_check = message.text or message.caption or ""
    bad_found = contains_bad_words(text_to_check)
    
    # Формируем шапку для вас
    status = "⚠️ СОДЕРЖИТ ЗАПРЕЩЁННЫЕ СЛОВА" if bad_found else "✅ ЧИСТО (опубликовано в канал)"
    sender_info = (
        f"{status}\n"
        f"👤 От: {user.first_name} {user.last_name or ''}\n"
        f"🔗 Username: @{user.username or 'нет'}\n"
        f"🆔 ID: {user.id}\n"
    )
    if bad_found:
        sender_info += f"🚫 Найдено: {', '.join(bad_found)}\n"
    sender_info += "➖➖➖➖➖➖➖➖➖➖"
    
    try:
        # 1. Отправляем шапку вам
        bot.send_message(ADMIN_ID, sender_info)
        
        # 2. Копируем сообщение вам (для контроля/ручной модерации)
        bot.copy_message(
            chat_id=ADMIN_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )
        
        # 3. Сохраняем для возможного /publish
        last_message[ADMIN_ID] = message
        
        # 4. Если чисто — публикуем в канал автоматически
        if not bad_found:
            try:
                bot.copy_message(
                    chat_id=CHANNEL_ID,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id
                )
                bot.reply_to(message, "✅ Ваше сообщение опубликовано анонимно!")
            except Exception as e:
                bot.reply_to(message, "✅ Сообщение принято, скоро появится в канале.")
                bot.send_message(ADMIN_ID, f"❌ Ошибка автопубликации: {e}")
        else:
            # Содержит мат — только вам, ждёт ручного решения
            bot.reply_to(
                message,
                "✅ Ваше сообщение отправлено на проверку администратору."
            )
        
    except Exception as e:
        bot.reply_to(message, "❌ Ошибка при отправке. Попробуйте позже.")
        print(f"Ошибка: {e}")

# ===== КОМАНДА ДЛЯ АДМИНА: РУЧНАЯ ПУБЛИКАЦИЯ =====
@bot.message_handler(commands=['publish'])
def publish_to_channel(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    if ADMIN_ID in last_message:
        original = last_message[ADMIN_ID]
        try:
            bot.copy_message(
                chat_id=CHANNEL_ID,
                from_chat_id=original.chat.id,
                message_id=original.message_id
            )
            bot.reply_to(message, "✅ Успешно опубликовано в канал!")
            del last_message[ADMIN_ID]
        except Exception as e:
            bot.reply_to(message, f"❌ Ошибка публикации: {e}")
    else:
        bot.reply_to(message, "Нет сообщений для публикации.")

# ===== ЗАПУСК =====
if __name__ == '__main__':
    print("Бот запущен...")
    bot.infinity_polling()
