import telebot
import os
import re
from telebot import types

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 957705940        # ← ваш ID
CHANNEL_ID = -1004300683892 # ← ID канала

if not BOT_TOKEN:
    print("❌ ОШИБКА: Переменная BOT_TOKEN не найдена!")
    exit(1)

bot = telebot.TeleBot(BOT_TOKEN)

# ===== СПИСОК ЗАПРЕЩЁННЫХ СЛОВ =====
BAD_WORDS = [
    "хуй", "хуя", "хую", "хуе", "хуи",
    "пизд", "бля", "блят", "бляд",
    "ебал", "ебат", "ебан", "ебуч", "ёб",
    "сука", "суки", "сучк",
    "мудак", "мудил", "мраз",
    "гандон", "гондон",
    "долбоеб", "долбоёб",
    "пидор", "пидар", "пидр",
    "шлюх", "проститут",
    "нах", "нахуй", "нахуя",
    "дебил", "дурак", "идиот", "кретин",
    "подписывайтесь", "казино", "ставки", "заработок",
]

def contains_bad_words(text: str) -> list:
    if not text:
        return []
    text_lower = text.lower()
    cleaned = re.sub(r'[^\w\s]', '', text_lower)
    cleaned = re.sub(r'\s+', '', cleaned)
    found = []
    for word in BAD_WORDS:
        if word in cleaned:
            found.append(word)
    return found

# ===== ХРАНИЛИЩЕ СООБЩЕНИЙ, ОЖИДАЮЩИХ МОДЕРАЦИИ =====
# Ключ — message_id сообщения, которое вы получили в личке.
# Значение — message_id оригинала (чтобы можно было copy_message).
pending = {}

# ===== ПРИВЕТСТВИЕ =====
@bot.message_handler(commands=['start'])
def send_welcome(message):
    if message.chat.type != 'private':
        return
    bot.reply_to(
        message,
        "Привет! Это анонимный чат-бот подслушано ФМиИТ.\n"
        "Что вы хотите сообщить ФМиИТовцам?\n\n"
        "📝 Текстовые сообщения публикуются сразу.\n"
        "📷 Фото и видео — после проверки администратором."
    )

# ===== ОБРАБОТКА СООБЩЕНИЙ ОТ ПОЛЬЗОВАТЕЛЕЙ =====
@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.from_user.id != ADMIN_ID)
def handle_anonymous_message(message):
    user = message.from_user
    text_to_check = message.text or message.caption or ""
    bad_found = contains_bad_words(text_to_check)
    is_media = message.content_type in ('photo', 'video', 'document', 'voice', 'audio', 'video_note', 'animation')

    # === ШАПКА ДЛЯ АДМИНА ===
    sender_info = (
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

        # 2. Копируем само сообщение вам и получаем message_id копии
        copied = bot.copy_message(
            chat_id=ADMIN_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )

        # ===== ЛОГИКА: ТЕКСТ vs МЕДИА =====
        if is_media:
            # --- ФОТО/ВИДЕО: ждём вашего решения через кнопки ---
            pending[copied.message_id] = message.message_id

            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("✅ Опубликовать", callback_data=f"pub_{copied.message_id}"),
                types.InlineKeyboardButton("❌ Отклонить", callback_data=f"rej_{copied.message_id}")
            )
            bot.send_message(
                ADMIN_ID,
                "📷 Медиа на модерации. Что делаем?",
                reply_markup=markup
            )
            bot.reply_to(
                message,
                "✅ Ваше медиа отправлено на проверку администратору."
            )

        else:
            # --- ТЕКСТ: как и раньше, авто с фильтром ---
            if not bad_found:
                bot.copy_message(
                    chat_id=CHANNEL_ID,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id
                )
                bot.reply_to(message, "✅ Ваше сообщение опубликовано анонимно!")
            else:
                # Мат в тексте — тоже ждёт вашего решения (кнопки)
                pending[copied.message_id] = message.message_id
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("✅ Опубликовать", callback_data=f"pub_{copied.message_id}"),
                    types.InlineKeyboardButton("❌ Отклонить", callback_data=f"rej_{copied.message_id}")
                )
                bot.send_message(
                    ADMIN_ID,
                    "⚠️ Текст с запрещёнными словами. Что делаем?",
                    reply_markup=markup
                )
                bot.reply_to(
                    message,
                    "✅ Ваше сообщение отправлено на проверку администратору."
                )

    except Exception as e:
        bot.reply_to(message, "❌ Ошибка при отправке. Попробуйте позже.")
        print(f"Ошибка: {e}")

# ===== ОБРАБОТКА КНОПОК АДМИНА =====
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Нет доступа")
        return

    action, msg_id_str = call.data.split("_", 1)
    pending_msg_id = int(msg_id_str)

    if pending_msg_id not in pending:
        bot.answer_callback_query(call.id, "Уже обработано")
        bot.edit_message_reply_markup(
            chat_id=ADMIN_ID,
            message_id=call.message.message_id,
            reply_markup=None
        )
        return

    original_msg_id = pending.pop(pending_msg_id)

    if action == "pub":
        try:
            bot.copy_message(
                chat_id=CHANNEL_ID,
                from_chat_id=ADMIN_ID,
                message_id=pending_msg_id
            )
            bot.answer_callback_query(call.id, "✅ Опубликовано")
            bot.edit_message_text(
                "✅ Опубликовано в канал",
                chat_id=ADMIN_ID,
                message_id=call.message.message_id
            )
        except Exception as e:
            bot.answer_callback_query(call.id, f"Ошибка: {e}")

    elif action == "rej":
        bot.answer_callback_query(call.id, "❌ Отклонено")
        bot.edit_message_text(
            "❌ Отклонено",
            chat_id=ADMIN_ID,
            message_id=call.message.message_id
        )

# ===== ЗАПУСК =====
if __name__ == '__main__':
    print("Бот запущен...")
    bot.infinity_polling()
