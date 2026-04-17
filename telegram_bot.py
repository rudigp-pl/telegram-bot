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

# Conversation history per user — stores previous_response_id for Responses API
user_sessions = {}

# System prompt
SYSTEM_INSTRUCTIONS = "Jesteś pomocnym asystentem AI z dostępem do internetu. Odpowiadaj zwięźle i na temat. Potrafisz rozmawiać po polsku i po angielsku. Jeśli pytanie dotyczy aktualnych wydarzeń, użyj wyszukiwania w internecie."


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_sessions[user.id] = None  # Reset session
    await update.message.reply_html(
        f"Cześć {user.mention_html()}! 👋\n\n"
        f"Jestem botem GPT z dostępem do internetu 🌐\n"
        f"Napisz cokolwiek, a odpowiem!\n\n"
        f"/start - restart rozmowy\n"
        f"/reset - wyczyść historię\n"
        f"/help - pomoc"
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_sessions[user_id] = None
    await update.message.reply_text("🗑️ Historia rozmowy wyczyszczona!")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤖 Bot ChatGPT + Web Search 🌐\n\n"
        "Napisz wiadomość, a odpowiem za pomocą GPT-4.1-mini.\n"
        "Mam dostęp do internetu — mogę szukać aktualnych informacji!\n\n"
        "/start - restart\n"
        "/reset - wyczyść historię\n"
        "/help - pomoc"
    )


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message.text
    user_id = update.effective_user.id

    logger.info(f"User {user_id}: {user_message[:100]}")

    try:
        await update.message.chat.send_action("typing")

        # Build request with Responses API
        request_params = {
            "model": "gpt-4.1-mini",
            "input": user_message,
            "instructions": SYSTEM_INSTRUCTIONS,
            "tools": [{"type": "web_search"}],
        }

        # Continue conversation if we have a previous response
        prev_id = user_sessions.get(user_id)
        if prev_id:
            request_params["previous_response_id"] = prev_id

        # Call OpenAI Responses API with web search
        response = client.responses.create(**request_params)

        # Save response ID for conversation continuity
        user_sessions[user_id] = response.id

        # Extract text from response
        bot_reply = response.output_text

        # Send reply
        if bot_reply:
            if len(bot_reply) <= 4096:
                await update.message.reply_text(bot_reply, disable_web_page_preview=True)
            else:
                for i in range(0, len(bot_reply), 4096):
                    await update.message.reply_text(bot_reply[i:i+4096], disable_web_page_preview=True)

        logger.info(f"Bot reply to {user_id}: {bot_reply[:100] if bot_reply else 'empty'}")

    except Exception as e:
        logger.error(f"OpenAI error: {e}", exc_info=True)
        # If previous_response_id caused error, reset and retry
        if "previous_response_id" in str(e):
            user_sessions[user_id] = None
            await update.message.reply_text("🔄 Sesja wygasła, spróbuj ponownie.")
        else:
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

    logger.info("🤖 Bot with Web Search started on Railway!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
