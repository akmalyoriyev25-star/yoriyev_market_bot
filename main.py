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

# --- CALLBACK HANDLER (for general menu) ---
def menu_callback_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data

    if data == "menu_products":
        show_products(query, context)
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
    elif data == "complaint":
        context.user_data['complaint_type'] = 'shikoyat'
        query.edit_message_text("⚠️ Shikoyatingizni yozib yuboring:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_complaint")]]))
    elif data == "suggestion":
        context.user_data['complaint_type'] = 'taklif'
        query.edit_message_text("💡 Taklifingizni yozib yuboring:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_complaint")]]))
    query.answer()

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

# --- ORDER FLOW (Conversation handler) ---
def order_start(update: Update, context: CallbackContext):
    query = update.callback_query
    query.edit_message_text("📝 Mahsulotlar ro'yxatini yozing:\nMasalan: 2 kg kartoshka, 1 kg piyoz\n[⬅️ Orqaga]", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]))
    return PRODUCTS

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

# --- COMPLAINT TEXT HANDLER ---
def complaint_text_handler(update: Update, context: CallbackContext):
    if 'complaint_type' in context.user_data:
        ctype = context.user_data['complaint_type']
        text = update.message.text
        user_id = update.message.from_user.id
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO complaints (user_id, text, type, created_at) VALUES (?, ?, ?, ?)",
                  (user_id, text, ctype, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        update.message.reply_text("✅ Fikringiz qabul qilindi. Rahmat!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]]))
        del context.user_data['complaint_type']
    else:
        # Not a complaint, pass to other handlers (or ignore)
        pass

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

# --- MAIN ---
def main():
    init_db()
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Conversation handler for order flow
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(order_start, pattern="^order_start$")],
        states={
            PRODUCTS: [MessageHandler(Filters.text & ~Filters.command, products_input)],
            NAME: [MessageHandler(Filters.text & ~Filters.command | Filters.contact, name_input)],
            PHONE: [MessageHandler(Filters.text & ~Filters.command | Filters.contact, phone_input)],
            ADDRESS: [MessageHandler(Filters.text & ~Filters.command, address_input)],
        },
        fallbacks=[CommandHandler("start", start)]
    )

    # General command handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("admin", admin_panel))

    # Callback handlers
    dp.add_handler(CallbackQueryHandler(menu_callback_handler, pattern="^(?!admin_).*"))  # all non-admin callbacks
    dp.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))  # admin callbacks

    # Conversation handler
    dp.add_handler(conv_handler)

    # Text handlers (order of addition matters)
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, complaint_text_handler))  # complaints/suggestions
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, admin_text_handler))  # admin promo/broadcast

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
