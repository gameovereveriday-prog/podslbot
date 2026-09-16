import telebot
import os
from telebot import types

# ===== НАСТРОЙКИ =====
# Токен берем из переменных окружения Bothost (безопасно!)
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 957705940  # ЗАМЕНИТЕ на ваш ID
CHANNEL_ID = -1004300683892  # ЗАМЕНИТЕ на ID канала

if not BOT_TOKEN:
    print("❌ ОШИБКА: Переменная BOT_TOKEN не найдена!")
    exit(1)

bot = telebot.TeleBot(BOT_TOKEN)
last_message = {}  # Хранилище последнего сообщения для команды /publish


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

    # Формируем информацию об отправителе (видите только вы)
    sender_info = (
        f"👤 От: {user.first_name} {user.last_name or ''}\n"
        f"🔗 Username: @{user.username or 'нет'}\n"
        f"🆔 ID: {user.id}\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
    )

    try:
        # 1. Отправляем вам "шапку" с данными автора
        bot.send_message(ADMIN_ID, sender_info)

        # 2. Копируем само сообщение (текст/фото/видео) вам в личку
        bot.copy_message(
            chat_id=ADMIN_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )

        # 3. Запоминаем это сообщение, чтобы потом можно было опубликовать командой
        last_message[ADMIN_ID] = message

        # 4. Подтверждение пользователю
        bot.reply_to(message, "✅ Ваше сообщение отправлено анонимно!")

    except Exception as e:
        bot.reply_to(message, "❌ Ошибка при отправке. Попробуйте позже.")
        print(f"Ошибка: {e}")


# ===== КОМАНДА ДЛЯ АДМИНА: ПУБЛИКАЦИЯ В КАНАЛ =====
@bot.message_handler(commands=['publish'])
def publish_to_channel(message):
    # Проверка, что команду пишет именно админ
    if message.from_user.id != ADMIN_ID:
        return

    if ADMIN_ID in last_message:
        original = last_message[ADMIN_ID]
        try:
            # Копируем сообщение в канал (анонимно, без ссылки на отправителя)
            bot.copy_message(
                chat_id=CHANNEL_ID,
                from_chat_id=original.chat.id,
                message_id=original.message_id
            )
            bot.reply_to(message, "✅ Успешно опубликовано в канал!")
            # Очищаем, чтобы нельзя было случайно запостить дважды
            del last_message[ADMIN_ID]
        except Exception as e:
            bot.reply_to(message, f"❌ Ошибка публикации: {e}")
    else:
        bot.reply_to(message, "Нет сообщений для публикации.")


# ===== ЗАПУСК =====
if __name__ == '__main__':
    print("Бот запущен...")
    bot.infinity_polling()