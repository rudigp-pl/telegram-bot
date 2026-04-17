import logging
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# API Keys from environment variables (set in Railway dashboard)
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

# OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Conversation history per user (in-memory)
conversation_history = {}

# System prompt
SYSTEM_PROMPT = {
    "role": "system",
    "content": "Jesteś pomocnym asystentem AI. Odpowiadaj zwięźle i na temat. Potrafisz rozmawiać po polsku i po angielsku."
}

MAX_HISTORY = 20


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    conversation_history[user.id] = []
    await update.message.reply_html(
        f"Cześć {user.mention_html()}! 👋\n\n"
        f"Jestem botem opartym na GPT-4.1-mini. Napisz cokolwiek, a odpowiem!\n\n"
        f"/start - restart rozmowy\n"
        f"/reset - wyczyść historię\n"
        f"/help - pomoc"
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    conversation_history[user_id] = []
    await update.message.reply_text("🗑️ Historia rozmowy wyczyszczona!")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤖 Bot ChatGPT\n\n"
        "Napisz wiadomość, a odpowiem za pomocą GPT-4.1-mini.\n\n"
        "/start - restart\n"
        "/reset - wyczyść historię\n"
        "/help - pomoc"
    )


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message.text
    user_id = update.effective_user.id

    logger.info(f"User {user_id}: {user_message[:100]}")

    if user_id not in conversation_history:
        conversation_history[user_id] = []

    conversation_history[user_id].append({"role": "user", "content": user_message})

    if len(conversation_history[user_id]) > MAX_HISTORY:
        conversation_history[user_id] = conversation_history[user_id][-MAX_HISTORY:]

    messages = [SYSTEM_PROMPT] + conversation_history[user_id]

    try:
        await update.message.chat.send_action("typing")

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
        )

        bot_reply = response.choices[0].message.content
        conversation_history[user_id].append({"role": "assistant", "content": bot_reply})

        if len(bot_reply) <= 4096:
            await update.message.reply_text(bot_reply)
        else:
            for i in range(0, len(bot_reply), 4096):
                await update.message.reply_text(bot_reply[i:i+4096])

        logger.info(f"Bot reply to {user_id}: {bot_reply[:100]}")

    except Exception as e:
        logger.error(f"OpenAI error: {e}", exc_info=True)
        await update.message.reply_text(f"⚠️ Błąd: {str(e)[:200]}")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Error: {context.error}", exc_info=context.error)


def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reset", reset))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    application.add_error_handler(error_handler)

    logger.info("🤖 Bot started on Railway!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
