import sqlite3
import logging
from datetime import datetime
from telegram import (
    Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, ConversationHandler
)
import os

# ========== ENVIRONMENT VARIABLES ==========
BOT_TOKEN = os.getenv('BOT_TOKEN', '8743932506:AAFKE1rUE8PkemE-dNgwYYdDUdjzgnSNDBs')
ADMIN_ID = int(os.getenv('ADMIN_ID', '7887637727'))
ADMIN_PHONE = os.getenv('ADMIN_PHONE', '+998883822500')
CHANNEL = os.getenv('CHANNEL', '@yoriyev_market')
ABOUT_URL = "https://t.me/biz_haqimizda_yoriyev_market"
PARTNERS_URL = "https://t.me/hamkorlarimiz_yoriyev_market"

# ========== LOGGING ==========
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== DATABASE ==========
conn = sqlite3.connect("yoriyev_market.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    first_name TEXT,
    username TEXT,
    phone TEXT,
    address TEXT,
    registered_at TEXT,
    last_active TEXT,
    referred_by INTEGER,
    discount_count INTEGER DEFAULT 0,
    total_orders INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    items TEXT,
    status TEXT DEFAULT 'yangi',
    created_at TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    text TEXT,
    type TEXT,
    created_at TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS promotions (
    id INTEGER PRIMARY KEY CHECK (id=1),
    text TEXT
)
""")
conn.commit()

# ========== STATES ==========
(
    PRODUCT, NAME, PHONE, ADDRESS
) = range(4)

# ========== START ==========
def start(update: Update, context):
    user = update.effective_user
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user.id,))
    if cursor.fetchone() is None:
        cursor.execute(
            "INSERT INTO users (user_id, first_name, username, registered_at, last_active) VALUES (?, ?, ?, ?, ?)",
            (user.id, user.first_name, user.username, datetime.now(), datetime.now())
        )
        conn.commit()
    check_subscription(update, context)

def check_subscription(update: Update, context):
    user = update.effective_user
    # Telegram API orqali a'zolikni tekshirish mumkin emas, shuning uchun faqat xabar chiqaramiz
    keyboard = [
        [
            InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL.lstrip('@')}"),
            InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")
        ]
    ]
    update.message.reply_text(
        f"🌟 Assalomu alaykum {user.first_name}!\n"
        f"Botdan foydalanish uchun kanalimizga a'zo bo'ling.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def check_sub(update: Update, context):
    query = update.callback_query
    query.answer()
    # Bu yerda haqiqiy a'zolik tekshiruvi qilish uchun Telegram API kerak
    query.edit_message_text(f"✅ A'zo bo'lgansiz! Endi asosiy menyu:")
    main_menu(query, context)

# ========== MAIN MENU ==========
def main_menu(update_obj, context):
    keyboard = [
        [InlineKeyboardButton("🛒 Mahsulotlar", callback_data="menu_products")],
        [InlineKeyboardButton("📢 Aksiyalar", callback_data="menu_promo")],
        [InlineKeyboardButton("🤝 Hamkorlar", callback_data="menu_partners")],
        [InlineKeyboardButton("📌 Biz haqimizda", callback_data="menu_about")],
        [InlineKeyboardButton("📞 Admin bilan bog'lanish", callback_data="menu_contact")],
        [InlineKeyboardButton("⚠️ Shikoyat / Taklif", callback_data="menu_complaint")],
        [InlineKeyboardButton("💡 Taklif qilish", callback_data="menu_referral")],
        [InlineKeyboardButton("💳 To'lov tizimi", callback_data="menu_payment")],
    ]
    if hasattr(update_obj, "edit_message_text"):
        update_obj.edit_message_text(
            "🏠 Bosh menyu\n\nQuyidagi bo‘limlardan birini tanlang:", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        update_obj.message.reply_text(
            "🏠 Bosh menyu\n\nQuyidagi bo‘limlardan birini tanlang:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ========== PRODUCTS ==========
def menu_products(update: Update, context):
    query = update.callback_query
    query.answer()
    keyboard = [
        [InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL.lstrip('@')}"),
         InlineKeyboardButton("✅ Buyurtma berish", callback_data="order_start")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ]
    query.edit_message_text(
        f"🛒 Mahsulotlar\n\nKerakli mahsulotlarni kanaldan tanlang va bizga xabar shaklida yozing.\n\n👉 {CHANNEL}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def order_start(update: Update, context):
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        "📝 Mahsulotlar ro'yxatini yozing:\nMasalan: 2 kg kartoshka, 1 kg piyoz, 3 dona banan",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]])
    )
    return PRODUCT

def receive_product(update: Update, context):
    context.user_data['items'] = update.message.text
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("✍️ Ism yozish"), KeyboardButton("📱 Profilni yuborish", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True
    )
    update.message.reply_text("👤 Ismingizni kiriting yoki profilni yuboring:", reply_markup=keyboard)
    return NAME

def receive_name(update: Update, context):
    if update.message.contact:
        context.user_data['first_name'] = update.message.contact.first_name
        context.user_data['phone'] = update.message.contact.phone_number
    else:
        context.user_data['first_name'] = update.message.text
        update.message.reply_text("📞 Telefon raqamingizni kiriting:\nFormat: +998901234567")
        return PHONE
    update.message.reply_text("📍 Manzilingizni kiriting:\nMasalan: Chalmagadoy qishlog'i, Paynet ro'parasi",
                              reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True, one_time_keyboard=True))
    return ADDRESS

def receive_phone(update: Update, context):
    context.user_data['phone'] = update.message.text
    update.message.reply_text("📍 Manzilingizni kiriting:\nMasalan: Chalmagadoy qishlog'i, Paynet ro'parasi",
                              reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True, one_time_keyboard=True))
    return ADDRESS

def receive_address(update: Update, context):
    context.user_data['address'] = update.message.text
    user_id = update.effective_user.id
    items = context.user_data['items']
    name = context.user_data['first_name']
    phone = context.user_data['phone']
    address = context.user_data['address']
    created_at = datetime.now()

    cursor.execute(
        "INSERT INTO orders (user_id, items, status, created_at) VALUES (?, ?, 'yangi', ?)",
        (user_id, items, created_at)
    )
    order_id = cursor.lastrowid
    conn.commit()

    context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"🆕 YANGI BUYURTMA!\n\n👤 Ism: {name}\n📞 Tel: {phone}\n📍 Manzil: {address}\n🆔 ID: {user_id}\n📦 Mahsulotlar: {items}\n🔢 Buyurtma №: {order_id}\n🔗 Profil: tg://user?id={user_id}"
    )

    update.message.reply_text(
        f"✅ Buyurtmangiz qabul qilindi!\nTez orada admin siz bilan bog'lanadi.\n\n<i>Yoriyev Market tomonidan sizga rahmat!</i>\n\n[🏠 Bosh menyu]",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]])
    )
    return ConversationHandler.END

# ========== CALLBACK HANDLER ==========
def button_handler(update: Update, context):
    query = update.callback_query
    data = query.data

    if data == "main_menu":
        main_menu(query, context)
    elif data == "menu_products":
        menu_products(update, context)
    elif data == "order_start":
        order_start(update, context)
    elif data == "menu_about":
        query.edit_message_text(
            f"📌 Biz haqimizda\n\nYoriyev Market – Peshku tumanidagi eng arzon va sifatli meva-sabzavotlar yetkazib berish xizmati.\n\nManzil: Buxoro, Peshku, Chalmagadoy qishlog'i (Paynet ro'parasi)\nTelefon: {ADMIN_PHONE}\n\n👉 {ABOUT_URL}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]])
        )
    elif data == "menu_partners":
        query.edit_message_text(
            f"🤝 Hamkorlarimiz\n\nBiz bilan hamkorlik qilayotgan tashkilotlar:\n\n👉 {PARTNERS_URL}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]])
        )
    elif data == "menu_contact":
        query.edit_message_text(
            f"📞 Admin bilan bog'lanish\n\nAdmin: @akmalyoriyev\nTelefon: {ADMIN_PHONE}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]])
        )
    elif data == "menu_promo":
        cursor.execute("SELECT text FROM promotions WHERE id=1")
        promo = cursor.fetchone()
        text = promo[0] if promo else "Aksiyalar mavjud emas."
        query.edit_message_text(
            f"📢 Aksiyalar\n\n{text}\n\n👉 {CHANNEL}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]])
        )
    elif data == "menu_complaint":
        query.edit_message_text(
            "📝 Shikoyat yoki taklif?\n⚠️ Shikoyat\n💡 Taklif",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]])
        )
    elif data == "menu_referral":
        user_id = update.effective_user.id
        ref_link = f"https://t.me/Yoriyev_market_bot?start=ref_{user_id}"
        query.edit_message_text(
            f"💡 Taklif qilish tizimi\n\nDo'stlaringizni taklif qiling va chegirmalar oling!\n🔗 Sizning havolangiz: {ref_link}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]])
        )
    elif data == "menu_payment":
        query.edit_message_text(
            "💳 To'lov tizimi\n\nMahsulot sizga yoqsa, keyin to'lov qilasiz.\n💡 To'lov usullari: naqd, Click, Payme, Apelsin",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]])
        )
    elif data == "check_sub":
        check_sub(update, context)

# ========== MAIN ==========
def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="order_start")],
        states={
            PRODUCT: [MessageHandler(Filters.text & ~Filters.command, receive_product)],
            NAME: [MessageHandler(Filters.text | Filters.contact, receive_name)],
            PHONE: [MessageHandler(Filters.text & ~Filters.command, receive_phone)],
            ADDRESS: [MessageHandler(Filters.text & ~Filters.command, receive_address)],
        },
        fallbacks=[CallbackQueryHandler(button_handler, pattern="main_menu")]
    )

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(conv_handler)
    dp.add_handler(CallbackQueryHandler(button_handler))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
