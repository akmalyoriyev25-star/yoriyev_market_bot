import logging
import sqlite3
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ParseMode
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

# --- KONFIGURATSIYA ---
BOT_TOKEN = "8743932506:AAFKE1rUE8PkemE-dNgwYYdDUdjzgnSNDBs"
ADMIN_ID = 7887637727
ADMIN_PHONE = "+998883822500"
CHANNEL = "@yoriyev_market"
BIZ_HAQIMIZDA = "https://t.me/biz_haqimizda_yoriyev_market"
HAMKORLAR = "https://t.me/hamkorlarimiz_yoriyev_market"
BOT_USERNAME = "Yoriyev_market_bot"

# --- LOGGING ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- STATE HOLATLARI ---
(PRODUCTS, NAME, PHONE, ADDRESS, 
 COMPLAINT, SUGGESTION, EDIT_PROMO, BROADCAST) = range(8)

# ======================
# MA'LUMOTLAR BAZASI
# ======================
def init_db():
    conn = sqlite3.connect("yoriyev_market.db")
    c = conn.cursor()
    
    # Foydalanuvchilar
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
    
    # Buyurtmalar
    c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            items TEXT,
            status TEXT DEFAULT 'yangi',
            created_at TEXT
        )
    """)
    
    # Shikoyat/Takliflar
    c.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT,
            type TEXT,
            created_at TEXT
        )
    """)
    
    # Aksiyalar (faqat 1 qator)
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

# ======================
# ASOSIY FUNKSIYALAR
# ======================
def main_menu_keyboard():
    """Bosh menyu tugmalari"""
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
    return InlineKeyboardMarkup(buttons)

def back_button(callback="main_menu"):
    """Orqaga tugmasi"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Orqaga", callback_data=callback)]
    ])

def show_main_menu(update_or_query, context):
    """Bosh menyuni ko'rsatish"""
    if hasattr(update_or_query, "edit_message_text"):
        update_or_query.edit_message_text(
            "🏠 Bosh menyu", 
            reply_markup=main_menu_keyboard()
        )
    else:
        update_or_query.message.reply_text(
            "🏠 Bosh menyu", 
            reply_markup=main_menu_keyboard()
        )

# ======================
# START KOMANDASI
# ======================
def start(update: Update, context: CallbackContext):
    user = update.effective_user
    first_name = user.first_name or "Foydalanuvchi"
    
    # Referral tekshirish
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
    c.execute("SELECT * FROM users WHERE user_id=?", (user.id,))
    row = c.fetchone()
    
    if not row:
        c.execute("""
            INSERT INTO users (user_id, first_name, username, registered_at, referred_by)
            VALUES (?, ?, ?, ?, ?)
        """, (user.id, first_name, user.username, 
              datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ref_id))
        conn.commit()
    conn.close()
    
    # Kanalga a'zolikni tekshirish
    try:
        member = context.bot.get_chat_member(CHANNEL, user.id)
        if member.status in ["member", "creator", "administrator"]:
            update.message.reply_text(
                f"🌟 Assalomu alaykum {first_name}!\nBotga xush kelibsiz!",
                reply_markup=main_menu_keyboard()
            )
        else:
            buttons = [
                [InlineKeyboardButton("📢 Kanalga o'tish", 
                                      url=f"https://t.me/{CHANNEL.lstrip('@')}")],
                [InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")]
            ]
            update.message.reply_text(
                f"🌟 Assalomu alaykum {first_name}!\n"
                f"Botdan foydalanish uchun kanalimizga a'zo bo'ling.",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
    except Exception as e:
        logger.warning(f"Channel check error: {e}")
        buttons = [
            [InlineKeyboardButton("📢 Kanalga o'tish", 
                                  url=f"https://t.me/{CHANNEL.lstrip('@')}")],
            [InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")]
        ]
        update.message.reply_text(
            f"🌟 Assalomu alaykum {first_name}!\n"
            f"Botdan foydalanish uchun kanalimizga a'zo bo'ling.",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

# ======================
# KANAL TEKSHIRISH
# ======================
def check_sub(update: Update, context: CallbackContext):
    query = update.callback_query
    user = query.from_user
    
    try:
        member = context.bot.get_chat_member(CHANNEL, user.id)
        if member.status in ["member", "creator", "administrator"]:
            query.answer("✅ A'zo bo'lgansiz!")
            query.edit_message_text(
                "✅ A'zo bo'lgansiz! 🎉",
                reply_markup=main_menu_keyboard()
            )
        else:
            query.answer("❌ A'zo emassiz!")
            buttons = [
                [InlineKeyboardButton("📢 Kanalga o'tish", 
                                      url=f"https://t.me/{CHANNEL.lstrip('@')}")],
                [InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")]
            ]
            query.edit_message_text(
                f"❌ Siz kanalga a'zo emassiz! Iltimos a'zo bo'ling: {CHANNEL}",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
    except Exception as e:
        logger.warning(f"Channel check error: {e}")
        query.edit_message_text(
            f"❌ Xatolik yuz berdi. Iltimos keyinroq urinib ko'ring."
        )

# ======================
# MENU BO'LIMLARI
# ======================
def menu_products(update: Update, context: CallbackContext):
    """🛒 Mahsulotlar bo'limi"""
    query = update.callback_query
    text = (f"🛒 Mahsulotlar\n\n"
            f"Kerakli mahsulotlarni kanaldan tanlang va bizga xabar shaklida yozing.\n"
            f"👉 {CHANNEL}")
    buttons = [
        [InlineKeyboardButton("📢 Kanalga o'tish", 
                              url=f"https://t.me/{CHANNEL.lstrip('@')}")],
        [InlineKeyboardButton("✅ Buyurtma berish", callback_data="order_start")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ]
    query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

def menu_promo(update: Update, context: CallbackContext):
    """📢 Aksiyalar bo'limi"""
    query = update.callback_query
    conn = get_db()
    promo = conn.execute("SELECT text FROM promotions WHERE id=1").fetchone()
    conn.close()
    
    text = promo['text'] if promo else "Aksiyalar mavjud emas."
    buttons = [
        [InlineKeyboardButton("📢 Kanalga o'tish", 
                              url=f"https://t.me/{CHANNEL.lstrip('@')}")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ]
    query.edit_message_text(
        f"📢 Aksiyalar\n\n{text}\n\n👉 {CHANNEL}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

def menu_partners(update: Update, context: CallbackContext):
    """🤝 Hamkorlar bo'limi"""
    query = update.callback_query
    text = (f"🤝 Hamkorlarimiz\n\n"
            f"Biz bilan hamkorlik qilayotgan tashkilotlar:\n"
            f"👉 {HAMKORLAR}")
    buttons = [
        [InlineKeyboardButton("📢 Kanalga o'tish", 
                              url=f"https://t.me/{CHANNEL.lstrip('@')}")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ]
    query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

def menu_about(update: Update, context: CallbackContext):
    """📌 Biz haqimizda bo'limi"""
    query = update.callback_query
    text = (f"📌 Biz haqimizda\n\n"
            f"Yoriyev Market – Peshku tumanidagi eng arzon va sifatli "
            f"meva-sabzavotlar yetkazib berish xizmati.\n\n"
            f"Manzil: Buxoro, Peshku, Chalmagadoy qishlog'i (Paynet ro'parasi)\n"
            f"Telefon: {ADMIN_PHONE}\n"
            f"👉 {BIZ_HAQIMIZDA}")
    buttons = [
        [InlineKeyboardButton("📢 Kanalga o'tish", 
                              url=f"https://t.me/{CHANNEL.lstrip('@')}")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ]
    query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

def menu_contact(update: Update, context: CallbackContext):
    """📞 Admin bilan bog'lanish"""
    query = update.callback_query
    text = f"📞 Admin bilan bog'lanish\n\nAdmin: @akmalyoriyev"
    buttons = [
        [InlineKeyboardButton("👤 Admin profili", url="https://t.me/akmalyoriyev")],
        [InlineKeyboardButton("📞 Telefon raqam", callback_data="show_phone")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ]
    query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

def show_phone(update: Update, context: CallbackContext):
    """Telefon raqamni ko'rsatish"""
    query = update.callback_query
    query.edit_message_text(
        f"📞 Admin telefon raqami: {ADMIN_PHONE}",
        reply_markup=back_button("menu_contact")
    )

def menu_complaint(update: Update, context: CallbackContext):
    """⚠️ Shikoyat / Taklif"""
    query = update.callback_query
    buttons = [
        [InlineKeyboardButton("⚠️ Shikoyat", callback_data="complaint")],
        [InlineKeyboardButton("💡 Taklif", callback_data="suggestion")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ]
    query.edit_message_text(
        "📝 Shikoyat yoki taklif?",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

def menu_referral(update: Update, context: CallbackContext):
    """💡 Taklif qilish (referral)"""
    query = update.callback_query
    user_id = query.from_user.id
    
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", 
                        (user_id,)).fetchone()[0]
    discount = conn.execute("SELECT discount_count FROM users WHERE user_id=?", 
                           (user_id,)).fetchone()[0]
    conn.close()
    
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    text = (f"💡 Taklif qilish tizimi\n\n"
            f"Do'stlaringizni taklif qiling va chegirmalar oling!\n\n"
            f"1️⃣ Havolani do'stingizga yuboring\n"
            f"2️⃣ Do'stingiz birinchi buyurtma bersa, siz va do'stingiz 1 tadan chegirma olasiz\n\n"
            f"🔗 Sizning havolangiz: {ref_link}\n\n"
            f"Taklif qilganlaringiz: {count}\n"
            f"Chegirmalaringiz: {discount}")
    
    query.edit_message_text(text, reply_markup=back_button())

def menu_payment(update: Update, context: CallbackContext):
    """💳 To'lov tizimi"""
    query = update.callback_query
    text = (f"💳 To'lov tizimi\n\n"
            f"Mahsulot sizga yoqsa, keyin to'lov qilasiz.\n"
            f"Buyurtma berish jarayonida to'lov haqida admin bilan kelishiladi.\n\n"
            f"💡 To'lov usullari: naqd, Click, Payme, Apelsin.")
    query.edit_message_text(text, reply_markup=back_button())

# ======================
# BUYURTMA BERISH JARAYONI
# ======================
def order_start(update: Update, context: CallbackContext):
    """Buyurtma berishni boshlash"""
    query = update.callback_query
    query.edit_message_text(
        "📝 Mahsulotlar ro'yxatini yozing:\n"
        "Masalan: 2 kg kartoshka, 1 kg piyoz, 3 dona banan\n\n"
        "[⬅️ Orqaga]",
        reply_markup=back_button("main_menu")
    )
    return PRODUCTS

def products_input(update: Update, context: CallbackContext):
    """Mahsulotlar ro'yxatini qabul qilish"""
    context.user_data['items'] = update.message.text
    
    buttons = [
        [KeyboardButton("✍️ Ism yozish"), 
         KeyboardButton("📱 Profilni yuborish", request_contact=True)]
    ]
    update.message.reply_text(
        "👤 Ismingizni kiriting yoki profilni yuboring:",
        reply_markup=ReplyKeyboardMarkup(
            buttons, resize_keyboard=True, one_time_keyboard=True
        )
    )
    return NAME

def name_input(update: Update, context: CallbackContext):
    """Ism yoki kontaktni qabul qilish"""
    if update.message.contact:
        context.user_data['first_name'] = update.message.contact.first_name
        context.user_data['phone'] = update.message.contact.phone_number
        update.message.reply_text(
            "📍 Manzilingizni kiriting:",
            reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True)
        )
        return ADDRESS
    else:
        context.user_data['first_name'] = update.message.text
        update.message.reply_text(
            "📞 Telefon raqamingizni kiriting:",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("📱 Profilni yuborish", request_contact=True)]],
                resize_keyboard=True, one_time_keyboard=True
            )
        )
        return PHONE

def phone_input(update: Update, context: CallbackContext):
    """Telefon raqamni qabul qilish"""
    if update.message.contact:
        context.user_data['phone'] = update.message.contact.phone_number
    else:
        context.user_data['phone'] = update.message.text
    
    update.message.reply_text(
        "📍 Manzilingizni kiriting:",
        reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True)
    )
    return ADDRESS

def address_input(update: Update, context: CallbackContext):
    """Manzilni qabul qilish va buyurtmani saqlash"""
    context.user_data['address'] = update.message.text
    user_id = update.message.from_user.id
    items = context.user_data['items']
    first_name = context.user_data['first_name']
    phone = context.user_data['phone']
    address = context.user_data['address']
    
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO orders (user_id, items, status, created_at) 
        VALUES (?, ?, 'yangi', ?)
    """, (user_id, items, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    order_id = c.lastrowid
    
    # Referral chegirmasini tekshirish
    user = c.execute("SELECT referred_by, total_orders FROM users WHERE user_id=?", 
                    (user_id,)).fetchone()
    if user and user['referred_by'] and user['total_orders'] == 0:
        # Birinchi buyurtma va referral orqali kelgan
        c.execute("UPDATE users SET discount_count = discount_count + 1 WHERE user_id=?", 
                 (user['referred_by'],))
        c.execute("UPDATE users SET discount_count = discount_count + 1 WHERE user_id=?", 
                 (user_id,))
        # Referralga xabar
        try:
            context.bot.send_message(
                user['referred_by'],
                "🎉 Siz taklif qilgan do'stingiz birinchi buyurtmasini berdi!\n"
                "Endi siz chegirmaga ega bo'ldingiz."
            )
        except:
            pass
    
    c.execute("UPDATE users SET total_orders = total_orders + 1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    
    # Adminga xabar
    context.bot.send_message(
        ADMIN_ID,
        f"🆕 YANGI BUYURTMA!\n\n"
        f"👤 Ism: {first_name}\n"
        f"📞 Tel: {phone}\n"
        f"📍 Manzil: {address}\n"
        f"🆔 ID: {user_id}\n"
        f"📦 Mahsulotlar: {items}\n"
        f"🔢 Buyurtma №: {order_id}\n"
        f"🔗 Profil: tg://user?id={user_id}"
    )
    
    # Foydalanuvchiga tasdiq
    update.message.reply_text(
        "✅ Buyurtmangiz qabul qilindi!\n\n"
        "Tez orada admin siz bilan bog'lanadi.\n\n"
        "<i>Yoriyev Market tomonidan sizga rahmat!</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_keyboard()
    )
    
    return ConversationHandler.END

# ======================
# SHIKOYAT / TAKLIF JARAYONI
# ======================
def complaint_start(update: Update, context: CallbackContext):
    """Shikoyat yozishni boshlash"""
    query = update.callback_query
    context.user_data['complaint_type'] = 'shikoyat'
    query.edit_message_text(
        "⚠️ Shikoyatingizni yozib yuboring:",
        reply_markup=back_button("menu_complaint")
    )
    return COMPLAINT

def suggestion_start(update: Update, context: CallbackContext):
    """Taklif yozishni boshlash"""
    query = update.callback_query
    context.user_data['complaint_type'] = 'taklif'
    query.edit_message_text(
        "💡 Taklifingizni yozib yuboring:",
        reply_markup=back_button("menu_complaint")
    )
    return SUGGESTION

def complaint_input(update: Update, context: CallbackContext):
    """Shikoyat/taklif matnini qabul qilish"""
    text = update.message.text
    user_id = update.message.from_user.id
    ctype = context.user_data.get('complaint_type', 'shikoyat')
    
    conn = get_db()
    conn.execute("""
        INSERT INTO complaints (user_id, text, type, created_at) 
        VALUES (?, ?, ?, ?)
    """, (user_id, text, ctype, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    
    # Adminga xabar
    emoji = "⚠️" if ctype == "shikoyat" else "💡"
    context.bot.send_message(
        ADMIN_ID,
        f"{emoji} Yangi {ctype}:\n"
        f"👤 ID: {user_id}\n"
        f"🔗 Profil: tg://user?id={user_id}\n"
        f"📝 {text}"
    )
    
    # Foydalanuvchiga tasdiq
    update.message.reply_text(
        f"✅ {ctype.title()}ingiz qabul qilindi!\n\nRahmat!",
        reply_markup=main_menu_keyboard()
    )
    
    return ConversationHandler.END

# ======================
# ADMIN PANEL
# ======================
def admin_panel(update: Update, context: CallbackContext):
    """Admin panelni ko'rsatish"""
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
        [InlineKeyboardButton("⬅️ Bosh menyu", callback_data="main_menu")]
    ]
    update.message.reply_text(
        "🛠 Admin panel",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

def admin_stats(update: Update, context: CallbackContext):
    """Statistika"""
    query = update.callback_query
    conn = get_db()
    
    users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    new_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE status='yangi'").fetchone()[0]
    today = datetime.now().strftime("%Y-%m-%d")
    today_orders = conn.execute(
        "SELECT COUNT(*) FROM orders WHERE date(created_at)=?", (today,)
    ).fetchone()[0]
    complaints = conn.execute(
        "SELECT COUNT(*) FROM complaints WHERE type='shikoyat'"
    ).fetchone()[0]
    suggestions = conn.execute(
        "SELECT COUNT(*) FROM complaints WHERE type='taklif'"
    ).fetchone()[0]
    conn.close()
    
    text = (f"📊 Statistika\n\n"
            f"👥 Jami foydalanuvchilar: {users}\n"
            f"🆕 Yangi buyurtmalar: {new_orders}\n"
            f"📅 Bugungi buyurtmalar: {today_orders}\n"
            f"⚠️ Shikoyatlar: {complaints}\n"
            f"💡 Takliflar: {suggestions}")
    
    query.edit_message_text(text, reply_markup=back_button("admin_panel"))

def admin_orders(update: Update, context: CallbackContext):
    """Yangi buyurtmalar"""
    query = update.callback_query
    conn = get_db()
    orders = conn.execute("SELECT * FROM orders WHERE status='yangi'").fetchall()
    conn.close()
    
    if not orders:
        text = "📦 Yangi buyurtmalar mavjud emas."
    else:
        text = "📦 Yangi buyurtmalar:\n\n"
        for o in orders:
            text += (f"ID: {o['id']}\n"
                     f"Foydalanuvchi ID: {o['user_id']}\n"
                     f"Mahsulotlar: {o['items']}\n"
                     f"Sana: {o['created_at']}\n\n")
    
    query.edit_message_text(text, reply_markup=back_button("admin_panel"))

def admin_complaints(update: Update, context: CallbackContext):
    """Shikoyatlar"""
    query = update.callback_query
    conn = get_db()
    complaints = conn.execute(
        "SELECT * FROM complaints WHERE type='shikoyat' ORDER BY created_at DESC LIMIT 10"
    ).fetchall()
    conn.close()
    
    if not complaints:
        text = "⚠️ Shikoyatlar mavjud emas."
    else:
        text = "⚠️ Oxirgi 10 ta shikoyat:\n\n"
        for c in complaints:
            text += (f"ID: {c['id']} | User: {c['user_id']}\n"
                     f"📝 {c['text']}\n"
                     f"🕒 {c['created_at']}\n\n")
    
    query.edit_message_text(text, reply_markup=back_button("admin_panel"))

def admin_suggestions(update: Update, context: CallbackContext):
    """Takliflar"""
    query = update.callback_query
    conn = get_db()
    suggestions = conn.execute(
        "SELECT * FROM complaints WHERE type='taklif' ORDER BY created_at DESC LIMIT 10"
    ).fetchall()
    conn.close()
    
    if not suggestions:
        text = "💡 Takliflar mavjud emas."
    else:
        text = "💡 Oxirgi 10 ta taklif:\n\n"
        for s in suggestions:
            text += (f"ID: {s['id']} | User: {s['user_id']}\n"
                     f"📝 {s['text']}\n"
                     f"🕒 {s['created_at']}\n\n")
    
    query.edit_message_text(text, reply_markup=back_button("admin_panel"))

def admin_edit_promo(update: Update, context: CallbackContext):
    """Aksiyani tahrirlash"""
    query = update.callback_query
    query.edit_message_text(
        "📢 Yangi aksiya matnini yuboring:",
        reply_markup=back_button("admin_panel")
    )
    return EDIT_PROMO

def admin_broadcast(update: Update, context: CallbackContext):
    """Xabar yuborish"""
    query = update.callback_query
    query.edit_message_text(
        "📤 Barcha foydalanuvchilarga yuboriladigan xabar matnini yozing:",
        reply_markup=back_button("admin_panel")
    )
    return BROADCAST

def admin_text_handler(update: Update, context: CallbackContext):
    """Admin matnlarini qayta ishlash"""
    if context.user_data.get('edit_promo'):
        text = update.message.text
        conn = get_db()
        conn.execute("INSERT OR REPLACE INTO promotions (id, text) VALUES (1, ?)", (text,))
        conn.commit()
        conn.close()
        update.message.reply_text(
            "✅ Aksiya yangilandi!",
            reply_markup=main_menu_keyboard()
        )
        context.user_data['edit_promo'] = False
        return ConversationHandler.END
    
    elif context.user_data.get('broadcast'):
        text = update.message.text
        conn = get_db()
        users = conn.execute("SELECT user_id FROM users").fetchall()
        conn.close()
        
        success = 0
        failed = 0
        for user in users:
            try:
                context.bot.send_message(
                    user['user_id'],
                    f"📢 Broadcast xabar:\n\n{text}"
                )
                success += 1
            except:
                failed += 1
        
        update.message.reply_text(
            f"✅ Xabar yuborildi!\n"
            f"Yuborildi: {success} ta\n"
            f"Xatolik: {failed} ta",
            reply_markup=main_menu_keyboard()
        )
        context.user_data['broadcast'] = False
        return ConversationHandler.END
    
    return ConversationHandler.END

# ======================
# UMUMIY CALLBACK HANDLER
# ======================
def callback_handler(update: Update, context: CallbackContext):
    """Barcha callbacklarni qayta ishlash"""
    query = update.callback_query
    data = query.data
    query.answer()
    
    # Bosh menyu
    if data == "main_menu":
        show_main_menu(query, context)
    
    # Kanal tekshirish
    elif data == "check_sub":
        check_sub(update, context)
    
    # Asosiy menyu bo'limlari
    elif data == "menu_products":
        menu_products(update, context)
    elif data == "menu_promo":
        menu_promo(update, context)
    elif data == "menu_partners":
        menu_partners(update, context)
    elif data == "menu_about":
        menu_about(update, context)
    elif data == "menu_contact":
        menu_contact(update, context)
    elif data == "menu_complaint":
        menu_complaint(update, context)
    elif data == "menu_referral":
        menu_referral(update, context)
    elif data == "menu_payment":
        menu_payment(update, context)
    elif data == "show_phone":
        show_phone(update, context)
    
    # Admin panel
    elif data == "admin_stats":
        admin_stats(update, context)
    elif data == "admin_orders":
        admin_orders(update, context)
    elif data == "admin_complaints":
        admin_complaints(update, context)
    elif data == "admin_suggestions":
        admin_suggestions(update, context)
    elif data == "admin_edit_promo":
        return admin_edit_promo(update, context)
    elif data == "admin_broadcast":
        return admin_broadcast(update, context)
    elif data == "admin_panel":
        # Admin panelga qaytish
        query.edit_message_text(
            "🛠 Admin panel",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
                [InlineKeyboardButton("📦 Yangi buyurtmalar", callback_data="admin_orders")],
                [InlineKeyboardButton("⚠️ Shikoyatlar", callback_data="admin_complaints")],
                [InlineKeyboardButton("💡 Takliflar", callback_data="admin_suggestions")],
                [InlineKeyboardButton("📢 Aksiyani tahrirlash", callback_data="admin_edit_promo")],
                [InlineKeyboardButton("📤 Xabar yuborish", callback_data="admin_broadcast")],
                [InlineKeyboardButton("⬅️ Bosh menyu", callback_data="main_menu")]
            ])
        )
    
    return ConversationHandler.END

# ======================
# ASOSIY FUNKSIYA
# ======================
def main():
    """Botni ishga tushirish"""
    # Ma'lumotlar bazasini yaratish
    init_db()
    
    # Updater yaratish
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    
    # Buyurtma berish conversation handler
    order_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(order_start, pattern="^order_start$")],
        states={
            PRODUCTS: [MessageHandler(Filters.text & ~Filters.command, products_input)],
            NAME: [MessageHandler(Filters.text & ~Filters.command | Filters.contact, name_input)],
            PHONE: [MessageHandler(Filters.text & ~Filters.command | Filters.contact, phone_input)],
            ADDRESS: [MessageHandler(Filters.text & ~Filters.command, address_input)],
        },
        fallbacks=[CommandHandler("start", start)],
        name="order_conversation",
        persistent=False
    )
    
    # Shikoyat/Taklif conversation handler
    complaint_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(complaint_start, pattern="^complaint$"),
            CallbackQueryHandler(suggestion_start, pattern="^suggestion$")
        ],
        states={
            COMPLAINT: [MessageHandler(Filters.text & ~Filters.command, complaint_input)],
            SUGGESTION: [MessageHandler(Filters.text & ~Filters.command, complaint_input)],
        },
        fallbacks=[CommandHandler("start", start)],
        name="complaint_conversation",
        persistent=False
    )
    
    # Admin aksiya tahrirlash conversation handler
    admin_promo_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_edit_promo, pattern="^admin_edit_promo$")],
        states={
            EDIT_PROMO: [MessageHandler(Filters.text & ~Filters.command, admin_text_handler)],
        },
        fallbacks=[CommandHandler("start", start)],
        name="admin_promo_conversation",
        persistent=False
    )
    
    # Admin broadcast conversation handler
    admin_broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_broadcast, pattern="^admin_broadcast$")],
        states={
            BROADCAST: [MessageHandler(Filters.text & ~Filters.command, admin_text_handler)],
        },
        fallbacks=[CommandHandler("start", start)],
        name="admin_broadcast_conversation",
        persistent=False
    )
    
    # Handlerlarni qo'shish
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("admin", admin_panel))
    dp.add_handler(order_conv)
    dp.add_handler(complaint_conv)
    dp.add_handler(admin_promo_conv)
    dp.add_handler(admin_broadcast_conv)
    dp.add_handler(CallbackQueryHandler(callback_handler))
    
    # Botni ishga tushirish
    updater.start_polling()
    logger.info("Bot ishga tushdi!")
    updater.idle()

if __name__ == "__main__":
    main()
