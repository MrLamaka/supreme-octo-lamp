import time
import asyncio
import os
from collections import deque
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters

import nest_asyncio

nest_asyncio.apply()

# 🔑 Токен и ID канала из переменных окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID"))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# ⏳ Кулдаун
COOLDOWN = 120  # секунд

# 🥒 Очередь сообщений
message_queue = deque()
last_sent_time = 0

# 📥 Приём сообщений
async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global last_sent_time
    if not update.message:
        return

    now = time.time()
    time_since_last = now - last_sent_time
    time_left = COOLDOWN - time_since_last

    message_queue.append(update.message)

    if time_left > 0:
        await update.message.reply_text(
            f"Сообщение получено. До следующей отправки в канал осталось {int(time_left)} секунд."
        )
    else:
        await update.message.reply_text(
            "Сообщение получено и будет сразу отправлено в канал.\n✅ Вы уже можете снова отправить сообщение."
        )

# 📨 Пересылка
async def send_to_channel(bot, message):
    try:
        if message.text:
            await bot.send_message(chat_id=CHANNEL_ID, text=message.text)
        elif message.photo:
            await bot.send_photo(chat_id=CHANNEL_ID, photo=message.photo[-1].file_id, caption=message.caption or "")
        elif message.video:
            await bot.send_video(chat_id=CHANNEL_ID, video=message.video.file_id, caption=message.caption or "")
        elif message.document:
            await bot.send_document(chat_id=CHANNEL_ID, document=message.document.file_id, caption=message.caption or "")
        elif message.audio:
            await bot.send_audio(chat_id=CHANNEL_ID, audio=message.audio.file_id, caption=message.caption or "")
        elif message.voice:
            await bot.send_voice(chat_id=CHANNEL_ID, voice=message.voice.file_id)
        else:
            await bot.send_message(chat_id=CHANNEL_ID, text="(неподдерживаемый тип сообщения)")
    except Exception as e:
        print(f"Ошибка при отправке в канал: {e}")

# ⏲️ Очередь
async def queue_worker(app):
    global last_sent_time
    while True:
        now = time.time()
        if message_queue and (now - last_sent_time >= COOLDOWN):
            message = message_queue.popleft()
            await send_to_channel(app.bot, message)
            last_sent_time = now
        await asyncio.sleep(1)

# 🌐 Flask
flask_app = Flask(__name__)
telegram_app = Application.builder().token(BOT_TOKEN).build()
telegram_app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, forward_message))


@flask_app.route("/")
def home():
    return "Бот работает!"

@flask_app.route("/webhook", methods=["POST"])
async def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return "OK"

async def init_bot():
    await telegram_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    asyncio.create_task(queue_worker(telegram_app))
    print("Webhook установлен.")

if __name__ == "__main__":
    asyncio.run(init_bot())
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))