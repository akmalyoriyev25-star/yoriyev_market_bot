# main.py
import logging
import sqlite3
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackQueryHandler,
    CallbackContext,
    ConversationHandler,
)

# --- CONFIGURATION ---
BOT_TOKEN = "8743932506:AAFKE1rUE8PkemE-dNgwYYdDUdjzgnSNDBs"
ADMIN_ID = 7887637727
ADMIN_PHONE = "+998883822500"
CHANNEL = "@yoriyev_market"
BIZ_HAQIMIZDA = "https://t.me/biz_haqimizda_yoriyev_market"
HAMKORLAR = "https://t.me/hamkorlarimiz_yoriyev_market"

# --- LOGGING ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect("yoriyev_market.db")
    c = conn.cursor()
    # Users
    c.execute("""
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
    # Orders
    c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            items TEXT,
            status TEXT DEFAULT 'yangi',
            created_at TEXT
        )
    """)
    # Complaints/Feedback
    c.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT,
            type TEXT,
            created_at TEXT
        )
    """)
    # Promotions (only 1 row)
    c.execute("""
        CREATE TABLE IF NOT EXISTS promotions (
            id INTEGER PRIMARY KEY CHECK(id=1),
            text TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect("yoriyev_market.db")
    conn.row_factory = sqlite3.Row
    return conn

# --- STATES ---
PRODUCTS, NAME, PHONE, ADDRESS = range(4)

# --- START COMMAND ---
def start(update: Update, context: CallbackContext):
    user = update.effective_user
    chat_id = update.effective_chat.id
    first_name = user.first_name or "Foydalanuvchi"

    # Referral check
    ref_id = None
    if context.args:
        arg = context.args[0]
        if arg.startswith("ref_"):
            try:
                ref_id = int(arg.split("_")[1])
            except:
                ref_id = None

    conn = get_db()
    c = conn.cursor()
    # Insert user if not exists
    c.execute("SELECT * FROM users WHERE user_id=?", (user.id,))
    row = c.fetchone()
    if not row:
        c.execute("""
            INSERT INTO users (user_id, first_name, username, registered_at, referred_by)
            VALUES (?, ?, ?, ?, ?)
        """, (user.id, first_name, user.username, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ref_id))
        conn.commit()
    conn.close()

    # Check if user joined channel
    buttons = [
        [InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL.lstrip('@')}")],
        [InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")]
    ]
    update.message.reply_text(
        f"🌟 Assalomu alaykum {first_name}!\nBotdan foydalanish uchun kanalimizga a'zo bo'ling.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# --- CHANNEL CHECK ---
def check_sub(update: Update, context: CallbackContext):
    query = update.callback_query
    user = query.from_user
    try:
        member = context.bot.get_chat_member(CHANNEL, user.id)
        if member.status in ["member", "creator", "administrator"]:
            query.answer()
            query.edit_message_text("✅ A'zo bo'lgansiz! 🎉")
            main_menu(query, context)
        else:
            query.answer()
            query.edit_message_text(
                f"❌ Siz kanalga a'zo emassiz! Iltimos a'zo bo'ling: @{CHANNEL.lstrip('@')}"
            )
    except Exception as e:
        logger.warning(f"Channel check error: {e}")
        query.edit_message_text(
            f"❌ Kanalga a'zo bo'lishda xatolik yuz berdi. @{CHANNEL.lstrip('@')}"
        )

# --- MAIN MENU ---
def main_menu(update_or_query, context):
    buttons = [
        [InlineKeyboardButton("🛒 Mahsulotlar", callback_data="menu_products"),
         InlineKeyboardButton("📢 Aksiyalar", callback_data="menu_promo")],
        [InlineKeyboardButton("🤝 Hamkorlar", callback_data="menu_partners"),
         InlineKeyboardButton("📌 Biz haqimizda", callback_data="menu_about")],
        [InlineKeyboardButton("📞 Admin bilan bog'lanish", callback_data="menu_contact"),
         InlineKeyboardButton("⚠️ Shikoyat / Taklif", callback_data="menu_complaint")],
        [InlineKeyboardButton("💡 Taklif qilish", callback_data="menu_referral"),
         InlineKeyboardButton("💳 To'lov tizimi", callback_data="menu_payment")]
    ]
    text = "🏠 Bosh menyu"
    if hasattr(update_or_query, "edit_message_text"):
        update_or_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        update_or_query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# --- CALLBACK HANDLER ---
def callback_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data

    if data == "menu_products":
        show_products(query, context)
    elif data == "order_start":
        query.edit_message_text("📝 Mahsulotlar ro'yxatini yozing:\nMasalan: 2 kg kartoshka, 1 kg piyoz\n[⬅️ Orqaga]", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]))
        return PRODUCTS
    elif data == "menu_promo":
        show_promo(query, context)
    elif data == "menu_partners":
        show_partners(query)
    elif data == "menu_about":
        show_about(query)
    elif data == "menu_contact":
        show_admin_contact(query)
    elif data == "menu_complaint":
        show_complaint(query)
    elif data == "menu_referral":
        show_referral(query, context)
    elif data == "menu_payment":
        show_payment(query)
    elif data == "main_menu":
        main_menu(query, context)
    elif data == "check_sub":
        check_sub(update, context)
    elif data == "show_phone":
        query.edit_message_text(f"📞 Admin telefon raqami: {ADMIN_PHONE}\n[⬅️ Orqaga]", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_contact")]]))

# --- PRODUCTS ---
def show_products(query, context):
    text = f"🛒 Mahsulotlar\n\nKerakli mahsulotlarni kanaldan tanlang va bizga xabar shaklida yozing.\n👉 @{CHANNEL.lstrip('@')}"
    buttons = [
        [InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL.lstrip('@')}"),
         InlineKeyboardButton("✅ Buyurtma berish", callback_data="order_start")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ]
    query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# --- PROMO ---
def show_promo(query, context):
    conn = get_db()
    c = conn.cursor()
    promo = c.execute("SELECT text FROM promotions WHERE id=1").fetchone()
    text = promo['text'] if promo else "Aksiyalar mavjud emas."
    query.edit_message_text(f"📢 Aksiyalar\n\n{text}\n\n👉 @{CHANNEL.lstrip('@')}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]))
    conn.close()

# --- PARTNERS ---
def show_partners(query):
    text = f"🤝 Hamkorlarimiz\n\nBiz bilan hamkorlik qilayotgan tashkilotlar:\n👉 {HAMKORLAR}"
    query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL.lstrip('@')}")],[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]))

# --- ABOUT ---
def show_about(query):
    text = f"📌 Biz haqimizda\n\nYoriyev Market – Peshku tumanidagi eng arzon va sifatli meva-sabzavotlar yetkazib berish xizmati.\n\nManzil: Buxoro, Peshku, Chalmagadoy qishlog'i (Paynet ro'parasi)\nTelefon: {ADMIN_PHONE}\n👉 {BIZ_HAQIMIZDA}"
    query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL.lstrip('@')}")],[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]))

# --- ADMIN CONTACT ---
def show_admin_contact(query):
    text = f"📞 Admin bilan bog'lanish\nAdmin: @akmalyoriyev\nTugmalar orqali bog'laning:"
    buttons = [
        [InlineKeyboardButton("👤 Admin profili", url=f"https://t.me/akmalyoriyev")],
        [InlineKeyboardButton("📞 Telefon raqam", callback_data="show_phone")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ]
    query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# --- COMPLAINT / SUGGESTION ---
def show_complaint(query):
    buttons = [
        [InlineKeyboardButton("⚠️ Shikoyat", callback_data="complaint")],
        [InlineKeyboardButton("💡 Taklif", callback_data="suggestion")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ]
    query.edit_message_text("📝 Shikoyat yoki taklif?", reply_markup=InlineKeyboardMarkup(buttons))

# --- REFERRAL ---
def show_referral(query, context):
    user_id = query.from_user.id
    conn = get_db()
    c = conn.cursor()
    count = c.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (user_id,)).fetchone()[0]
    discount = c.execute("SELECT discount_count FROM users WHERE user_id=?", (user_id,)).fetchone()[0]
    ref_link = f"https://t.me/Yoriyev_market_bot?start=ref_{user_id}"
    text = f"💡 Taklif qilish tizimi\n\nDo'stlaringizni taklif qiling va chegirmalar oling!\n🔗 Sizning havolangiz: {ref_link}\nTaklif qilganlaringiz: {count}\nChegirmalaringiz: {discount}\n\n[⬅️ Orqaga]"
    query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]))
    conn.close()

# --- PAYMENT ---
def show_payment(query):
    text = f"💳 To'lov tizimi\n\nMahsulot sizga yoqsa, keyin to'lov qilasiz. Buyurtma berish jarayonida to'lov haqida admin bilan kelishiladi.\n💡 To'lov usullari: naqd, Click, Payme, Apelsin.\n[⬅️ Orqaga]"
    query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]))

# --- ORDER FLOW ---
def products_input(update: Update, context: CallbackContext):
    context.user_data['items'] = update.message.text
    update.message.reply_text("👤 Ismingizni kiriting yoki profilni yuboring:", reply_markup=ReplyKeyboardMarkup([
        [KeyboardButton("✍️ Ism yozish"), KeyboardButton("📱 Profilni yuborish", request_contact=True)]
    ], resize_keyboard=True, one_time_keyboard=True))
    return NAME

def name_input(update: Update, context: CallbackContext):
    if update.message.contact:
        context.user_data['first_name'] = update.message.contact.first_name
        context.user_data['phone'] = update.message.contact.phone_number
        update.message.reply_text("📍 Manzilingizni kiriting:", reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True))
        return ADDRESS
    else:
        context.user_data['first_name'] = update.message.text
        update.message.reply_text("📞 Telefon raqamingizni kiriting:", reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("📱 Profilni yuborish", request_contact=True)]
        ], resize_keyboard=True, one_time_keyboard=True))
        return PHONE

def phone_input(update: Update, context: CallbackContext):
    if update.message.contact:
        context.user_data['phone'] = update.message.contact.phone_number
    else:
        context.user_data['phone'] = update.message.text
    update.message.reply_text("📍 Manzilingizni kiriting:", reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True))
    return ADDRESS

def address_input(update: Update, context: CallbackContext):
    context.user_data['address'] = update.message.text
    user_id = update.message.from_user.id
    items = context.user_data['items']
    first_name = context.user_data['first_name']
    phone = context.user_data['phone']
    address = context.user_data['address']

    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO orders (user_id, items, status, created_at) VALUES (?, ?, 'yangi', ?)", (user_id, items, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    order_id = c.lastrowid
    conn.commit()
    conn.close()

    # Admin notification
    context.bot.send_message(ADMIN_ID, f"🆕 YANGI BUYURTMA!\n\n👤 Ism: {first_name}\n📞 Tel: {phone}\n📍 Manzil: {address}\n🆔 ID: {user_id}\n📦 Mahsulotlar: {items}\n🔢 Buyurtma №: {order_id}\n🔗 Profil: tg://user?id={user_id}")

    # Confirmation to user
    update.message.reply_text("✅ Buyurtmangiz qabul qilindi!\nTez orada admin siz bilan bog'lanadi.\n<i>Yoriyev Market tomonidan sizga rahmat!</i>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]]))

    return ConversationHandler.END

# --- MAIN ---
def main():
    init_db()
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(callback_handler, pattern="order_start")],
        states={
            PRODUCTS: [MessageHandler(Filters.text & ~Filters.command, products_input)],
            NAME: [MessageHandler(Filters.text & ~Filters.command | Filters.contact, name_input)],
            PHONE: [MessageHandler(Filters.text & ~Filters.command | Filters.contact, phone_input)],
            ADDRESS: [MessageHandler(Filters.text & ~Filters.command, address_input)],
        },
        fallbacks=[CommandHandler("start", start)]
    )

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(callback_handler))
    dp.add_handler(conv_handler)

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
  # --- ADMIN PANEL ---
def admin_panel(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        update.message.reply_text("❌ Siz admin emassiz!")
        return

    buttons = [
        [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton("📦 Yangi buyurtmalar", callback_data="admin_orders")],
        [InlineKeyboardButton("⚠️ Shikoyatlar", callback_data="admin_complaints")],
        [InlineKeyboardButton("💡 Takliflar", callback_data="admin_suggestions")],
        [InlineKeyboardButton("📢 Aksiyani tahrirlash", callback_data="admin_edit_promo")],
        [InlineKeyboardButton("📤 Xabar yuborish", callback_data="admin_broadcast")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ]
    update.message.reply_text("🛠 Admin panel", reply_markup=InlineKeyboardMarkup(buttons))

# --- ADMIN CALLBACK HANDLER ---
def admin_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data
    conn = get_db()
    c = conn.cursor()

    if data == "admin_stats":
        users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        new_orders = c.execute("SELECT COUNT(*) FROM orders WHERE status='yangi'").fetchone()[0]
        today_orders = c.execute("SELECT COUNT(*) FROM orders WHERE date(created_at)=date('now')").fetchone()[0]
        complaints = c.execute("SELECT COUNT(*) FROM complaints WHERE type='shikoyat'").fetchone()[0]
        suggestions = c.execute("SELECT COUNT(*) FROM complaints WHERE type='taklif'").fetchone()[0]
        text = f"📊 Statistika\n\n👥 Jami foydalanuvchilar: {users}\n🆕 Yangi buyurtmalar: {new_orders}\n📅 Bugungi buyurtmalar: {today_orders}\n⚠️ Shikoyatlar: {complaints}\n💡 Takliflar: {suggestions}"
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]))

    elif data == "admin_orders":
        rows = c.execute("SELECT * FROM orders WHERE status='yangi'").fetchall()
        text = "📦 Yangi buyurtmalar:\n\n"
        for r in rows:
            text += f"ID: {r['id']}\nUser: {r['user_id']}\nMahsulotlar: {r['items']}\nSana: {r['created_at']}\n\n"
        query.edit_message_text(text if text != "" else "Yangi buyurtmalar mavjud emas", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]))

    elif data == "admin_complaints":
        rows = c.execute("SELECT * FROM complaints WHERE type='shikoyat' ORDER BY id DESC LIMIT 10").fetchall()
        text = "⚠️ Oxirgi 10 ta shikoyat:\n\n"
        for r in rows:
            text += f"ID: {r['id']}\nUser: {r['user_id']}\nXabar: {r['text']}\nSana: {r['created_at']}\n\n"
        query.edit_message_text(text if text != "" else "Shikoyat mavjud emas", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]))

    elif data == "admin_suggestions":
        rows = c.execute("SELECT * FROM complaints WHERE type='taklif' ORDER BY id DESC LIMIT 10").fetchall()
        text = "💡 Oxirgi 10 ta taklif:\n\n"
        for r in rows:
            text += f"ID: {r['id']}\nUser: {r['user_id']}\nXabar: {r['text']}\nSana: {r['created_at']}\n\n"
        query.edit_message_text(text if text != "" else "Taklif mavjud emas", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]))

    elif data == "admin_edit_promo":
        query.edit_message_text("📢 Aksiyani tahrirlash: yangi matnni yuboring", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]))
        context.user_data['edit_promo'] = True

    elif data == "admin_broadcast":
        query.edit_message_text("📤 Foydalanuvchilarga xabar yuboring:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]))
        context.user_data['broadcast'] = True

    conn.close()
    query.answer()

# --- ADMIN TEXT HANDLER ---
def admin_text_handler(update: Update, context: CallbackContext):
    if context.user_data.get('edit_promo'):
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO promotions (id, text) VALUES (1, ?)", (update.message.text,))
        conn.commit()
        conn.close()
        update.message.reply_text("✅ Aksiya yangilandi!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]))
        context.user_data['edit_promo'] = False

    elif context.user_data.get('broadcast'):
        conn = get_db()
        c = conn.cursor()
        users = c.execute("SELECT user_id FROM users").fetchall()
        conn.close()
        for u in users:
            try:
                context.bot.send_message(u['user_id'], f"📢 Broadcast xabar:\n\n{update.message.text}")
            except:
                continue
        update.message.reply_text("✅ Xabar yuborildi!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]))
        context.user_data['broadcast'] = False

# --- INTEGRATE WITH MAIN ---
def main_admin():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("admin", admin_panel))
    dp.add_handler(CallbackQueryHandler(admin_callback, pattern="admin_"))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, admin_text_handler))
    updater.start_polling()
    updater.idle()
  # main.py davomiy qism
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, Update
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext
import sqlite3
import os
from datetime import datetime

# Env variables
BOT_TOKEN = os.getenv("BOT_TOKEN", "8743932506:AAFKE1rUE8PkemE-dNgwYYdDUdjzgnSNDBs")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7887637727"))
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@yoriyev_market")
ADMIN_PHONE = os.getenv("ADMIN_PHONE", "+998883822500")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "@yoriyev_market")
BOT_USERNAME = os.getenv("BOT_USERNAME", "Yoriyev_market_bot")

DB_FILE = "yoriyev_market.db"

# =======================
# DB FUNCTIONS
# =======================
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
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
        conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            items TEXT,
            status TEXT DEFAULT 'yangi',
            created_at TEXT
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT,
            type TEXT,
            created_at TEXT
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS promotions (
            id INTEGER PRIMARY KEY CHECK (id=1),
            text TEXT
        )
        """)

# =======================
# START COMMAND
# =======================
def start(update: Update, context: CallbackContext):
    user = update.effective_user
    with get_db() as conn:
        if not conn.execute("SELECT 1 FROM users WHERE user_id=?", (user.id,)).fetchone():
            referred_by = None
            if context.args and context.args[0].startswith("ref_"):
                try:
                    referred_by = int(context.args[0].split("_")[1])
                except:
                    referred_by = None
            conn.execute("INSERT INTO users (user_id, first_name, username, registered_at, referred_by) VALUES (?, ?, ?, ?, ?)",
                         (user.id, user.first_name, user.username, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), referred_by))
    # Kanalga a'zo bo'lish tekshiruvi
    try:
        member = context.bot.get_chat_member(CHANNEL_USERNAME, user.id)
        if member.status in ['member', 'creator', 'administrator']:
            show_main_menu(update, context)
        else:
            send_sub_message(update, context)
    except:
        send_sub_message(update, context)

def send_sub_message(update, context):
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"),
         InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")]
    ]
    update.message.reply_text(f"🌟 Assalomu alaykum {user.first_name}!\nBotdan foydalanish uchun kanalimizga a'zo bo'ling.", 
                              reply_markup=InlineKeyboardMarkup(keyboard))

# =======================
# CALLBACKS
# =======================
def callback_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data
    query.answer()
    
    if data == "check_sub":
        user = query.from_user
        try:
            member = context.bot.get_chat_member(CHANNEL_USERNAME, user.id)
            if member.status in ['member', 'creator', 'administrator']:
                query.edit_message_text("✅ A'zo bo'lgansiz!")
                show_main_menu(update, context)
            else:
                query.edit_message_text("❌ Kanalga a'zo bo'lishingiz kerak.", reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"),
                     InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")]
                ]))
        except:
            query.edit_message_text("❌ Xatolik yuz berdi. Kanalni tekshirib ko'ring.")
    
    elif data == "menu_products":
        query.edit_message_text(
            f"🛒 Mahsulotlar\n\nKerakli mahsulotlarni kanaldan tanlang va bizga xabar shaklida yozing.\n\n👉 {CHANNEL_USERNAME}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"),
                InlineKeyboardButton("✅ Buyurtma berish", callback_data="order_start")
            ]])
        )
    elif data == "main_menu":
        show_main_menu(update, context)
    elif data == "menu_promo":
        with get_db() as conn:
            promo = conn.execute("SELECT text FROM promotions WHERE id=1").fetchone()
            text = promo['text'] if promo else "Aksiyalar mavjud emas."
        query.edit_message_text(f"📢 Aksiyalar\n\n{text}\n\n👉 {CHANNEL_USERNAME}",
                                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]))
    elif data == "menu_about":
        query.edit_message_text(f"📌 Biz haqimizda\n\nYoriyev Market – Peshku tumanidagi eng arzon va sifatli meva-sabzavotlar yetkazib berish xizmati.\n\nManzil: Buxoro, Peshku, Chalmagadoy qishlog'i (Paynet ro'parasi)\nTelefon: {ADMIN_PHONE}\n\n👉 https://t.me/biz_haqimizda_yoriyev_market",
                                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]))
    elif data == "menu_contact":
        query.edit_message_text(f"📞 Admin bilan bog'lanish\n\nAdmin: {ADMIN_USERNAME}\nTelefon: {ADMIN_PHONE}",
                                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]))

# =======================
# MAIN MENU
# =======================
def show_main_menu(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("🛒 Mahsulotlar", callback_data="menu_products"),
         InlineKeyboardButton("📢 Aksiyalar", callback_data="menu_promo")],
        [InlineKeyboardButton("🤝 Hamkorlar", callback_data="menu_partners"),
         InlineKeyboardButton("📌 Biz haqimizda", callback_data="menu_about")],
        [InlineKeyboardButton("📞 Admin bilan bog'lanish", callback_data="menu_contact"),
         InlineKeyboardButton("⚠️ Shikoyat / Taklif", callback_data="menu_complaint")],
        [InlineKeyboardButton("💡 Taklif qilish", callback_data="menu_referral"),
         InlineKeyboardButton("💳 To'lov tizimi", callback_data="menu_payment")]
    ]
    if update.callback_query:
        update.callback_query.edit_message_text("🏠 Bosh menyu", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        update.message.reply_text("🏠 Bosh menyu", reply_markup=InlineKeyboardMarkup(keyboard))

# =======================
# RUN BOT
# =======================
def main():
    init_db()
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(callback_handler))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
  # =======================
# ORDER / BUYURTMA BOSHQARISH
# =======================
from telegram.ext import ConversationHandler

ORDER_ITEMS, ORDER_NAME, ORDER_PHONE, ORDER_ADDRESS = range(4)

def order_start(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        "📝 Mahsulotlar ro'yxatini yozing:\n"
        "Masalan: 2 kg kartoshka, 1 kg piyoz, 3 dona banan\n\n"
        "[⬅️ Orqaga]", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]])
    )
    return ORDER_ITEMS

def order_items(update: Update, context: CallbackContext):
    context.user_data['items'] = update.message.text
    keyboard = [
        [KeyboardButton("✍️ Ism yozish"), KeyboardButton("📱 Profilni yuborish", request_contact=True)]
    ]
    update.message.reply_text("👤 Ismingizni kiriting yoki profilni yuboring:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True))
    return ORDER_NAME

def order_name(update: Update, context: CallbackContext):
    if update.message.contact:
        context.user_data['phone'] = update.message.contact.phone_number
        context.user_data['name'] = update.message.contact.first_name
    else:
        context.user_data['name'] = update.message.text
    keyboard = [
        [KeyboardButton("📱 Profilni yuborish", request_contact=True)]
    ]
    update.message.reply_text("📞 Telefon raqamingizni kiriting:\nFormat: +998901234567", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True))
    return ORDER_PHONE

def order_phone(update: Update, context: CallbackContext):
    if update.message.contact:
        context.user_data['phone'] = update.message.contact.phone_number
    else:
        context.user_data['phone'] = update.message.text
    update.message.reply_text("📍 Manzilingizni kiriting:\nMasalan: Chalmagadoy qishlog'i, Paynet ro'parasi", reply_markup=ReplyKeyboardMarkup([[]], remove_keyboard=True))
    return ORDER_ADDRESS

def order_address(update: Update, context: CallbackContext):
    context.user_data['address'] = update.message.text
    user_id = update.message.from_user.id
    with get_db() as conn:
        conn.execute(
            "INSERT INTO orders (user_id, items, status, created_at) VALUES (?, ?, 'yangi', ?)",
            (user_id, context.user_data['items'], datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        order_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    # Admin ga xabar
    context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"🆕 YANGI BUYURTMA!\n\n👤 Ism: {context.user_data['name']}\n📞 Tel: {context.user_data['phone']}\n📍 Manzil: {context.user_data['address']}\n🆔 ID: {user_id}\n📦 Mahsulotlar: {context.user_data['items']}\n🔢 Buyurtma №: {order_id}\n🔗 Profil: tg://user?id={user_id}"
    )
    # Mijozga xabar
    update.message.reply_text("✅ Buyurtmangiz qabul qilindi!\nTez orada admin siz bilan bog'lanadi.\n\n<i>Yoriyev Market tomonidan sizga rahmat!</i>\n\n[🏠 Bosh menyu]", parse_mode='HTML', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]]))
    return ConversationHandler.END

# =======================
# Shikoyat / Taklif
# =======================
COMPLAINT, SUGGESTION = range(2)

def complaint_start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("⚠️ Shikoyat", callback_data="complaint_text")],
        [InlineKeyboardButton("💡 Taklif", callback_data="suggestion_text")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ]
    update.callback_query.edit_message_text("📝 Shikoyat yoki taklif?", reply_markup=InlineKeyboardMarkup(keyboard))

def complaint_text(update: Update, context: CallbackContext):
    update.callback_query.edit_message_text("⚠️ Shikoyatingizni yozing:")
    return COMPLAINT

def suggestion_text(update: Update, context: CallbackContext):
    update.callback_query.edit_message_text("💡 Taklifingizni yozing:")
    return SUGGESTION

def save_complaint(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    text = update.message.text
    with get_db() as conn:
        conn.execute("INSERT INTO complaints (user_id, text, type, created_at) VALUES (?, ?, 'shikoyat', ?)", (user_id, text, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    # Admin ga xabar
    context.bot.send_message(ADMIN_ID, f"⚠️ Yangi shikoyat:\n👤 ID: {user_id}\n🔗 tg://user?id={user_id}\n📝 {text}")
    update.message.reply_text("✅ Shikoyatingiz qabul qilindi!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]]))
    return ConversationHandler.END

# =======================
# Referral bo'limi
# =======================
def referral(update: Update, context: CallbackContext):
    user_id = update.callback_query.from_user.id
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (user_id,)).fetchone()[0]
        discount = conn.execute("SELECT discount_count FROM users WHERE user_id=?", (user_id,)).fetchone()[0]
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    update.callback_query.edit_message_text(f"💡 Taklif qilish tizimi\n\nDo'stlaringizni taklif qiling va chegirmalar oling!\n\n🔗 Sizning havolangiz: {ref_link}\nTaklif qilganlaringiz: {count}\nChegirmalaringiz: {discount}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]))

# =======================
# AKSIYALAR BO'LIMI
# =======================
def promo(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    with get_db() as conn:
        promo_data = conn.execute("SELECT text FROM promotions WHERE id=1").fetchone()
        text = promo_data['text'] if promo_data else "Aksiyalar mavjud emas."
    query.edit_message_text(
        f"📢 Aksiyalar\n\n{text}\n\n👉 @yoriyev_market",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Kanalga o'tish", url="https://t.me/yoriyev_market")],
            [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
        ])
    )

# =======================
# HAMKORLAR BO'LIMI
# =======================
def partners(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        "🤝 Hamkorlarimiz\n\nBiz bilan hamkorlik qilayotgan tashkilotlar:\n👉 https://t.me/hamkorlarimiz_yoriyev_market",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Kanalga o'tish", url="https://t.me/yoriyev_market")],
            [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
        ])
    )

# =======================
# BIZ HAQIMIZDA BO'LIMI
# =======================
def about(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        "📌 Biz haqimizda\n\nYoriyev Market – Peshku tumanidagi eng arzon va sifatli meva-sabzavotlar yetkazib berish xizmati.\n\nManzil: Buxoro, Peshku, Chalmagadoy qishlog'i (Paynet ro'parasi)\nTelefon: +998883822500\n\n👉 https://t.me/biz_haqimizda_yoriyev_market",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Kanalga o'tish", url="https://t.me/yoriyev_market")],
            [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
        ])
    )

# =======================
# ADMIN BILAN BOG'LANISH
# =======================
def contact_admin(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        "📞 Admin bilan bog'lanish\n\nAdmin: @akmalyoriyev\n\nQuyidagi tugmalar orqali bog'lanishingiz mumkin:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("👤 Admin profili", url="https://t.me/akmalyoriyev")],
            [InlineKeyboardButton("📞 Telefon raqam", callback_data="show_phone")],
            [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
        ])
    )

def show_admin_phone(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        "📞 Admin telefon raqami: +998883822500\n\n[⬅️ Orqaga]",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_contact")]])
    )

# =======================
# TO'LOV TIZIMI BO'LIMI
# =======================
def payment(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        "💳 To'lov tizimi\n\nMahsulot sizga yoqsa, keyin to'lov qilasiz.\nBuyurtma berish jarayonida to'lov haqida admin bilan kelishasiz.\n\n💡 To'lov usullari: naqd, Click, Payme, Apelsin.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]])
    )
  # =======================
# ADMIN PANEL
# =======================
def admin_panel(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if str(user_id) != ADMIN_ID:
        update.message.reply_text("❌ Siz admin emassiz!")
        return
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton("📦 Yangi buyurtmalar", callback_data="admin_orders")],
        [InlineKeyboardButton("⚠️ Shikoyatlar", callback_data="admin_complaints")],
        [InlineKeyboardButton("💡 Takliflar", callback_data="admin_suggestions")],
        [InlineKeyboardButton("📢 Aksiyani tahrirlash", callback_data="admin_edit_promo")],
        [InlineKeyboardButton("📤 Xabar yuborish", callback_data="admin_broadcast")],
        [InlineKeyboardButton("⬅️ Yopish", callback_data="main_menu")]
    ])
    update.message.reply_text("🛠 Admin panelga xush kelibsiz:", reply_markup=keyboard)

# =======================
# STATISTIKA
# =======================
def admin_stats(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    with get_db() as conn:
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        new_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE status='yangi'").fetchone()[0]
        today = datetime.now().strftime("%Y-%m-%d")
        today_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE DATE(created_at)=?", (today,)).fetchone()[0]
        complaints = conn.execute("SELECT COUNT(*) FROM complaints WHERE type='shikoyat'").fetchone()[0]
        suggestions = conn.execute("SELECT COUNT(*) FROM complaints WHERE type='taklif'").fetchone()[0]
    text = (f"📊 Statistika\n\n"
            f"👥 Jami foydalanuvchilar: {users}\n"
            f"🆕 Yangi buyurtmalar: {new_orders}\n"
            f"📅 Bugungi buyurtmalar: {today_orders}\n"
            f"⚠️ Shikoyatlar: {complaints}\n"
            f"💡 Takliflar: {suggestions}")
    query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]))

# =======================
# YANGI BUYURTMALAR
# =======================
def admin_orders(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    with get_db() as conn:
        orders = conn.execute("SELECT * FROM orders WHERE status='yangi'").fetchall()
    if not orders:
        text = "📦 Yangi buyurtmalar mavjud emas."
    else:
        text = "📦 Yangi buyurtmalar:\n"
        for o in orders:
            text += (f"\nID: {o['id']}\nFoydalanuvchi ID: {o['user_id']}\n"
                     f"Mahsulotlar: {o['items']}\nHolat: {o['status']}\n"
                     f"Sana: {o['created_at']}\n")
    query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]))

# =======================
# SHIKOYAT / TAKLIF
# =======================
def admin_complaints(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    with get_db() as conn:
        complaints = conn.execute("SELECT * FROM complaints WHERE type='shikoyat' ORDER BY created_at DESC LIMIT 10").fetchall()
    if not complaints:
        text = "⚠️ Shikoyatlar mavjud emas."
    else:
        text = "⚠️ Oxirgi 10 shikoyat:\n"
        for c in complaints:
            text += f"\nID: {c['id']} | User ID: {c['user_id']}\n{x['text']}\n"
    query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]))

def admin_suggestions(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    with get_db() as conn:
        suggestions = conn.execute("SELECT * FROM complaints WHERE type='taklif' ORDER BY created_at DESC LIMIT 10").fetchall()
    if not suggestions:
        text = "💡 Takliflar mavjud emas."
    else:
        text = "💡 Oxirgi 10 taklif:\n"
        for s in suggestions:
            text += f"\nID: {s['id']} | User ID: {s['user_id']}\n{s['text']}\n"
    query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]))

# =======================
# AKSIYANI TAHRIRLASH
# =======================
def admin_edit_promo(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text("📢 Yangi aksiyani yozing:")
    return "EDIT_PROMO"

def save_promo(update: Update, context: CallbackContext):
    new_text = update.message.text
    with get_db() as conn:
        conn.execute("UPDATE promotions SET text=? WHERE id=1", (new_text,))
    update.message.reply_text("✅ Aksiya yangilandi!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]))
    return ConversationHandler.END

# =======================
# BROADCAST XABAR
# =======================
def admin_broadcast(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text("📤 Yuboriladigan xabar matnini yozing:")
    return "BROADCAST"

def send_broadcast(update: Update, context: CallbackContext):
    text = update.message.text
    with get_db() as conn:
        users = conn.execute("SELECT user_id FROM users").fetchall()
    for u in users:
        try:
            context.bot.send_message(u['user_id'], text)
        except Exception as e:
            print(f"Xatolik {u['user_id']} ga yuborishda: {e}")
    update.message.reply_text("✅ Xabar barcha foydalanuvchilarga yuborildi!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]))
    return ConversationHandler.END
  # =======================
# REFERRAL / TAKLIF TIZIMI
# =======================
def start(update: Update, context: CallbackContext):
    user = update.effective_user
    args = context.args
    referred_by = None

    # Agar referral havolasi bo'lsa, id olish
    if args and args[0].startswith("ref_"):
        referred_by = int(args[0].split("_")[1])

    with get_db() as conn:
        # Foydalanuvchini ro'yxatdan o'tkazish
        user_exists = conn.execute("SELECT * FROM users WHERE user_id=?", (user.id,)).fetchone()
        if not user_exists:
            conn.execute(
                "INSERT INTO users (user_id, first_name, username, referred_by, registered_at) VALUES (?, ?, ?, ?, ?)",
                (user.id, user.first_name, user.username, referred_by, datetime.now())
            )

    # Kanal a'zoligini tekshirish
    check_membership(update, context)

def referral_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = update.effective_user.id
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (user_id,)).fetchone()[0]
        discount = conn.execute("SELECT discount_count FROM users WHERE user_id=?", (user_id,)).fetchone()[0]

    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"

    text = (f"💡 Taklif qilish tizimi\n\n"
            f"Do'stlaringizni taklif qiling va chegirmalar oling!\n\n"
            f"🔗 Sizning havolangiz:\n{ref_link}\n\n"
            f"Taklif qilganlaringiz: {count}\n"
            f"Chegirmalaringiz: {discount}")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ])
    query.edit_message_text(text, reply_markup=keyboard)

def apply_referral_discount(new_user_id):
    with get_db() as conn:
        # Yangi foydalanuvchi ma'lumotlari
        new_user = conn.execute("SELECT * FROM users WHERE user_id=?", (new_user_id,)).fetchone()
        if new_user and new_user['referred_by']:
            referrer_id = new_user['referred_by']

            # Faqat birinchi buyurtma qilinganda
            total_orders = new_user['total_orders']
            if total_orders == 1:
                # Taklif qilgan foydalanuvchi chegirmasini oshirish
                conn.execute("UPDATE users SET discount_count = discount_count + 1 WHERE user_id=?", (referrer_id,))
                # Yangi foydalanuvchiga ham chegirma
                conn.execute("UPDATE users SET discount_count = discount_count + 1 WHERE user_id=?", (new_user_id,))
                return referrer_id
    return None

def notify_referrer(bot, referrer_id, new_user_id):
    if referrer_id:
        try:
            bot.send_message(referrer_id,
                             f"🎉 Siz taklif qilgan do'stingiz birinchi buyurtmasini berdi!\n"
                             f"Endi siz chegirmaga ega bo'ldingiz.")
        except Exception as e:
            print(f"Xatolik: referrer notify {referrer_id} - {e}")
          # =======================
# TO'LOV TIZIMI / CHECKOUT
# =======================
def payment_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    text = ("💳 To'lov tizimi\n\n"
            "Mahsulot sizga yoqsa, keyin to'lov qilasiz.\n"
            "Buyurtma berish jarayonida to'lov haqida admin bilan kelishasiz.\n\n"
            "💡 To'lov usullari: naqd, Click, Payme, Apelsin.")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ])
    query.edit_message_text(text, reply_markup=keyboard)

# Checkout: Buyurtma tasdiqlash va adminga yuborish
def finalize_order(update: Update, context: CallbackContext, items, name, phone, address):
    user_id = update.effective_user.id
    created_at = datetime.now()
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO orders (user_id, items, status, created_at) VALUES (?, ?, 'yangi', ?)",
            (user_id, items, created_at)
        )
        order_id = cursor.lastrowid

    # Adminga buyurtma xabari
    admins = [ADMIN_ID_1, ADMIN_ID_2]  # Admin IDlar ro'yxati
    for admin in admins:
        try:
            context.bot.send_message(
                admin,
                f"🆕 YANGI BUYURTMA!\n\n"
                f"👤 Ism: {name}\n"
                f"📞 Tel: {phone}\n"
                f"📍 Manzil: {address}\n"
                f"🆔 ID: {user_id}\n"
                f"🔗 Profil: tg://user?id={user_id}\n"
                f"📦 Mahsulotlar: {items}\n"
                f"🔢 Buyurtma №: {order_id}"
            )
        except Exception as e:
            print(f"Xatolik: admin notify {admin} - {e}")

    # Foydalanuvchiga tasdiq
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
    ])
    update.message.reply_text(
        "✅ Buyurtmangiz qabul qilindi!\n\n"
        "Tez orada admin siz bilan bog'lanadi.\n\n"
        "<i>Yoriyev Market tomonidan sizga rahmat!</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard
    )

    # Referral chegirmalarini qo‘llash
    referrer_id = apply_referral_discount(user_id)
    if referrer_id:
        notify_referrer(context.bot, referrer_id, user_id)
      # =======================
# ADMIN PANEL
# =======================
def admin_panel(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id not in [ADMIN_ID_1, ADMIN_ID_2]:
        update.message.reply_text("❌ Siz admin emassiz!")
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton("📦 Yangi buyurtmalar", callback_data="admin_new_orders")],
        [InlineKeyboardButton("⚠️ Shikoyatlar", callback_data="admin_complaints")],
        [InlineKeyboardButton("💡 Takliflar", callback_data="admin_suggestions")],
        [InlineKeyboardButton("📢 Aksiyani tahrirlash", callback_data="admin_edit_promo")],
        [InlineKeyboardButton("📤 Xabar yuborish", callback_data="admin_broadcast")],
        [InlineKeyboardButton("⬅️ Bosh menyu", callback_data="main_menu")]
    ])
    update.message.reply_text("⚙️ Admin panelga xush kelibsiz!", reply_markup=keyboard)

# Statistika
def admin_stats(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    with get_db() as conn:
        cursor = conn.cursor()
        users = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        new_orders = cursor.execute("SELECT COUNT(*) FROM orders WHERE status='yangi'").fetchone()[0]
        today_orders = cursor.execute(
            "SELECT COUNT(*) FROM orders WHERE date(created_at)=date('now','localtime')"
        ).fetchone()[0]
        complaints = cursor.execute("SELECT COUNT(*) FROM complaints WHERE type='shikoyat'").fetchone()[0]
        suggestions = cursor.execute("SELECT COUNT(*) FROM complaints WHERE type='taklif'").fetchone()[0]

    text = (f"📊 Statistika\n\n"
            f"👥 Jami foydalanuvchilar: {users}\n"
            f"🆕 Yangi buyurtmalar: {new_orders}\n"
            f"📅 Bugungi buyurtmalar: {today_orders}\n"
            f"⚠️ Shikoyatlar: {complaints}\n"
            f"💡 Takliflar: {suggestions}")

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")]])
    query.edit_message_text(text, reply_markup=keyboard)

# Yangi buyurtmalar ro'yxati
def admin_new_orders(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    with get_db() as conn:
        cursor = conn.cursor()
        orders = cursor.execute(
            "SELECT * FROM orders WHERE status='yangi' ORDER BY created_at DESC"
        ).fetchall()

    if not orders:
        text = "📦 Yangi buyurtmalar mavjud emas."
    else:
        text = "📦 Yangi buyurtmalar:\n\n"
        for o in orders:
            text += (f"🆔 Buyurtma #{o['id']}\n"
                     f"👤 ID: {o['user_id']}\n"
                     f"📦 Mahsulotlar: {o['items']}\n"
                     f"🕒 Sana: {o['created_at']}\n\n")

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")]])
    query.edit_message_text(text, reply_markup=keyboard)

# Shikoyatlar / Takliflar
def admin_complaints(update: Update, context: CallbackContext, type_filter='shikoyat'):
    query = update.callback_query
    query.answer()
    with get_db() as conn:
        cursor = conn.cursor()
        complaints = cursor.execute(
            "SELECT * FROM complaints WHERE type=? ORDER BY created_at DESC LIMIT 10", (type_filter,)
        ).fetchall()

    if not complaints:
        text = f"⚠️ {type_filter.title()}lar mavjud emas."
    else:
        text = f"⚠️ Oxirgi 10 ta {type_filter}:\n\n"
        for c in complaints:
            text += (f"👤 ID: {c['user_id']}\n"
                     f"📝 {c['text']}\n"
                     f"🕒 {c['created_at']}\n\n")

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")]])
    query.edit_message_text(text, reply_markup=keyboard)

# Aksiyani tahrirlash
def admin_edit_promo(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    context.user_data['edit_promo'] = True
    query.edit_message_text("📢 Yangi aksiya matnini kiriting:")

# Xabar yuborish (broadcast)
def admin_broadcast(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    context.user_data['broadcast'] = True
    query.edit_message_text("📤 Barcha foydalanuvchilarga yuborish uchun matn kiriting:")
  # =======================
# REFERRAL (Taklif qilish) VA BUYURTMALAR
# =======================

def handle_start(update: Update, context: CallbackContext):
    """/start handler, referral logikasini tekshiradi"""
    user = update.effective_user
    args = context.args
    referred_by = None

    if args and args[0].startswith("ref_"):
        try:
            referred_by = int(args[0].split("_")[1])
        except ValueError:
            referred_by = None

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, first_name, username, registered_at, referred_by) "
            "VALUES (?, ?, ?, datetime('now','localtime'), ?)",
            (user.id, user.first_name, user.username, referred_by)
        )
        conn.commit()

    # /start tugmasi yoki referral orqali boshlanganda
    send_main_menu(update, context)

def referral_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = update.effective_user.id
    with get_db() as conn:
        cursor = conn.cursor()
        count = cursor.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (user_id,)).fetchone()[0]
        discount = cursor.execute("SELECT discount_count FROM users WHERE user_id=?", (user_id,)).fetchone()[0]

    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"

    text = (f"💡 Taklif qilish tizimi\n\n"
            f"Do'stlaringizni taklif qiling va chegirmalar oling!\n\n"
            f"1️⃣ Havolani do'stingizga yuboring\n"
            f"2️⃣ Do'stingiz birinchi buyurtma bersa, siz va do'stingiz 1 tadan chegirma olasiz\n\n"
            f"🔗 Sizning havolangiz:\n{ref_link}\n\n"
            f"Taklif qilganlaringiz: {count}\n"
            f"Chegirmalaringiz: {discount}")

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]])
    query.edit_message_text(text, reply_markup=keyboard)

# Buyurtmani yakunlash va adminga xabar berish
def finalize_order(update: Update, context: CallbackContext, user_data):
    """Buyurtma barcha bosqichlarini yakunlaydi va adminga yuboradi"""
    user = update.effective_user
    items = user_data.get('items')
    name = user_data.get('name')
    phone = user_data.get('phone')
    address = user_data.get('address')

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO orders (user_id, items, status, created_at) VALUES (?, ?, 'yangi', datetime('now','localtime'))",
            (user.id, items)
        )
        order_id = cursor.lastrowid
        conn.commit()

    # Adminlarga xabar yuborish
    admin_text = (f"🆕 YANGI BUYURTMA!\n\n"
                  f"👤 Ism: {name}\n"
                  f"📞 Tel: {phone}\n"
                  f"📍 Manzil: {address}\n"
                  f"🆔 ID: {user.id}\n"
                  f"🔗 Profil: tg://user?id={user.id}\n"
                  f"📦 Mahsulotlar: {items}\n"
                  f"🔢 Buyurtma №: {order_id}")

    for admin_id in [ADMIN_ID_1, ADMIN_ID_2]:
        context.bot.send_message(chat_id=admin_id, text=admin_text)

    # Mijozga tasdiq
    text = ("✅ Buyurtmangiz qabul qilindi!\n\n"
            "Tez orada admin siz bilan bog'lanadi.\n\n"
            "<i>Yoriyev Market tomonidan sizga rahmat!</i>")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]])
    update.effective_message.reply_text(text, reply_markup=keyboard, parse_mode='HTML')

    # Referral logikasi: birinchi buyurtma uchun
    with get_db() as conn:
        cursor = conn.cursor()
        total_orders = cursor.execute("SELECT total_orders FROM users WHERE user_id=?", (user.id,)).fetchone()[0]
        if total_orders == 0 and user_data.get('referred_by'):
            referred_id = user_data.get('referred_by')
            # Chegirma sonini oshirish
            cursor.execute("UPDATE users SET discount_count=discount_count+1 WHERE user_id=?", (referred_id,))
            cursor.execute("UPDATE users SET discount_count=discount_count+1 WHERE user_id=?", (user.id,))
            conn.commit()
            # Taklif qilgan do‘stga xabar
            context.bot.send_message(chat_id=referred_id,
                                     text="🎉 Siz taklif qilgan do'stingiz birinchi buyurtmasini berdi! "
                                          "Endi siz chegirmaga ega bo'ldingiz.")
        # Buyurtma sonini oshirish
        cursor.execute("UPDATE users SET total_orders=total_orders+1 WHERE user_id=?", (user.id,))
        conn.commit()
      # =======================
# SHIKOYAT / TAKLIF VA ADMIN BO'LIMI
# =======================

def complaint_menu(update: Update, context: CallbackContext):
    """⚠️ Shikoyat yoki taklif bo'limi"""
    query = update.callback_query
    query.answer()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚠️ Shikoyat", callback_data="complaint")],
        [InlineKeyboardButton("💡 Taklif", callback_data="suggestion")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ])
    query.edit_message_text("📝 Shikoyat yoki taklif?", reply_markup=keyboard)

def handle_complaint(update: Update, context: CallbackContext):
    """Shikoyat matnini qabul qiladi"""
    user = update.effective_user
    text = update.message.text
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO complaints (user_id, text, type, created_at) VALUES (?, ?, 'shikoyat', datetime('now','localtime'))",
            (user.id, text)
        )
        conn.commit()

    # Adminlarga xabar
    admin_text = f"⚠️ Yangi shikoyat:\n👤 ID: {user.id}\n🔗 tg://user?id={user.id}\n📝 {text}"
    for admin_id in [ADMIN_ID_1, ADMIN_ID_2]:
        context.bot.send_message(chat_id=admin_id, text=admin_text)

    # Foydalanuvchiga tasdiq
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]])
    update.message.reply_text("✅ Shikoyatingiz qabul qilindi!", reply_markup=keyboard)

def handle_suggestion(update: Update, context: CallbackContext):
    """Taklif matnini qabul qiladi"""
    user = update.effective_user
    text = update.message.text
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO complaints (user_id, text, type, created_at) VALUES (?, ?, 'taklif', datetime('now','localtime'))",
            (user.id, text)
        )
        conn.commit()

    # Adminlarga xabar
    admin_text = f"💡 Yangi taklif:\n👤 ID: {user.id}\n🔗 tg://user?id={user.id}\n📝 {text}"
    for admin_id in [ADMIN_ID_1, ADMIN_ID_2]:
        context.bot.send_message(chat_id=admin_id, text=admin_text)

    # Foydalanuvchiga tasdiq
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]])
    update.message.reply_text("✅ Taklifingiz qabul qilindi!", reply_markup=keyboard)

# =======================
# ADMIN BILAN BOG'LANISH
# =======================
def contact_admin(update: Update, context: CallbackContext):
    """Admin bilan bog'lanish bo'limi"""
    query = update.callback_query
    query.answer()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Admin profili", url=f"https://t.me/{ADMIN_USERNAME}")],
        [InlineKeyboardButton("📞 Telefon raqam", callback_data="show_phone")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ])
    query.edit_message_text("📞 Admin bilan bog'lanish\n\nAdmin bilan quyidagi yo'llar orqali bog'lanishingiz mumkin:", reply_markup=keyboard)

def show_admin_phone(update: Update, context: CallbackContext):
    """Admin telefon raqamini ko'rsatadi"""
    query = update.callback_query
    query.answer()
    text = f"📞 Admin telefon raqami: {ADMIN_PHONE_1}\n📞 Qo‘shimcha telefon: {ADMIN_PHONE_2}"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_contact")]])
    query.edit_message_text(text, reply_markup=keyboard)
  # =======================
# AKSIYALAR BO'LIMI
# =======================
def promotions_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    with get_db() as conn:
        promo = conn.execute("SELECT text FROM promotions WHERE id=1").fetchone()
        text = promo['text'] if promo else "📢 Hozirda aksiyalar mavjud emas."

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL_USERNAME}")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ])
    query.edit_message_text(f"📢 Aksiyalar\n\n{text}\n\n👉 @{CHANNEL_USERNAME}", reply_markup=keyboard)


# =======================
# HAMKORLAR BO'LIMI
# =======================
def partners_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Kanalga o'tish", url="https://t.me/hamkorlarimiz_yoriyev_market")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ])
    query.edit_message_text(
        "🤝 Hamkorlarimiz\n\nBiz bilan hamkorlik qilayotgan tashkilotlar:\n👉 https://t.me/hamkorlarimiz_yoriyev_market",
        reply_markup=keyboard
    )


# =======================
# BIZ HAQIMIZDA BO'LIMI
# =======================
def about_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    text = (
        "📌 Biz haqimizda\n\n"
        "Yoriyev Market – Peshku tumanidagi eng arzon va sifatli meva-sabzavotlar yetkazib berish xizmati.\n\n"
        "Manzil: Buxoro, Peshku, Chalmagadoy qishlog'i (Paynet ro'parasi)\n"
        f"Telefon: {ADMIN_PHONE_1}\n\n"
        "👉 Bizning kanal: https://t.me/biz_haqimizda_yoriyev_market"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Kanalga o'tish", url="https://t.me/biz_haqimizda_yoriyev_market")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ])
    query.edit_message_text(text, reply_markup=keyboard)
  # =======================
# TAKLIF QILISH (REFERRAL) BO'LIMI
# =======================
def referral_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id

    with get_db() as conn:
        # Taklif qilingan foydalanuvchilar soni
        count = conn.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (user_id,)).fetchone()[0]
        # Mavjud chegirmalar soni
        discount = conn.execute("SELECT discount_count FROM users WHERE user_id=?", (user_id,)).fetchone()[0]

    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"

    text = (
        "💡 Taklif qilish tizimi\n\n"
        "Do'stlaringizni taklif qiling va chegirmalar oling!\n\n"
        "Qanday ishlaydi:\n"
        "1. Havolani do'stingizga yuboring\n"
        "2. Do'stingiz birinchi buyurtma bersa\n"
        "3. Siz va do'stingiz 1 tadan chegirma olasiz\n\n"
        f"🔗 Sizning havolangiz: {ref_link}\n\n"
        f"Taklif qilganlaringiz: {count}\n"
        f"Chegirmalaringiz: {discount}"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ])

    query.edit_message_text(text, reply_markup=keyboard)


# =======================
# REFERRAL LOGIKASI
# =======================
def handle_start(update: Update, context: CallbackContext):
    user = update.effective_user
    user_id = user.id
    first_name = user.first_name
    username = user.username

    args = context.args
    referred_by = None
    if args and args[0].startswith("ref_"):
        try:
            referred_by = int(args[0].split("_")[1])
        except:
            referred_by = None

    with get_db() as conn:
        # Foydalanuvchini saqlash
        existing = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO users (user_id, first_name, username, registered_at, referred_by) VALUES (?, ?, ?, ?, ?)",
                (user_id, first_name, username, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), referred_by)
            )

    # Agar foydalanuvchi referral orqali kelgan bo'lsa, referral_count +1 qilinadi faqat birinchi buyurtmada
    # Bu logika buyurtma berish qismida qo‘shiladi (orders bo‘limida)
  # =======================
# TO'LOV TIZIMI BO'LIMI
# =======================
def payment_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    text = (
        "💳 To'lov tizimi\n\n"
        "Mahsulot sizga yoqsa, keyin to'lov qilasiz.\n"
        "Buyurtma berish jarayonida to'lov haqida admin bilan kelishasiz.\n\n"
        "💡 To'lov usullari: Naqd, Click, Payme, Apelsin."
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📞 Admin bilan bog‘lanish", callback_data="menu_contact")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ])

    query.edit_message_text(text, reply_markup=keyboard)


# =======================
# ADMIN BILAN BOG'LANISH BO'LIMI
# =======================
def contact_admin(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    text = (
        "📞 Admin bilan bog‘lanish\n\n"
        "Admin: @yoriyev_market\n"
        "Telefon raqamlar:\n"
        "+998883822500\n"
        "+998883092500\n\n"
        "Quyidagi tugmalar orqali bog'lanishingiz mumkin:"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Admin profili", url="https://t.me/yoriyev_market")],
        [InlineKeyboardButton("📞 Telefon raqamni ko‘rsatish", callback_data="show_phone")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ])

    query.edit_message_text(text, reply_markup=keyboard)


# =======================
# TELEFON RAQAMNI KO'RISH
# =======================
def show_phone(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    text = "📞 Admin telefon raqami: +998883822500"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_contact")]
    ])

    query.edit_message_text(text, reply_markup=keyboard)
  # =======================
# SHIKOYAT / TAKLIF BO'LIMI
# =======================
def complaint_suggestion_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    text = (
        "📝 Shikoyat yoki taklif?\n\n"
        "Quyidagi tugmalardan birini tanlang:"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚠️ Shikoyat", callback_data="complaint")],
        [InlineKeyboardButton("💡 Taklif", callback_data="suggestion")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ])

    query.edit_message_text(text, reply_markup=keyboard)


# =======================
# SHIKOYAT YUBORISH
# =======================
def write_complaint(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    context.user_data['complaint_type'] = 'shikoyat'

    text = "⚠️ Shikoyatingizni yozing:\n\n[⬅️ Bekor qilish]"
    query.edit_message_text(text)

    return 'WAITING_COMPLAINT_TEXT'


# =======================
# TAKLIF YUBORISH
# =======================
def write_suggestion(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    context.user_data['complaint_type'] = 'taklif'

    text = "💡 Taklifingizni yozing:\n\n[⬅️ Bekor qilish]"
    query.edit_message_text(text)

    return 'WAITING_COMPLAINT_TEXT'


# =======================
# FOYDALANUVCHI MATNINI QABUL QILISH
# =======================
def receive_complaint_text(update: Update, context: CallbackContext):
    user = update.message.from_user
    text = update.message.text
    complaint_type = context.user_data.get('complaint_type', 'shikoyat')

    if text.lower() == '⬅️ bekor qilish':
        update.message.reply_text("✅ Bekor qilindi.", reply_markup=main_menu_keyboard())
        return ConversationHandler.END

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Ma'lumotlar bazasiga saqlash
    with get_db() as conn:
        conn.execute(
            "INSERT INTO complaints (user_id, text, type, created_at) VALUES (?, ?, ?, ?)",
            (user.id, text, complaint_type, created_at)
        )

    # Adminga xabar
    context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"⚠️ Yangi {complaint_type}:\n"
             f"👤 ID: {user.id}\n"
             f"🔗 Profil: tg://user?id={user.id}\n"
             f"📝 {text}"
    )

    update.message.reply_text(
        "✅ Xabaringiz qabul qilindi!\n\n"
        "[🏠 Bosh menyu]",
        reply_markup=main_menu_keyboard()
    )

    return ConversationHandler.END
  import logging
import sqlite3
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Updater, CommandHandler, CallbackQueryHandler,
    MessageHandler, Filters, CallbackContext, ConversationHandler
)
import os
from datetime import datetime

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN", "8743932506:AAFKE1rUE8PkemE-dNgwYYdDUdjzgnSNDBs")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@yoriyev_market")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7887637727"))
BOT_USERNAME = os.getenv("BOT_USERNAME", "@yoriyev_market_bot")
ADMIN_PHONE = os.getenv("ADMIN_PHONE", "+998883822500")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "@akmalyoriyev")

# Conversation states
PRODUCTS, NAME, PHONE, ADDRESS = range(4)

# Database helper
def get_db():
    conn = sqlite3.connect("yoriyev_market.db")
    conn.row_factory = sqlite3.Row
    return conn

# Initialize tables
def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users(
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                items TEXT,
                status TEXT DEFAULT 'yangi',
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS complaints(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                text TEXT,
                type TEXT,
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS promotions(
                id INTEGER PRIMARY KEY CHECK (id=1),
                text TEXT
            )
        """)

# Helper: go back to main menu
def main_menu_keyboard():
    buttons = [
        [InlineKeyboardButton("🛒 Mahsulotlar", callback_data="menu_products")],
        [InlineKeyboardButton("📢 Aksiyalar", callback_data="menu_promo")],
        [InlineKeyboardButton("🤝 Hamkorlar", callback_data="menu_partners")],
        [InlineKeyboardButton("📌 Biz haqimizda", callback_data="menu_about")],
        [InlineKeyboardButton("📞 Admin bilan bog'lanish", callback_data="menu_contact")],
        [InlineKeyboardButton("⚠️ Shikoyat / Taklif", callback_data="menu_complaint")],
        [InlineKeyboardButton("💡 Taklif qilish", callback_data="menu_referral")],
        [InlineKeyboardButton("💳 To'lov tizimi", callback_data="menu_payment")]
    ]
    return InlineKeyboardMarkup(buttons)

def back_button():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ])
  # /start handler
def start(update: Update, context: CallbackContext):
    user = update.effective_user
    chat_id = update.effective_chat.id

    # Kanalga a'zolik tekshirish
    try:
        member = context.bot.get_chat_member(CHANNEL_USERNAME, chat_id)
        if member.status not in ['member', 'administrator', 'creator']:
            update.message.reply_text(
                f"🌟 Assalomu alaykum {user.first_name}!\n"
                "Botdan foydalanish uchun kanalimizga a'zo bo'ling.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL_USERNAME}")],
                    [InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")]
                ])
            )
            return
    except Exception as e:
        logger.error(f"Kanal tekshiruvi xatosi: {e}")
    
    update.message.reply_text(
        "✅ A'zo bo'lgansiz! Bosh menyuga o'tish:",
        reply_markup=main_menu_keyboard()
    )

# Kanalga a'zolik qayta tekshirish
def check_sub(update: Update, context: CallbackContext):
    query = update.callback_query
    user = update.effective_user
    chat_id = query.message.chat_id
    try:
        member = context.bot.get_chat_member(CHANNEL_USERNAME, chat_id)
        if member.status in ['member', 'administrator', 'creator']:
            query.edit_message_text(
                "✅ A'zo bo'lgansiz! Bosh menyuga o'tish:",
                reply_markup=main_menu_keyboard()
            )
        else:
            query.answer("Siz hali kanalga a'zo bo‘lmadingiz!")
    except Exception as e:
        logger.error(f"Tekshirish xatosi: {e}")
        query.answer("Xatolik yuz berdi, keyinroq urinib ko‘ring.")

# 🛒 Mahsulotlar bo‘limi
def menu_products(update: Update, context: CallbackContext):
    query = update.callback_query
    query.edit_message_text(
        f"🛒 Mahsulotlar\n\nKerakli mahsulotlarni kanaldan tanlang va bizga xabar shaklida yozing.\n\n👉 {CHANNEL_USERNAME}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL_USERNAME}"),
            InlineKeyboardButton("✅ Buyurtma berish", callback_data="order_start")
        ]])
    )

# Buyurtma jarayoni boshlash
def order_start(update: Update, context: CallbackContext):
    query = update.callback_query
    query.edit_message_text(
        "📝 Mahsulotlar ro'yxatini yozing:\n"
        "Masalan: 2 kg kartoshka, 1 kg piyoz, 3 dona banan",
        reply_markup=back_button()
    )
    return PRODUCTS

# Mahsulotlar ro'yxatini qabul qilish
def products_received(update: Update, context: CallbackContext):
    context.user_data['items'] = update.message.text
    # Ism so'rash
    buttons = [[KeyboardButton("✍️ Ism yozish")],
               [KeyboardButton("📱 Profilni yuborish", request_contact=True)]]
    update.message.reply_text(
        "👤 Ismingizni kiriting yoki profilni yuboring:",
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=True)
    )
    return NAME

# Ism yoki kontakt qabul qilish
def name_received(update: Update, context: CallbackContext):
    if update.message.contact:
        context.user_data['first_name'] = update.message.contact.first_name
        context.user_data['phone'] = update.message.contact.phone_number
        update.message.reply_text("📍 Manzilingizni kiriting:", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("⬅️ Orqaga")]], resize_keyboard=True))
        return ADDRESS
    else:
        context.user_data['first_name'] = update.message.text
        update.message.reply_text("📞 Telefon raqamingizni kiriting (Format: +998901234567)", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("📱 Profilni yuborish", request_contact=True)]], resize_keyboard=True))
        return PHONE

# Telefon raqam qabul qilish
def phone_received(update: Update, context: CallbackContext):
    if update.message.contact:
        context.user_data['phone'] = update.message.contact.phone_number
    else:
        context.user_data['phone'] = update.message.text
    update.message.reply_text("📍 Manzilingizni kiriting:\nMasalan: Chalmagadoy qishlog'i, Paynet ro'parasi", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("⬅️ Orqaga")]], resize_keyboard=True))
    return ADDRESS

# Manzil qabul qilish va buyurtma saqlash
def address_received(update: Update, context: CallbackContext):
    context.user_data['address'] = update.message.text
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO orders (user_id, items, status, created_at) VALUES (?, ?, 'yangi', ?)",
                       (update.effective_user.id, context.user_data['items'], now))
        order_id = cursor.lastrowid
    # Adminga xabar
    context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"🆕 YANGI BUYURTMA!\n\n"
             f"👤 Ism: {context.user_data['first_name']}\n"
             f"📞 Tel: {context.user_data['phone']}\n"
             f"📍 Manzil: {context.user_data['address']}\n"
             f"🆔 ID: {update.effective_user.id}\n"
             f"🔗 Profil: tg://user?id={update.effective_user.id}\n"
             f"📦 Mahsulotlar: {context.user_data['items']}\n"
             f"🔢 Buyurtma №: {order_id}"
    )
    update.message.reply_text(
        "✅ Buyurtmangiz qabul qilindi!\n\nTez orada admin siz bilan bog'lanadi.\n\n<i>Yoriyev Market tomonidan sizga rahmat!</i>",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END
  # 📢 Aksiyalar
def menu_promo(update: Update, context: CallbackContext):
    query = update.callback_query
    with get_db() as conn:
        promo = conn.execute("SELECT text FROM promotions WHERE id=1").fetchone()
    text = promo['text'] if promo else "Aksiyalar mavjud emas."
    query.edit_message_text(
        f"📢 Aksiyalar\n\n{text}\n\n👉 {CHANNEL_USERNAME}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL_USERNAME}")],
            [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
        ])
    )

# 🤝 Hamkorlar
def menu_partners(update: Update, context: CallbackContext):
    query = update.callback_query
    query.edit_message_text(
        f"🤝 Hamkorlarimiz\n\nBiz bilan hamkorlik qilayotgan tashkilotlar:\n\n👉 https://t.me/hamkorlarimiz_yoriyev_market",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL_USERNAME}")],
            [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
        ])
    )

# 📌 Biz haqimizda
def menu_about(update: Update, context: CallbackContext):
    query = update.callback_query
    query.edit_message_text(
        f"📌 Biz haqimizda\n\nYoriyev Market – Peshku tumanidagi eng arzon va sifatli meva-sabzavotlar yetkazib berish xizmati.\n\n"
        f"Manzil: Buxoro, Peshku, Chalmagadoy qishlog'i (Paynet ro'parasi)\n"
        f"Telefon: +998883822500\n\n"
        f"👉 https://t.me/biz_haqimizda_yoriyev_market",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL_USERNAME}")],
            [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
        ])
    )

# 📞 Admin bilan bog'lanish
def menu_contact(update: Update, context: CallbackContext):
    query = update.callback_query
    query.edit_message_text(
        f"📞 Admin bilan bog'lanish\n\nAdmin: @yoriyev_market\n\nTugmalar orqali bog'laning:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("👤 Admin profili", url=f"https://t.me/yoriyev_market")],
            [InlineKeyboardButton("📞 Telefon raqam", callback_data="show_phone")],
            [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
        ])
    )

def show_phone(update: Update, context: CallbackContext):
    query = update.callback_query
    query.edit_message_text(
        "📞 Admin telefon raqami: +998883822500",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_contact")]])
    )

# ⚠️ Shikoyat / Taklif
def menu_complaint(update: Update, context: CallbackContext):
    query = update.callback_query
    query.edit_message_text(
        "📝 Shikoyat yoki taklif?\n",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⚠️ Shikoyat", callback_data="complaint")],
            [InlineKeyboardButton("💡 Taklif", callback_data="suggestion")],
            [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
        ])
    )

def complaint_received(update: Update, context: CallbackContext):
    text = update.message.text
    with get_db() as conn:
        conn.execute("INSERT INTO complaints (user_id, text, type, created_at) VALUES (?, ?, 'shikoyat', ?)",
                     (update.effective_user.id, text, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"⚠️ Yangi shikoyat:\n👤 ID: {update.effective_user.id}\n🔗 tg://user?id={update.effective_user.id}\n📝 {text}"
    )
    update.message.reply_text(
        "✅ Shikoyatingiz qabul qilindi!",
        reply_markup=main_menu_keyboard()
    )

def suggestion_received(update: Update, context: CallbackContext):
    text = update.message.text
    with get_db() as conn:
        conn.execute("INSERT INTO complaints (user_id, text, type, created_at) VALUES (?, ?, 'taklif', ?)",
                     (update.effective_user.id, text, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"💡 Yangi taklif:\n👤 ID: {update.effective_user.id}\n🔗 tg://user?id={update.effective_user.id}\n📝 {text}"
    )
    update.message.reply_text(
        "✅ Taklifingiz qabul qilindi!",
        reply_markup=main_menu_keyboard()
    )

# 💡 Referral tizimi
def menu_referral(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = update.effective_user.id
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (user_id,)).fetchone()[0]
        discount = conn.execute("SELECT discount_count FROM users WHERE user_id=?", (user_id,)).fetchone()[0]

    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    query.edit_message_text(
        f"💡 Taklif qilish tizimi\n\nDo'stlaringizni taklif qiling va chegirmalar oling!\n\n"
        f"🔗 Sizning havolangiz: {ref_link}\n"
        f"Taklif qilganlaringiz: {count}\n"
        f"Chegirmalaringiz: {discount}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]])
    )
