import os
import logging
import sqlite3
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

# ======== CONFIG ========

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

PORT = int(os.environ.get("PORT", 8000))
RAILWAY_URL = os.getenv("RAILWAY_STATIC_URL")

logging.basicConfig(level=logging.INFO)

DB_PATH = "market.db"
STATE_ORDER = 1

# ======== DATABASE ========

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        first_name TEXT,
        username TEXT,
        created_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        items TEXT,
        status TEXT DEFAULT 'new',
        created_at TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ======== START ========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT OR IGNORE INTO users VALUES (?, ?, ?, ?)",
        (user.id, user.first_name, user.username, datetime.now().isoformat())
    )

    conn.commit()
    conn.close()

    keyboard = [
        [InlineKeyboardButton("🛒 Buyurtma berish", callback_data="order")]
    ]

    await update.message.reply_text(
        f"Assalomu alaykum {user.first_name} 👋\n\nBuyurtma berish uchun tugmani bosing.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ======== ORDER ========

async def order_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "Mahsulotlarni yozing:\n\nMasalan:\n2kg kartoshka\n1kg piyoz"
    )

    return STATE_ORDER

async def save_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO orders (user_id, items, created_at) VALUES (?, ?, ?)",
        (user_id, text, datetime.now().isoformat())
    )

    order_id = cursor.lastrowid

    conn.commit()
    conn.close()

    # Admin xabari
    if ADMIN_ID:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"confirm_{order_id}"),
                InlineKeyboardButton("❌ Bekor qilish", callback_data=f"cancel_{order_id}")
            ]
        ])

        await context.bot.send_message(
            ADMIN_ID,
            f"🆕 Yangi buyurtma #{order_id}\n\n👤 User ID: {user_id}\n📦 {text}",
            reply_markup=keyboard
        )

    await update.message.reply_text("✅ Buyurtmangiz qabul qilindi!")

    return ConversationHandler.END

# ======== ADMIN ACTION ========

async def order_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    action, order_id = query.data.split("_")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT user_id FROM orders WHERE id=?", (order_id,))
    result = cursor.fetchone()

    if not result:
        await query.edit_message_text("Buyurtma topilmadi.")
        return

    user_id = result[0]

    new_status = "confirmed" if action == "confirm" else "cancelled"

    cursor.execute("UPDATE orders SET status=? WHERE id=?", (new_status, order_id))
    conn.commit()
    conn.close()

    await context.bot.send_message(
        user_id,
        f"Sizning buyurtmangiz #{order_id} {new_status.upper()}"
    )

    await query.edit_message_text(f"Buyurtma #{order_id} {new_status}")

# ======== MAIN ========

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(order_start, pattern="^order$")],
        states={
            STATE_ORDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_order)]
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(order_action, pattern="^(confirm|cancel)_"))

    print("Bot ishga tushdi 🚀")

    if RAILWAY_URL:
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=f"https://{RAILWAY_URL}"
        )
    else:
        app.run_polling()

if __name__ == "__main__":
    main()
