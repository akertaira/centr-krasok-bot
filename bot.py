"""
Telegram AI-бот для компании «Центр Красок #1»
Использует Groq API (бесплатно) — модель llama-3.3-70b-versatile
"""

import os
import asyncio
import logging
from collections import defaultdict
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
from groq import Groq
from dotenv import load_dotenv

from company_knowledge import COMPANY_KNOWLEDGE

load_dotenv()


# ─────────────────────────────────────────────
# Логирование
# ─────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Токены из переменных окружения
# ─────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

if not TELEGRAM_TOKEN:
    raise ValueError("Задайте TELEGRAM_TOKEN в переменных окружения")
if not GROQ_API_KEY:
    raise ValueError("Задайте GROQ_API_KEY в переменных окружения")

# ─────────────────────────────────────────────
# Groq клиент
# ─────────────────────────────────────────────
groq_client = Groq(api_key=GROQ_API_KEY)
GROQ_MODEL = "llama-3.3-70b-versatile"

# ─────────────────────────────────────────────
# История диалогов (в памяти)
# ─────────────────────────────────────────────
MAX_HISTORY = 10
conversation_history: dict[int, list[dict]] = defaultdict(list)

# ─────────────────────────────────────────────
# Системный промпт
# ─────────────────────────────────────────────
SYSTEM_PROMPT = f"""Ты — вежливый AI-ассистент интернет-магазина «Центр Красок #1» (Казахстан).
Твоя задача — помогать клиентам, отвечая на вопросы о компании, товарах, услугах, доставке и адресах.

БАЗА ЗНАНИЙ О КОМПАНИИ:
{COMPANY_KNOWLEDGE}

ПРАВИЛА:
1. Отвечай ТОЛЬКО на основе базы знаний. Не придумывай факты.
2. Если информации нет в базе — честно скажи и предложи позвонить: +7 (777) 292-84-01 или info@centr-krasok.kz.
3. Если вопрос не связан с компанией — вежливо объясни, что специализируешься только на вопросах «Центр Красок #1».
4. Пиши на русском. Если пользователь пишет на казахском — отвечай на казахском.
5. Отвечай дружелюбно и ёмко. Используй 1–2 эмодзи в ответе.
6. На вопросы о конкретных ценах (которых нет в базе) — отправляй на каталог: https://centr-krasok.kz/catalog/
7. НЕ цитируй базу напрямую — давай живые разговорные ответы.
"""


# ─────────────────────────────────────────────
# Обработчики
# ─────────────────────────────────────────────
async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Приветствие и сброс истории."""
    chat_id = update.effective_chat.id
    conversation_history[chat_id] = []

    await update.message.reply_text(
        "👋 Привет! Я AI-ассистент магазина «Центр Красок #1».\n\n"
        "Помогу с:\n"
        "🎨 Выбором красок и материалов\n"
        "📦 Информацией об ассортименте и брендах\n"
        "🚚 Условиями доставки\n"
        "📍 Адресами шоурумов\n\n"
        "Просто напишите ваш вопрос!"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает текстовое сообщение пользователя."""
    chat_id = update.effective_chat.id
    user_text = update.message.text.strip()

    if not user_text:
        return

    logger.info("chat_id=%s | %s", chat_id, user_text[:80])
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    # Обновляем историю
    history = conversation_history[chat_id]
    history.append({"role": "user", "content": user_text})

    # Исправлено: сохраняем обрезанную историю обратно
    if len(history) > MAX_HISTORY * 2:
        conversation_history[chat_id] = history[-(MAX_HISTORY * 2):]
        history = conversation_history[chat_id]

    # Формируем сообщения для Groq (system + история)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            max_tokens=800,
            temperature=0.4,
        )
        reply = response.choices[0].message.content.strip()

        history.append({"role": "assistant", "content": reply})
        await update.message.reply_text(reply)
        logger.info("Ответ отправлен для chat_id=%s", chat_id)

    except Exception as e:
        logger.exception("Ошибка Groq API: %s", e)
        await update.message.reply_text(
            "😔 Произошла техническая ошибка. Попробуйте ещё раз или свяжитесь с нами: "
            "+7 (777) 292-84-01"
        )


# ─────────────────────────────────────────────
# Запуск
# ─────────────────────────────────────────────
def main() -> None:
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("reset", handle_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Бот запущен (Groq / %s)", GROQ_MODEL)

    # Фикс для Python 3.14+
    try:
        app.run_polling()
    except RuntimeError as e:
        if "no current event loop" in str(e):
            asyncio.run(app.run_polling())
        else:
            raise


if __name__ == "__main__":
    main()