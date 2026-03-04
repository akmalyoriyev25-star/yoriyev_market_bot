# -*- coding: utf-8 -*-
"""YORIYEV MARKET BOT – MUKAMMAL VERSIYA"""

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
    raise ValueError("BOT_TOKEN environment variable topilmadi!")

CHANNEL = os.environ.get("CHANNEL_USERNAME", "@yoriyev_market")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
BOT_USERNAME = os.environ.get("BOT_USERNAME", "Yoriyev_market_bot")
ADMIN_PHONE = os.environ.get("ADMIN_PHONE", "+998883092500")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "akmalyoriyev")

# KANALLAR
HAMKORLAR_KANAL = "https://t.me/hamkorlarimiz_yoriyev_market"
BIZ_HAQIMIZDA_KANAL = "https://t.me/biz_haqimizda_yoriyev_market"

# ==================== LOGGING ====================
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
        cursor.execute("INSERT OR IGNORE INTO promotions (id, text) VALUES (1, '🔥 Hozircha maxsus aksiyalar yoʻq')")
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
        cur = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        user = cur.fetchone()
        if not user:
            conn.execute("""
                INSERT INTO users (user_id, first_name, username, registered_at, last_active, referred_by)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, safe_str(first_name), username, datetime.now().isoformat(),
                  datetime.now().isoformat(), referred_by))
            conn.commit()
            return None
        else:
            conn.execute("UPDATE users SET last_active=? WHERE user_id=?", (datetime.now().isoformat(), user_id))
            conn.commit()
            return user

def update_user_activity(user_id):
    with get_db() as conn:
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
    except Exception as e:
        logger.error(f"Kanal tekshirish xatosi: {e}")
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
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            elif update.callback_query:
                update.callback_query.edit_message_text(
                    "🚫 Botdan foydalanish uchun kanalimizga a'zo bo'ling!",
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            return
    return wrapper

# ==================== HOLATLAR ====================
(
    STATE_PRODUCT_TEXT,
    STATE_ORDER_NAME,
    STATE_ORDER_PHONE,
    STATE_ORDER_ADDRESS,
    STATE_COMPLAINT_TEXT,
    STATE_SUGGESTION_TEXT,
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
            f"🌟 <b>Assalomu alaykum {user.first_name}!</b>\n\nBotdan foydalanish uchun kanalimizga a'zo bo'ling.",
            parse_mode="HTML",
            reply_markup=keyboard
        )

def check_sub_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    if check_subscription(context.bot, user_id):
        update_user_activity(user_id)
        query.edit_message_text("✅ <b>A'zo bo'lgansiz!</b>", parse_mode="HTML")
        show_main_menu(update, context, edit=True)
    else:
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL.lstrip('@')}"),
            InlineKeyboardButton("🔄 Qayta tekshirish", callback_data="check_sub")
        ]])
        query.edit_message_text(
            "❌ <b>Siz kanalga a'zo emassiz.</b> Iltimos, avval a'zo bo'ling.",
            parse_mode="HTML",
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
    text = "🏠 <b>Bosh menyu</b>"
    if edit:
        update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

# ==================== MAHSULOTLAR ====================
@require_subscription
def products_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    text = (
        "🛒 <b>Mahsulotlar</b>\n\n"
        f"Kerakli mahsulotlarni kanaldan tanlang va bizga xabar shaklida yozing.\n\n"
        f"👉 @{CHANNEL.lstrip('@')}"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL.lstrip('@')}"),
        InlineKeyboardButton("✅ Buyurtma berish", callback_data="order_start")
    ]])
    query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

# ==================== BUYURTMA JARAYONI ====================
@require_subscription
def order_start(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        "📝 <b>Mahsulotlar ro'yxatini yozing:</b>\n\n"
        "Masalan: 2 kg kartoshka, 1 kg piyoz, 3 dona banan",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_products")
        ]])
    )
    return STATE_PRODUCT_TEXT

def handle_product_text(update: Update, context: CallbackContext):
    text = safe_str(update.message.text)
    if len(text) < 2:
        update.message.reply_text("❌ Mahsulot ro'yxati juda qisqa. Qayta kiriting:")
        return STATE_PRODUCT_TEXT
    context.user_data['order_items'] = text
    update_user_activity(update.effective_user.id)

    # Ism so'rash (ikki tugma: Ism yozish yoki Profil yuborish)
    keyboard = ReplyKeyboardMarkup([
        ["✍️ Ism yozish"],
        ["📱 Profilni yuborish", request_contact=True]
    ], resize_keyboard=True, one_time_keyboard=True)
    update.message.reply_text(
        "👤 <b>Ismingizni kiriting yoki profilni yuboring:</b>",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    return STATE_ORDER_NAME

def order_name_receive(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    if update.message.contact:
        contact = update.message.contact
        context.user_data['order_name'] = contact.first_name
        context.user_data['order_phone'] = contact.phone_number

        # Admin ga profil xabari
        if ADMIN_ID:
            try:
                context.bot.send_message(
                    ADMIN_ID,
                    f"📱 <b>Yangi profil ulashdi</b>\n"
                    f"👤 Ism: {contact.first_name}\n"
                    f"📞 Telefon: {contact.phone_number}\n"
                    f"🆔 ID: {user_id}\n"
                    f"👤 Profil: <a href='tg://user?id={user_id}'>Yozish</a>",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Admin xabar yuborishda xatolik: {e}")

        with get_db() as conn:
            conn.execute("UPDATE users SET phone=? WHERE user_id=?", (contact.phone_number, user_id))
            conn.commit()

        update.message.reply_text(
            "📍 <b>Manzilingizni kiriting:</b>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove()
        )
        return STATE_ORDER_ADDRESS

    elif update.message.text == "✍️ Ism yozish":
        update.message.reply_text(
            "👤 <b>Ismingizni yozing:</b>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove()
        )
        return STATE_ORDER_NAME  # shu holatda qoladi, keyingi xabar ism bo'ladi

    else:
        name = safe_str(update.message.text)
        if len(name) < 2:
            update.message.reply_text("❌ Ism juda qisqa. Qayta kiriting:")
            return STATE_ORDER_NAME

        context.user_data['order_name'] = name
        update.message.reply_text(
            "📞 <b>Telefon raqamingizni kiriting:</b>\nFormat: +998901234567",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup([["📱 Profilni yuborish"]], resize_keyboard=True, one_time_keyboard=True)
        )
        return STATE_ORDER_PHONE

def order_phone_receive(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    if update.message.contact:
        contact = update.message.contact
        context.user_data['order_phone'] = contact.phone_number

        if ADMIN_ID:
            try:
                context.bot.send_message(
                    ADMIN_ID,
                    f"📱 <b>Yangi profil ulashdi</b>\n"
                    f"👤 Ism: {contact.first_name}\n"
                    f"📞 Telefon: {contact.phone_number}\n"
                    f"🆔 ID: {user_id}\n"
                    f"👤 Profil: <a href='tg://user?id={user_id}'>Yozish</a>",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Admin xabar yuborishda xatolik: {e}")

        with get_db() as conn:
            conn.execute("UPDATE users SET phone=? WHERE user_id=?", (contact.phone_number, user_id))
            conn.commit()

        update.message.reply_text(
            "📍 <b>Manzilingizni kiriting:</b>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove()
        )
        return STATE_ORDER_ADDRESS

    else:
        phone = safe_str(update.message.text)
        if not validate_phone(phone):
            update.message.reply_text("❌ Noto'g'ri format. Qayta kiriting (masalan: +998901234567):")
            return STATE_ORDER_PHONE

        context.user_data['order_phone'] = phone
        with get_db() as conn:
            conn.execute("UPDATE users SET phone=? WHERE user_id=?", (phone, user_id))
            conn.commit()

        update.message.reply_text(
            "📍 <b>Manzilingizni kiriting:</b>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove()
        )
        return STATE_ORDER_ADDRESS

def order_address_receive(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    if update.message.contact:
        contact = update.message.contact
        context.user_data['order_address'] = "Kontakt orqali yuborilgan"

        if ADMIN_ID:
            try:
                context.bot.send_message(
                    ADMIN_ID,
                    f"📱 <b>Yangi profil ulashdi</b>\n"
                    f"👤 Ism: {contact.first_name}\n"
                    f"📞 Telefon: {contact.phone_number}\n"
                    f"🆔 ID: {user_id}\n"
                    f"👤 Profil: <a href='tg://user?id={user_id}'>Yozish</a>",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Admin xabar yuborishda xatolik: {e}")

        with get_db() as conn:
            conn.execute("UPDATE users SET phone=? WHERE user_id=?", (contact.phone_number, user_id))
            conn.commit()
    else:
        address = safe_str(update.message.text)
        if len(address) < 3:
            update.message.reply_text("❌ Manzil juda qisqa. Qayta kiriting:")
            return STATE_ORDER_ADDRESS
        context.user_data['order_address'] = address
        with get_db() as conn:
            conn.execute("UPDATE users SET address=? WHERE user_id=?", (address, user_id))
            conn.commit()

    # Buyurtmani saqlash
    name = context.user_data.get('order_name', '')
    phone = context.user_data.get('order_phone', '')
    address = context.user_data.get('order_address', '')
    items = context.user_data.get('order_items', '')

    with get_db() as conn:
        conn.execute("""
            INSERT INTO orders (user_id, items, status, created_at)
            VALUES (?, ?, ?, ?)
        """, (user_id, items, "yangi", datetime.now().isoformat()))
        order_id = conn.lastrowid

        conn.execute("UPDATE users SET total_orders = total_orders + 1 WHERE user_id=?", (user_id,))

        # Referral tekshirish
        cur = conn.execute("SELECT referred_by, total_orders FROM users WHERE user_id=?", (user_id,))
        row = cur.fetchone()
        if row and row['referred_by'] and row['total_orders'] == 0:
            add_discount(row['referred_by'])
            add_discount(user_id)
            try:
                context.bot.send_message(
                    row['referred_by'],
                    "🎉 Siz taklif qilgan do'stingiz birinchi buyurtmasini berdi! Endi siz chegirmaga ega bo'ldingiz."
                )
            except:
                pass
        conn.commit()

    # Admin ga buyurtma xabari
    if ADMIN_ID:
        try:
            admin_message = (
                f"🆕 <b>YANGI BUYURTMA!</b>\n\n"
                f"👤 <b>Mijoz:</b>\n"
                f"   Ism: {name}\n"
                f"   Telefon: {phone}\n"
                f"   Manzil: {address}\n"
                f"   ID: {user_id}\n"
                f"   Profil: <a href='tg://user?id={user_id}'>Yozish</a>\n\n"
                f"📦 <b>Buyurtma:</b>\n{items}\n\n"
                f"🔢 Buyurtma №: {order_id}"
            )
            context.bot.send_message(ADMIN_ID, admin_message, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Admin xabar yuborishda xatolik: {e}")

    # Foydalanuvchiga tasdiq xabari
    context.user_data.clear()
    update.message.reply_text(
        f"✅ <b>Buyurtmangiz qabul qilindi!</b>\n\n"
        f"Tez orada admin siz bilan bog'lanadi.\n\n"
        f"<i>Yoriyev Market tomonidan sizga rahmat! Botimizdan foydalanganingiz uchun tashakkur.</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu"),
            InlineKeyboardButton("🔄 /start", callback_data="restart")
        ]])
    )
    return ConversationHandler.END

# ==================== AKSIYALAR ====================
@require_subscription
def show_promotion(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    with get_db() as conn:
        cur = conn.execute("SELECT text FROM promotions WHERE id=1")
        row = cur.fetchone()
        promo_text = row['text'] if row else "Aksiyalar mavjud emas."

    text = (
        f"📢 <b>Aksiyalar</b>\n\n"
        f"{promo_text}\n\n"
        f"👉 @{CHANNEL.lstrip('@')}"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL.lstrip('@')}"),
        InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")
    ]])
    query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

# ==================== HAMKORLAR ====================
@require_subscription
def partners(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    text = (
        "🤝 <b>Hamkorlarimiz</b>\n\n"
        "Biz bilan hamkorlik qilayotgan tashkilotlar va do'konlar:\n\n"
        f"👉 <a href='{HAMKORLAR_KANAL}'>Hamkorlar kanali</a>"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📢 Kanalga o'tish", url=HAMKORLAR_KANAL),
        InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")
    ]])
    query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

# ==================== BIZ HAQIMIZDA ====================
@require_subscription
def about(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    text = (
        "📌 <b>Biz haqimizda</b>\n\n"
        "Yoriyev Market – Peshku tumanidagi eng arzon va sifatli meva-sabzavotlar yetkazib berish xizmati.\n\n"
        "Manzil: Buxoro, Peshku, Chalmagadoy qishlog'i (Paynet ro'parasi)\n"
        "Telefon: +998883092500\n\n"
        f"👉 Batafsil: <a href='{BIZ_HAQIMIZDA_KANAL}'>Kanalimiz</a>"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📢 Kanalga o'tish", url=BIZ_HAQIMIZDA_KANAL),
        InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")
    ]])
    query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

# ==================== ADMIN BILAN BOG'LANISH ====================
@require_subscription
def admin_contact(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Admin profili", url=f"https://t.me/{ADMIN_USERNAME}")],
        [InlineKeyboardButton("📞 Telefon qilish", url=f"tel:{ADMIN_PHONE}")],
        [InlineKeyboardButton("✍️ Xabar yozish", url=f"https://t.me/{ADMIN_USERNAME}")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ])

    query.edit_message_text(
        "📞 <b>Admin bilan bog'lanish</b>\n\n"
        f"Admin: @{ADMIN_USERNAME}\n"
        f"Tel: {ADMIN_PHONE}\n\n"
        "Quyidagi tugmalar orqali admin bilan bog'lanishingiz mumkin:",
        parse_mode="HTML",
        reply_markup=keyboard
    )

# ==================== SHIKOYAT / TAKLIF ====================
@require_subscription
def complaint_start(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚠️ Shikoyat", callback_data="complaint_type")],
        [InlineKeyboardButton("💡 Taklif", callback_data="suggestion_type")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ])
    query.edit_message_text(
        "📝 <b>Shikoyat yoki taklif?</b>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

def complaint_type(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        "⚠️ <b>Shikoyatingizni yozing:</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Bekor qilish", callback_data="main_menu")
        ]])
    )
    return STATE_COMPLAINT_TEXT

def suggestion_type(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        "💡 <b>Taklifingizni yozing:</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Bekor qilish", callback_data="main_menu")
        ]])
    )
    return STATE_SUGGESTION_TEXT

def complaint_receive(update: Update, context: CallbackContext):
    text = safe_str(update.message.text)
    user_id = update.effective_user.id

    if len(text) < 3:
        update.message.reply_text("❌ Xabar juda qisqa. Qayta kiriting:")
        return STATE_COMPLAINT_TEXT

    with get_db() as conn:
        conn.execute("INSERT INTO complaints (user_id, text, type, created_at) VALUES (?, ?, ?, ?)",
                     (user_id, text, "shikoyat", datetime.now().isoformat()))
        conn.commit()

    if ADMIN_ID:
        try:
            admin_message = (
                f"⚠️ <b>YANGI SHIKOYAT</b>\n\n"
                f"👤 <b>Mijoz:</b>\n"
                f"   ID: {user_id}\n"
                f"   Profil: <a href='tg://user?id={user_id}'>Yozish</a>\n\n"
                f"📝 <b>Xabar:</b>\n{text}"
            )
            context.bot.send_message(ADMIN_ID, admin_message, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Admin xabar yuborishda xatolik: {e}")

    update.message.reply_text(
        "✅ <b>Shikoyatingiz qabul qilindi!</b>\n\n"
        "Tez orada admin siz bilan bog'lanadi.\n\n"
        f"<i>Yoriyev Market tomonidan sizga rahmat!</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")
        ]])
    )
    return ConversationHandler.END

def suggestion_receive(update: Update, context: CallbackContext):
    text = safe_str(update.message.text)
    user_id = update.effective_user.id

    if len(text) < 3:
        update.message.reply_text("❌ Xabar juda qisqa. Qayta kiriting:")
        return STATE_SUGGESTION_TEXT

    with get_db() as conn:
        conn.execute("INSERT INTO complaints (user_id, text, type, created_at) VALUES (?, ?, ?, ?)",
                     (user_id, text, "taklif", datetime.now().isoformat()))
        conn.commit()

    if ADMIN_ID:
        try:
            admin_message = (
                f"💡 <b>YANGI TAKLIF</b>\n\n"
                f"👤 <b>Mijoz:</b>\n"
                f"   ID: {user_id}\n"
                f"   Profil: <a href='tg://user?id={user_id}'>Yozish</a>\n\n"
                f"📝 <b>Xabar:</b>\n{text}"
            )
            context.bot.send_message(ADMIN_ID, admin_message, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Admin xabar yuborishda xatolik: {e}")

    update.message.reply_text(
        "✅ <b>Taklifingiz qabul qilindi!</b>\n\n"
        "Fikringiz uchun katta rahmat!\n\n"
        f"<i>Yoriyev Market tomonidan sizga rahmat!</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")
        ]])
    )
    return ConversationHandler.END

# ==================== TAKLIF QILISH (REFERRAL) ====================
@require_subscription
def referral_info(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"

    with get_db() as conn:
        cur = conn.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (user_id,))
        count = cur.fetchone()[0]
        cur = conn.execute("SELECT discount_count FROM users WHERE user_id=?", (user_id,))
        discount = cur.fetchone()[0]

    text = (
        "💡 <b>Taklif qilish tizimi</b>\n\n"
        "Do'stlaringizni taklif qiling va chegirmalar oling!\n\n"
        "<b>Qanday ishlaydi:</b>\n"
        "1️⃣ Havolani do'stingizga yuboring\n"
        "2️⃣ Do'stingiz havola orqali birinchi buyurtma bersa\n"
        "3️⃣ Siz va do'stingiz 1 tadan chegirma olasiz\n\n"
        f"🔗 <b>Sizning havolangiz:</b>\n<code>{ref_link}</code>\n\n"
        f"📊 Taklif qilganlaringiz: {count}\n"
        f"💰 Chegirmalaringiz: {discount}"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")
    ]])
    query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

# ==================== TO'LOV TIZIMI ====================
@require_subscription
def payment_info(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    text = (
        "💳 <b>To'lov tizimi</b>\n\n"
        "Mahsulot sizga yoqsa, keyin to'lov qilasiz.\n"
        "Buyurtma berish jarayonida to'lov haqida admin bilan kelishasiz.\n\n"
        "💡 To'lov usullari: naqd, Click, Payme, Apelsin."
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")
    ]])
    query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

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
    update.message.reply_text("⚙️ <b>Admin panel</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

def admin_stats(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    with get_db() as conn:
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        new_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE status='yangi'").fetchone()[0]
        today_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE date(created_at)=date('now')").fetchone()[0]
        complaints = conn.execute("SELECT COUNT(*) FROM complaints WHERE type='shikoyat'").fetchone()[0]
        suggestions = conn.execute("SELECT COUNT(*) FROM complaints WHERE type='taklif'").fetchone()[0]

    text = (
        f"📊 <b>Statistika</b>\n\n"
        f"👥 Jami foydalanuvchilar: {users}\n"
        f"🆕 Yangi buyurtmalar: {new_orders}\n"
        f"📅 Bugungi buyurtmalar: {today_orders}\n"
        f"⚠️ Shikoyatlar: {complaints}\n"
        f"💡 Takliflar: {suggestions}"
    )
    query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
    ]]))

def admin_orders(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    with get_db() as conn:
        cur = conn.execute("SELECT * FROM orders WHERE status='yangi' ORDER BY id DESC")
        orders = cur.fetchall()

    if not orders:
        query.edit_message_text(
            "📦 Yangi buyurtmalar yoʻq.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
            ]])
        )
        return

    text = "📦 <b>Yangi buyurtmalar:</b>\n\n"
    for o in orders:
        user = conn.execute("SELECT * FROM users WHERE user_id=?", (o['user_id'],)).fetchone()
        mijoz_ism = user['first_name'] if user else "Noma'lum"
        mijoz_tel = user['phone'] if user else "Yo'q"
        text += (
            f"🔢 <b>Buyurtma №{o['id']}</b>\n"
            f"👤 Mijoz: {mijoz_ism}\n"
            f"📞 Tel: {mijoz_tel}\n"
            f"🆔 ID: {o['user_id']}\n"
            f"📦 Mahsulotlar: {o['items']}\n"
            f"📅 Sana: {o['created_at'][:16]}\n"
            f"👤 Profil: <a href='tg://user?id={o['user_id']}'>Yozish</a>\n\n"
        )

    query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
    ]]))

def admin_complaints(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    with get_db() as conn:
        cur = conn.execute("SELECT * FROM complaints WHERE type='shikoyat' ORDER BY id DESC LIMIT 10")
        complaints = cur.fetchall()

    if not complaints:
        query.edit_message_text(
            "⚠️ Shikoyatlar yoʻq.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
            ]])
        )
        return

    text = "⚠️ <b>Shikoyatlar:</b>\n\n"
    for c in complaints:
        user = conn.execute("SELECT * FROM users WHERE user_id=?", (c['user_id'],)).fetchone()
        mijoz_ism = user['first_name'] if user else "Noma'lum"
        mijoz_tel = user['phone'] if user else "Yo'q"
        text += (
            f"🆔 <b>Mijoz ID:</b> {c['user_id']}\n"
            f"👤 Ism: {mijoz_ism}\n"
            f"📞 Tel: {mijoz_tel}\n"
            f"📝 Xabar: {c['text']}\n"
            f"📅 Sana: {c['created_at'][:16]}\n"
            f"👤 Profil: <a href='tg://user?id={c['user_id']}'>Yozish</a>\n\n"
        )

    query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
    ]]))

def admin_suggestions(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    with get_db() as conn:
        cur = conn.execute("SELECT * FROM complaints WHERE type='taklif' ORDER BY id DESC LIMIT 10")
        suggestions = cur.fetchall()

    if not suggestions:
        query.edit_message_text(
            "💡 Takliflar yoʻq.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
            ]])
        )
        return

    text = "💡 <b>Takliflar:</b>\n\n"
    for s in suggestions:
        user = conn.execute("SELECT * FROM users WHERE user_id=?", (s['user_id'],)).fetchone()
        mijoz_ism = user['first_name'] if user else "Noma'lum"
        mijoz_tel = user['phone'] if user else "Yo'q"
        text += (
            f"🆔 <b>Mijoz ID:</b> {s['user_id']}\n"
            f"👤 Ism: {mijoz_ism}\n"
            f"📞 Tel: {mijoz_tel}\n"
            f"📝 Taklif: {s['text']}\n"
            f"📅 Sana: {s['created_at'][:16]}\n"
            f"👤 Profil: <a href='tg://user?id={s['user_id']}'>Yozish</a>\n\n"
        )

    query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
    ]]))

def admin_promo_start(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        "✍️ <b>Yangi aksiya matnini yozing:</b>",
        parse_mode="HTML",
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
        "✍️ <b>Barcha foydalanuvchilarga yuboriladigan xabarni yozing:</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Bekor qilish", callback_data="admin_panel")
        ]])
    )
    return STATE_ADMIN_BROADCAST

def admin_broadcast_receive(update: Update, context: CallbackContext):
    text = update.message.text
    with get_db() as conn:
        cur = conn.execute("SELECT user_id FROM users")
        users = cur.fetchall()

    sent = 0
    for (uid,) in users:
        try:
            context.bot.send_message(uid, text)
            sent += 1
        except Exception as e:
            logger.error(f"Xabar yuborishda xatolik (user {uid}): {e}")

    update.message.reply_text(f"✅ Xabar {sent} ta foydalanuvchiga yuborildi.")
    return ConversationHandler.END

# ==================== QAYTA ISHGA TUSHIRISH ====================
def restart(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    start(update, context)

# ==================== CALLBACK HANDLER ====================
def callback_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    if data not in ["check_sub", "main_menu", "restart"]:
        if not check_subscription(context.bot, user_id):
            query.answer("⚠️ Avval kanalga a'zo bo'ling!", show_alert=True)
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL.lstrip('@')}"),
                InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")
            ]])
            query.edit_message_text(
                "🚫 Botdan foydalanish uchun kanalimizga a'zo bo'ling!",
                parse_mode="HTML",
                reply_markup=keyboard
            )
            return

    if data == "check_sub":
        check_sub_callback(update, context)
    elif data == "main_menu":
        show_main_menu(update, context, edit=True)
    elif data == "restart":
        restart(update, context)
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
    elif data == "menu_complaint":
        complaint_start(update, context)
    elif data == "complaint_type":
        complaint_type(update, context)
    elif data == "suggestion_type":
        suggestion_type(update, context)
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

    # Conversation handlers
    order_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(order_start, pattern="^order_start$")],
        states={
            STATE_PRODUCT_TEXT: [MessageHandler(Filters.text & ~Filters.command, handle_product_text)],
            STATE_ORDER_NAME: [MessageHandler(Filters.all, order_name_receive)],
            STATE_ORDER_PHONE: [MessageHandler(Filters.all, order_phone_receive)],
            STATE_ORDER_ADDRESS: [MessageHandler(Filters.all, order_address_receive)],
        },
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(show_main_menu, pattern="^main_menu$")],
    )

    complaint_text_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(complaint_type, pattern="^complaint_type$")],
        states={
            STATE_COMPLAINT_TEXT: [MessageHandler(Filters.text & ~Filters.command, complaint_receive)],
        },
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(show_main_menu, pattern="^main_menu$")],
    )

    suggestion_text_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(suggestion_type, pattern="^suggestion_type$")],
        states={
            STATE_SUGGESTION_TEXT: [MessageHandler(Filters.text & ~Filters.command, suggestion_receive)],
        },
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(show_main_menu, pattern="^main_menu$")],
    )

    admin_promo_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_promo_start, pattern="^admin_promo$")],
        states={
            STATE_ADMIN_PROMO: [MessageHandler(Filters.text & ~Filters.command, admin_promo_receive)],
        },
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(show_main_menu, pattern="^main_menu$")],
    )

    admin_broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_broadcast_start, pattern="^admin_broadcast$")],
        states={
            STATE_ADMIN_BROADCAST: [MessageHandler(Filters.text & ~Filters.command, admin_broadcast_receive)],
        },
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(show_main_menu, pattern="^main_menu$")],
    )

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("admin", admin_panel))
    dp.add_handler(order_conv)
    dp.add_handler(complaint_text_conv)
    dp.add_handler(suggestion_text_conv)
    dp.add_handler(admin_promo_conv)
    dp.add_handler(admin_broadcast_conv)
    dp.add_handler(CallbackQueryHandler(callback_handler))

    updater.start_polling()
    logger.info("✅ Bot ishga tushdi!")
    updater.idle()

if __name__ == "__main__":
    main()
