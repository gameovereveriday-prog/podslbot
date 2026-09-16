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

# ===== ХРАНИЛИЩЕ ДЛЯ МОДЕРАЦИИ =====
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

# ===== ОСНОВНОЙ ОБРАБОТЧИК (все типы контента, включая сообщения от админа) =====
@bot.message_handler(
    content_types=['text', 'photo', 'video', 'document', 'voice',
                   'audio', 'video_note', 'animation', 'sticker'],
    func=lambda message: message.chat.type == 'private'
                         and not (message.text or "").startswith('/')
)
def handle_anonymous_message(message):
    user = message.from_user
    is_admin = (user.id == ADMIN_ID)

    text_to_check = message.text or message.caption or ""
    bad_found = contains_bad_words(text_to_check)
    is_media = message.content_type in (
        'photo', 'video', 'document', 'voice',
        'audio', 'video_note', 'animation', 'sticker'
    )

    try:
        # ===== ШАПКА ВАМ (только если пишет НЕ админ) =====
        if not is_admin:
            sender_info = (
                f"👤 От: {user.first_name} {user.last_name or ''}\n"
                f"🔗 Username: @{user.username or 'нет'}\n"
                f"🆔 ID: {user.id}\n"
            )
            if bad_found:
                sender_info += f"🚫 Найдено: {', '.join(bad_found)}\n"
            sender_info += "➖➖➖➖➖➖➖➖➖➖"
            bot.send_message(ADMIN_ID, sender_info)

            # Копия сообщения вам
            copied = bot.copy_message(
                chat_id=ADMIN_ID,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            target_chat_for_buttons = ADMIN_ID
            copied_id = copied.message_id
        else:
            # Если пишет сам админ — не дублируем себе шапку,
            # а используем ЕГО ЖЕ сообщение как объект модерации.
            target_chat_for_buttons = message.chat.id
            copied_id = message.message_id

        # ===== ЛОГИКА =====
        if is_media or bad_found:
            # --- Требуется модерация (медиа ИЛИ мат) ---
            pending[(target_chat_for_buttons, copied_id)] = message.message_id

            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(
                    "✅ Опубликовать",
                    callback_data=f"pub|{target_chat_for_buttons}|{copied_id}"
                ),
                types.InlineKeyboardButton(
                    "❌ Отклонить",
                    callback_data=f"rej|{target_chat_for_buttons}|{copied_id}"
                )
            )
            label = "📷 Медиа на модерации" if is_media else "⚠️ Текст с запрещёнными словами"
            bot.send_message(
                target_chat_for_buttons,
                f"{label}. Что делаем?",
                reply_markup=markup
            )
            if not is_admin:
                bot.reply_to(
                    message,
                    "✅ Ваше сообщение отправлено на проверку администратору."
                )
        else:
            # --- Чистый текст: авто в канал ---
            bot.copy_message(
                chat_id=CHANNEL_ID,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            if not is_admin:
                bot.reply_to(message, "✅ Ваше сообщение опубликовано анонимно!")
            else:
                bot.reply_to(message, "✅ Опубликовано в канал (тест админа).")

    except Exception as e:
        bot.reply_to(message, "❌ Ошибка при отправке. Попробуйте позже.")
        print(f"Ошибка: {e}")

# ===== ОБРАБОТКА КНОПОК =====
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Нет доступа")
        return

    try:
        action, chat_id_str, msg_id_str = call.data.split("|")
        target_chat = int(chat_id_str)
        pending_msg_id = int(msg_id_str)
    except ValueError:
        bot.answer_callback_query(call.id, "Ошибка данных")
        return

    key = (target_chat, pending_msg_id)
    if key not in pending:
        bot.answer_callback_query(call.id, "Уже обработано")
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )
        return

    original_msg_id = pending.pop(key)

    if action == "pub":
        try:
            bot.copy_message(
                chat_id=CHANNEL_ID,
                from_chat_id=target_chat,
                message_id=pending_msg_id
            )
            bot.answer_callback_query(call.id, "✅ Опубликовано")
            bot.edit_message_text(
                "✅ Опубликовано в канал",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id
            )
        except Exception as e:
            bot.answer_callback_query(call.id, f"Ошибка: {e}")
            print(f"Ошибка публикации: {e}")

    elif action == "rej":
        bot.answer_callback_query(call.id, "❌ Отклонено")
        bot.edit_message_text(
            "❌ Отклонено",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )

# ===== ЗАПУСК =====
if __name__ == '__main__':
    print("Бот запущен...")
    bot.infinity_polling()
