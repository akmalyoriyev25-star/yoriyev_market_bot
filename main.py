# -*- coding: utf-8 -*-
"""YORIYEV MARKET BOT – YAKUNIY ISHCHI VERSIYA"""

import logging
import os
import sqlite3
import re
from datetime import datetime
from functools import wraps

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Updater, CommandHandler, CallbackQueryHandler, MessageHandler,
    Filters, CallbackContext, ConversationHandler
)

# ==================== KONFIGURATSIYA ====================
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN topilmadi! Railway'da environment variable qo'shing.")

CHANNEL = os.environ.get("CHANNEL_USERNAME", "@yoriyev_market")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
BOT_USERNAME = os.environ.get("BOT_USERNAME", "Yoriyev_market_bot")
ADMIN_PHONE = os.environ.get("ADMIN_PHONE", "+998883092500")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "akmalyoriyev")

# Kanallar
PARTNERS_CHANNEL = "https://t.me/hamkorlarimiz_yoriyev_market"
ABOUT_CHANNEL = "https://t.me/biz_haqimizda_yoriyev_market"

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== MA'LUMOTLAR BAZASI ====================
DB_PATH = "yoriyev_market.db"

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
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
        conn.execute("INSERT OR IGNORE INTO promotions (id, text) VALUES (1, '🔥 Hozircha maxsus aksiyalar yoʻq')")
        conn.commit()

init_db()

# ==================== YORDAMCHI FUNKSIYALAR ====================
def is_admin(user_id):
    return user_id == ADMIN_ID

def safe_str(text):
    return re.sub(r'[<>&]', '', text) if text else ''

def validate_phone(phone):
    return re.match(r'^\+998\d{9}$', phone) is not None

def get_or_create_user(user_id, first_name, username=None, referred_by=None):
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not user:
            conn.execute("""
                INSERT INTO users (user_id, first_name, username, registered_at, last_active, referred_by)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, safe_str(first_name), username, datetime.now().isoformat(),
                  datetime.now().isoformat(), referred_by))
            conn.commit()
        else:
            conn.execute("UPDATE users SET last_active=? WHERE user_id=?", (datetime.now().isoformat(), user_id))
            conn.commit()

def add_discount(user_id, count=1):
    with get_db() as conn:
        conn.execute("UPDATE users SET discount_count = discount_count + ? WHERE user_id=?", (count, user_id))
        conn.commit()

# ==================== KANAL TEKSHIRISH ====================
def check_subscription(bot, user_id):
    try:
        member = bot.get_chat_member(chat_id=CHANNEL, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def require_subscription(func):
    @wraps(func)
    def wrapper(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if check_subscription(context.bot, user_id):
            return func(update, context, *args, **kwargs)
        else:
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL.lstrip('@')}"),
                InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")
            ]])
            if update.message:
                update.message.reply_text(
                    "🚫 Botdan foydalanish uchun kanalimizga a'zo bo'ling!",
                    reply_markup=keyboard
                )
            elif update.callback_query:
                update.callback_query.edit_message_text(
                    "🚫 Botdan foydalanish uchun kanalimizga a'zo bo'ling!",
                    reply_markup=keyboard
                )
    return wrapper

# ==================== HOLATLAR ====================
(
    STATE_PRODUCT,
    STATE_NAME,
    STATE_PHONE,
    STATE_ADDRESS,
    STATE_COMPLAINT,
    STATE_SUGGESTION,
    STATE_ADMIN_PROMO,
    STATE_ADMIN_BROADCAST
) = range(8)

# ==================== START ====================
def start(update: Update, context: CallbackContext):
    user = update.effective_user
    args = context.args
    referred_by = None
    if args and args[0].startswith("ref_"):
        try:
            referred_by = int(args[0][4:])
        except:
            pass
    get_or_create_user(user.id, user.first_name, user.username, referred_by)

    if check_subscription(context.bot, user.id):
        show_main_menu(update, context)
    else:
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL.lstrip('@')}"),
            InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")
        ]])
        update.message.reply_text(
            f"🌟 Assalomu alaykum {user.first_name}!\n\nBotdan foydalanish uchun kanalimizga a'zo bo'ling.",
            reply_markup=keyboard
        )

def check_sub_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    if check_subscription(context.bot, query.from_user.id):
        query.edit_message_text("✅ A'zo bo'lgansiz!")
        show_main_menu(update, context, edit=True)
    else:
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL.lstrip('@')}"),
            InlineKeyboardButton("🔄 Qayta tekshirish", callback_data="check_sub")
        ]])
        query.edit_message_text(
            "❌ Siz kanalga a'zo emassiz. Iltimos, avval a'zo bo'ling.",
            reply_markup=keyboard
        )

def show_main_menu(update: Update, context: CallbackContext, edit=False):
    keyboard = [
        [InlineKeyboardButton("🛒 Mahsulotlar", callback_data="menu_products")],
        [InlineKeyboardButton("📢 Aksiyalar", callback_data="menu_promo")],
        [InlineKeyboardButton("🤝 Hamkorlar", callback_data="menu_partners")],
        [InlineKeyboardButton("📌 Biz haqimizda", callback_data="menu_about")],
        [InlineKeyboardButton("📞 Admin bilan bog'lanish", callback_data="menu_contact")],
        [InlineKeyboardButton("⚠️ Shikoyat / Taklif", callback_data="menu_complaint")],
        [InlineKeyboardButton("💡 Taklif qilish", callback_data="menu_referral")],
        [InlineKeyboardButton("💳 To'lov tizimi", callback_data="menu_payment")]
    ]
    text = "🏠 Bosh menyu"
    if edit:
        update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ==================== MAHSULOTLAR ====================
@require_subscription
def products_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    text = (
        "🛒 Mahsulotlar\n\n"
        f"Kerakli mahsulotlarni kanaldan tanlang va bizga xabar shaklida yozing.\n\n"
        f"👉 @{CHANNEL.lstrip('@')}"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL.lstrip('@')}"),
        InlineKeyboardButton("✅ Buyurtma berish", callback_data="order_start")
    ]])
    query.edit_message_text(text, reply_markup=keyboard)

# ==================== BUYURTMA JARAYONI ====================
@require_subscription
def order_start(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        "📝 Mahsulotlar ro'yxatini yozing:\n\n"
        "Masalan: 2 kg kartoshka, 1 kg piyoz, 3 dona banan",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")
        ]])
    )
    return STATE_PRODUCT

def handle_product(update: Update, context: CallbackContext):
    text = safe_str(update.message.text)
    if len(text) < 2:
        update.message.reply_text("❌ Mahsulot ro'yxati juda qisqa. Qayta kiriting:")
        return STATE_PRODUCT
    context.user_data['items'] = text

    # Ism so'rash
    keyboard = ReplyKeyboardMarkup([
        [KeyboardButton("✍️ Ism yozish")],
        [KeyboardButton("📱 Profilni yuborish", request_contact=True)]
    ], resize_keyboard=True, one_time_keyboard=True)
    update.message.reply_text(
        "👤 Ismingizni kiriting yoki profilni yuboring:",
        reply_markup=keyboard
    )
    return STATE_NAME

def handle_name(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    if update.message.contact:
        contact = update.message.contact
        context.user_data['name'] = contact.first_name
        context.user_data['phone'] = contact.phone_number
        with get_db() as conn:
            conn.execute("UPDATE users SET phone=? WHERE user_id=?", (contact.phone_number, user_id))
            conn.commit()
        # Admin xabar (profil)
        if ADMIN_ID:
            try:
                context.bot.send_message(
                    ADMIN_ID,
                    f"📱 Yangi profil ulashdi:\n👤 {contact.first_name}\n📞 {contact.phone_number}\n🆔 {user_id}\n🔗 tg://user?id={user_id}"
                )
            except:
                pass
        update.message.reply_text("📍 Manzilingizni kiriting:", reply_markup=ReplyKeyboardRemove())
        return STATE_ADDRESS

    elif update.message.text == "✍️ Ism yozish":
        update.message.reply_text("👤 Ismingizni yozing:", reply_markup=ReplyKeyboardRemove())
        return STATE_NAME

    else:
        name = safe_str(update.message.text)
        if len(name) < 2:
            update.message.reply_text("❌ Ism juda qisqa. Qayta kiriting:")
            return STATE_NAME
        context.user_data['name'] = name
        update.message.reply_text(
            "📞 Telefon raqamingizni kiriting:\nFormat: +998901234567",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("📱 Profilni yuborish", request_contact=True)]],
                resize_keyboard=True, one_time_keyboard=True
            )
        )
        return STATE_PHONE

def handle_phone(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    if update.message.contact:
        contact = update.message.contact
        context.user_data['phone'] = contact.phone_number
        with get_db() as conn:
            conn.execute("UPDATE users SET phone=? WHERE user_id=?", (contact.phone_number, user_id))
            conn.commit()
        if ADMIN_ID:
            try:
                context.bot.send_message(
                    ADMIN_ID,
                    f"📱 Yangi profil ulashdi:\n👤 {contact.first_name}\n📞 {contact.phone_number}\n🆔 {user_id}\n🔗 tg://user?id={user_id}"
                )
            except:
                pass
        update.message.reply_text("📍 Manzilingizni kiriting:", reply_markup=ReplyKeyboardRemove())
        return STATE_ADDRESS

    else:
        phone = safe_str(update.message.text)
        if not validate_phone(phone):
            update.message.reply_text("❌ Noto'g'ri format. Qayta kiriting (masalan: +998901234567):")
            return STATE_PHONE
        context.user_data['phone'] = phone
        with get_db() as conn:
            conn.execute("UPDATE users SET phone=? WHERE user_id=?", (phone, user_id))
            conn.commit()
        update.message.reply_text("📍 Manzilingizni kiriting:", reply_markup=ReplyKeyboardRemove())
        return STATE_ADDRESS

def handle_address(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    address = safe_str(update.message.text)
    if len(address) < 3:
        update.message.reply_text("❌ Manzil juda qisqa. Qayta kiriting:")
        return STATE_ADDRESS

    context.user_data['address'] = address
    with get_db() as conn:
        conn.execute("UPDATE users SET address=? WHERE user_id=?", (address, user_id))
        conn.commit()

    # Buyurtmani saqlash
    name = context.user_data['name']
    phone = context.user_data['phone']
    items = context.user_data['items']

    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO orders (user_id, items, status, created_at) VALUES (?, ?, ?, ?)",
        (user_id, items, "yangi", datetime.now().isoformat())
    )
    order_id = cursor.lastrowid
    conn.execute("UPDATE users SET total_orders = total_orders + 1 WHERE user_id=?", (user_id,))
    conn.commit()

    # Referral tekshirish
    user = conn.execute("SELECT referred_by, total_orders FROM users WHERE user_id=?", (user_id,)).fetchone()
    if user and user['referred_by'] and user['total_orders'] == 1:
        add_discount(user['referred_by'])
        add_discount(user_id)
        try:
            context.bot.send_message(
                user['referred_by'],
                "🎉 Siz taklif qilgan do'stingiz birinchi buyurtmasini berdi! Endi siz chegirmaga ega bo'ldingiz."
            )
        except:
            pass

    # Admin xabar (buyurtma)
    if ADMIN_ID:
        try:
            admin_msg = (
                f"🆕 YANGI BUYURTMA!\n\n"
                f"👤 Ism: {name}\n"
                f"📞 Tel: {phone}\n"
                f"📍 Manzil: {address}\n"
                f"🆔 ID: {user_id}\n"
                f"🔗 Profil: tg://user?id={user_id}\n"
                f"📦 Mahsulotlar: {items}\n"
                f"🔢 Buyurtma №: {order_id}"
            )
            context.bot.send_message(ADMIN_ID, admin_msg)
        except Exception as e:
            logger.error(f"Admin xabar yuborishda xatolik: {e}")

    # Mijozga xabar
    context.user_data.clear()
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")
    ]])
    update.message.reply_text(
        f"✅ Buyurtmangiz qabul qilindi!\n\nTez orada admin siz bilan bog'lanadi.\n\n<i>Yoriyev Market tomonidan sizga rahmat!</i>",
        reply_markup=keyboard
    )
    return ConversationHandler.END

# ==================== AKSIYALAR ====================
@require_subscription
def show_promotion(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    with get_db() as conn:
        promo = conn.execute("SELECT text FROM promotions WHERE id=1").fetchone()
        text = promo['text'] if promo else "Aksiyalar mavjud emas."
    msg = f"📢 Aksiyalar\n\n{text}\n\n👉 @{CHANNEL.lstrip('@')}"
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL.lstrip('@')}"),
        InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")
    ]])
    query.edit_message_text(msg, reply_markup=keyboard)

# ==================== HAMKORLAR ====================
@require_subscription
def partners(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    msg = f"🤝 Hamkorlarimiz\n\nBiz bilan hamkorlik qilayotgan tashkilotlar:\n\n👉 {PARTNERS_CHANNEL}"
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📢 Kanalga o'tish", url=PARTNERS_CHANNEL),
        InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")
    ]])
    query.edit_message_text(msg, reply_markup=keyboard)

# ==================== BIZ HAQIMIZDA ====================
@require_subscription
def about(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    msg = (
        f"📌 Biz haqimizda\n\n"
        f"Yoriyev Market – Peshku tumanidagi eng arzon va sifatli meva-sabzavotlar yetkazib berish xizmati.\n\n"
        f"Manzil: Buxoro, Peshku, Chalmagadoy qishlog'i (Paynet ro'parasi)\n"
        f"Telefon: {ADMIN_PHONE}\n\n"
        f"👉 {ABOUT_CHANNEL}"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📢 Kanalga o'tish", url=ABOUT_CHANNEL),
        InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")
    ]])
    query.edit_message_text(msg, reply_markup=keyboard)

# ==================== ADMIN BILAN BOG'LANISH ====================
@require_subscription
def admin_contact(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Admin profili", url=f"https://t.me/{ADMIN_USERNAME}")],
        [InlineKeyboardButton("📞 Telefon raqam", callback_data="show_phone")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ])
    query.edit_message_text(
        f"📞 Admin bilan bog'lanish\n\nAdmin: @{ADMIN_USERNAME}\n\nQuyidagi tugmalar orqali bog'lanishingiz mumkin:",
        reply_markup=keyboard
    )

def show_phone(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        f"📞 Admin telefon raqami: {ADMIN_PHONE}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_contact")
        ]])
    )

# ==================== SHIKOYAT / TAKLIF ====================
@require_subscription
def complaint_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚠️ Shikoyat", callback_data="complaint")],
        [InlineKeyboardButton("💡 Taklif", callback_data="suggestion")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ])
    query.edit_message_text("📝 Shikoyat yoki taklif?", reply_markup=keyboard)

def complaint_start(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        "⚠️ Shikoyatingizni yozing:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Bekor qilish", callback_data="main_menu")
        ]])
    )
    return STATE_COMPLAINT

def suggestion_start(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        "💡 Taklifingizni yozing:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Bekor qilish", callback_data="main_menu")
        ]])
    )
    return STATE_SUGGESTION

def handle_complaint(update: Update, context: CallbackContext):
    text = safe_str(update.message.text)
    user_id = update.effective_user.id
    if len(text) < 3:
        update.message.reply_text("❌ Xabar juda qisqa. Qayta kiriting:")
        return STATE_COMPLAINT
    with get_db() as conn:
        conn.execute("INSERT INTO complaints (user_id, text, type, created_at) VALUES (?, ?, ?, ?)",
                     (user_id, text, "shikoyat", datetime.now().isoformat()))
        conn.commit()
    if ADMIN_ID:
        try:
            context.bot.send_message(
                ADMIN_ID,
                f"⚠️ Yangi shikoyat:\n👤 ID: {user_id}\n🔗 tg://user?id={user_id}\n📝 {text}"
            )
        except:
            pass
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")
    ]])
    update.message.reply_text("✅ Shikoyatingiz qabul qilindi!", reply_markup=keyboard)
    return ConversationHandler.END

def handle_suggestion(update: Update, context: CallbackContext):
    text = safe_str(update.message.text)
    user_id = update.effective_user.id
    if len(text) < 3:
        update.message.reply_text("❌ Xabar juda qisqa. Qayta kiriting:")
        return STATE_SUGGESTION
    with get_db() as conn:
        conn.execute("INSERT INTO complaints (user_id, text, type, created_at) VALUES (?, ?, ?, ?)",
                     (user_id, text, "taklif", datetime.now().isoformat()))
        conn.commit()
    if ADMIN_ID:
        try:
            context.bot.send_message(
                ADMIN_ID,
                f"💡 Yangi taklif:\n👤 ID: {user_id}\n🔗 tg://user?id={user_id}\n📝 {text}"
            )
        except:
            pass
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")
    ]])
    update.message.reply_text("✅ Taklifingiz qabul qilindi!", reply_markup=keyboard)
    return ConversationHandler.END

# ==================== TAKLIF QILISH (REFERRAL) ====================
@require_subscription
def referral_info(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (user_id,)).fetchone()[0]
        discount = conn.execute("SELECT discount_count FROM users WHERE user_id=?", (user_id,)).fetchone()[0]
    msg = (
        f"💡 Taklif qilish tizimi\n\n"
        f"Do'stlaringizni taklif qiling va chegirmalar oling!\n\n"
        f"Qanday ishlaydi:\n"
        f"1. Havolani do'stingizga yuboring\n"
        f"2. Do'stingiz birinchi buyurtma bersa\n"
        f"3. Siz va do'stingiz 1 tadan chegirma olasiz\n\n"
        f"🔗 Sizning havolangiz:\n{ref_link}\n\n"
        f"Taklif qilganlaringiz: {count}\n"
        f"Chegirmalaringiz: {discount}"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")
    ]])
    query.edit_message_text(msg, reply_markup=keyboard)

# ==================== TO'LOV TIZIMI ====================
@require_subscription
def payment_info(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    msg = (
        "💳 To'lov tizimi\n\n"
        "Mahsulot sizga yoqsa, keyin to'lov qilasiz.\n"
        "Buyurtma berish jarayonida to'lov haqida admin bilan kelishasiz.\n\n"
        "💡 To'lov usullari: naqd, Click, Payme, Apelsin."
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")
    ]])
    query.edit_message_text(msg, reply_markup=keyboard)

# ==================== ADMIN PANEL ====================
def admin_panel(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Siz admin emassiz.")
        return
    keyboard = [
        [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton("📦 Yangi buyurtmalar", callback_data="admin_orders")],
        [InlineKeyboardButton("⚠️ Shikoyatlar", callback_data="admin_complaints")],
        [InlineKeyboardButton("💡 Takliflar", callback_data="admin_suggestions")],
        [InlineKeyboardButton("📢 Aksiyani tahrirlash", callback_data="admin_promo")],
        [InlineKeyboardButton("📤 Xabar yuborish", callback_data="admin_broadcast")],
        [InlineKeyboardButton("⬅️ Yopish", callback_data="main_menu")]
    ]
    update.message.reply_text("⚙️ Admin panel", reply_markup=InlineKeyboardMarkup(keyboard))

def admin_stats(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    with get_db() as conn:
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        new_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE status='yangi'").fetchone()[0]
        today_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE date(created_at)=date('now')").fetchone()[0]
        complaints = conn.execute("SELECT COUNT(*) FROM complaints WHERE type='shikoyat'").fetchone()[0]
        suggestions = conn.execute("SELECT COUNT(*) FROM complaints WHERE type='taklif'").fetchone()[0]
    msg = (
        f"📊 Statistika\n\n"
        f"👥 Jami foydalanuvchilar: {users}\n"
        f"🆕 Yangi buyurtmalar: {new_orders}\n"
        f"📅 Bugungi buyurtmalar: {today_orders}\n"
        f"⚠️ Shikoyatlar: {complaints}\n"
        f"💡 Takliflar: {suggestions}"
    )
    query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
    ]]))

def admin_orders(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    with get_db() as conn:
        orders = conn.execute("SELECT * FROM orders WHERE status='yangi' ORDER BY id DESC").fetchall()
    if not orders:
        query.edit_message_text("📦 Yangi buyurtmalar yoʻq.", reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
        ]]))
        return
    msg = "📦 Yangi buyurtmalar:\n\n"
    for o in orders:
        user = conn.execute("SELECT first_name, phone FROM users WHERE user_id=?", (o['user_id'],)).fetchone()
        name = user['first_name'] if user else "Noma'lum"
        phone = user['phone'] if user else "Yo'q"
        msg += (
            f"🔢 Buyurtma №{o['id']}\n"
            f"👤 Mijoz: {name}\n"
            f"📞 Tel: {phone}\n"
            f"🆔 ID: {o['user_id']}\n"
            f"📦 Mahsulotlar: {o['items']}\n"
            f"📅 Sana: {o['created_at'][:16]}\n"
            f"🔗 tg://user?id={o['user_id']}\n\n"
        )
    query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
    ]]))

def admin_complaints(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    with get_db() as conn:
        items = conn.execute("SELECT * FROM complaints WHERE type='shikoyat' ORDER BY id DESC LIMIT 10").fetchall()
    if not items:
        query.edit_message_text("⚠️ Shikoyatlar yoʻq.", reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
        ]]))
        return
    msg = "⚠️ Shikoyatlar:\n\n"
    for c in items:
        user = conn.execute("SELECT first_name, phone FROM users WHERE user_id=?", (c['user_id'],)).fetchone()
        name = user['first_name'] if user else "Noma'lum"
        phone = user['phone'] if user else "Yo'q"
        msg += (
            f"🆔 Mijoz ID: {c['user_id']}\n"
            f"👤 Ism: {name}\n"
            f"📞 Tel: {phone}\n"
            f"📝 Xabar: {c['text']}\n"
            f"📅 Sana: {c['created_at'][:16]}\n"
            f"🔗 tg://user?id={c['user_id']}\n\n"
        )
    query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
    ]]))

def admin_suggestions(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    with get_db() as conn:
        items = conn.execute("SELECT * FROM complaints WHERE type='taklif' ORDER BY id DESC LIMIT 10").fetchall()
    if not items:
        query.edit_message_text("💡 Takliflar yoʻq.", reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
        ]]))
        return
    msg = "💡 Takliflar:\n\n"
    for s in items:
        user = conn.execute("SELECT first_name, phone FROM users WHERE user_id=?", (s['user_id'],)).fetchone()
        name = user['first_name'] if user else "Noma'lum"
        phone = user['phone'] if user else "Yo'q"
        msg += (
            f"🆔 Mijoz ID: {s['user_id']}\n"
            f"👤 Ism: {name}\n"
            f"📞 Tel: {phone}\n"
            f"📝 Taklif: {s['text']}\n"
            f"📅 Sana: {s['created_at'][:16]}\n"
            f"🔗 tg://user?id={s['user_id']}\n\n"
        )
    query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
    ]]))

def admin_promo_start(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        "✍️ Yangi aksiya matnini yozing:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Bekor qilish", callback_data="admin_panel")
        ]])
    )
    return STATE_ADMIN_PROMO

def admin_promo_receive(update: Update, context: CallbackContext):
    text = safe_str(update.message.text)
    with get_db() as conn:
        conn.execute("UPDATE promotions SET text=? WHERE id=1", (text,))
        conn.commit()
    update.message.reply_text(
        "✅ Aksiya matni yangilandi!",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Admin panel", callback_data="admin_panel")
        ]])
    )
    return ConversationHandler.END

def admin_broadcast_start(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        "✍️ Barcha foydalanuvchilarga yuboriladigan xabarni yozing:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Bekor qilish", callback_data="admin_panel")
        ]])
    )
    return STATE_ADMIN_BROADCAST

def admin_broadcast_receive(update: Update, context: CallbackContext):
    text = update.message.text
    with get_db() as conn:
        users = conn.execute("SELECT user_id FROM users").fetchall()
    sent = 0
    for (uid,) in users:
        try:
            context.bot.send_message(uid, text)
            sent += 1
        except:
            pass
    update.message.reply_text(f"✅ Xabar {sent} ta foydalanuvchiga yuborildi.")
    return ConversationHandler.END

# ==================== CALLBACK HANDLER ====================
def callback_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    # Kanal tekshirish (check_sub va main_menu bundan mustasno)
    if data not in ["check_sub", "main_menu", "show_phone"]:
        if not check_subscription(context.bot, user_id):
            query.answer("⚠️ Avval kanalga a'zo bo'ling!", show_alert=True)
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL.lstrip('@')}"),
                InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")
            ]])
            query.edit_message_text(
                "🚫 Botdan foydalanish uchun kanalimizga a'zo bo'ling!",
                reply_markup=keyboard
            )
            return

    if data == "check_sub":
        check_sub_callback(update, context)
    elif data == "main_menu":
        show_main_menu(update, context, edit=True)
    elif data == "menu_products":
        products_menu(update, context)
    elif data == "order_start":
        order_start(update, context)
    elif data == "menu_promo":
        show_promotion(update, context)
    elif data == "menu_partners":
        partners(update, context)
    elif data == "menu_about":
        about(update, context)
    elif data == "menu_contact":
        admin_contact(update, context)
    elif data == "show_phone":
        show_phone(update, context)
    elif data == "menu_complaint":
        complaint_menu(update, context)
    elif data == "complaint":
        complaint_start(update, context)
    elif data == "suggestion":
        suggestion_start(update, context)
    elif data == "menu_referral":
        referral_info(update, context)
    elif data == "menu_payment":
        payment_info(update, context)
    elif data.startswith("admin_"):
        if not is_admin(user_id):
            query.answer("❌ Siz admin emassiz!", show_alert=True)
            return
        if data == "admin_stats":
            admin_stats(update, context)
        elif data == "admin_orders":
            admin_orders(update, context)
        elif data == "admin_complaints":
            admin_complaints(update, context)
        elif data == "admin_suggestions":
            admin_suggestions(update, context)
        elif data == "admin_promo":
            admin_promo_start(update, context)
        elif data == "admin_broadcast":
            admin_broadcast_start(update, context)

# ==================== MAIN ====================
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    # Order conversation
    order_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(order_start, pattern="^order_start$")],
        states={
            STATE_PRODUCT: [MessageHandler(Filters.text & ~Filters.command, handle_product)],
            STATE_NAME: [MessageHandler(Filters.all, handle_name)],
            STATE_PHONE: [MessageHandler(Filters.all, handle_phone)],
            STATE_ADDRESS: [MessageHandler(Filters.text & ~Filters.command, handle_address)],
        },
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(show_main_menu, pattern="^main_menu$")],
    )

    # Complaint conversation
    complaint_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(complaint_start, pattern="^complaint$")],
        states={STATE_COMPLAINT: [MessageHandler(Filters.text & ~Filters.command, handle_complaint)]},
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(show_main_menu, pattern="^main_menu$")],
    )

    # Suggestion conversation
    suggestion_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(suggestion_start, pattern="^suggestion$")],
        states={STATE_SUGGESTION: [MessageHandler(Filters.text & ~Filters.command, handle_suggestion)]},
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(show_main_menu, pattern="^main_menu$")],
    )

    # Admin conversations
    admin_promo_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_promo_start, pattern="^admin_promo$")],
        states={STATE_ADMIN_PROMO: [MessageHandler(Filters.text & ~Filters.command, admin_promo_receive)]},
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(show_main_menu, pattern="^main_menu$")],
    )

    admin_broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_broadcast_start, pattern="^admin_broadcast$")],
        states={STATE_ADMIN_BROADCAST: [MessageHandler(Filters.text & ~Filters.command, admin_broadcast_receive)]},
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(show_main_menu, pattern="^main_menu$")],
    )

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("admin", admin_panel))
    dp.add_handler(order_conv)
    dp.add_handler(complaint_conv)
    dp.add_handler(suggestion_conv)
    dp.add_handler(admin_promo_conv)
    dp.add_handler(admin_broadcast_conv)
    dp.add_handler(CallbackQueryHandler(callback_handler))

    updater.start_polling()
    logger.info("✅ Bot ishga tushdi!")
    updater.idle()

if __name__ == "__main__":
    main()
