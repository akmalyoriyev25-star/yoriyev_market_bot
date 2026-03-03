# -*- coding: utf-8 -*-
"""YORIYEV MARKET BOT – Ultra zamonaviy versiya (kanal talabi bilan)"""

import logging
import os
import sqlite3
import re
from datetime import datetime
from typing import Optional, Dict, List, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater, CommandHandler, CallbackQueryHandler, MessageHandler,
    Filters, CallbackContext, ConversationHandler
)

# ==================== KONFIGURATSIYA ====================
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN environment variable topilmadi!")

CHANNEL = os.environ.get("CHANNEL_USERNAME", "@yoriyev_market")  # Kanal username
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))                 # Admin Telegram ID
BOT_USERNAME = os.environ.get("BOT_USERNAME", "Yoriyev_market_bot")  # Bot username (referral havola uchun)

# ==================== LOGGING ====================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== MA'LUMOTLAR BAZASI ====================
DB_PATH = "yoriyev_market.db"

def get_db():
    """Ma'lumotlar bazasi ulanishini qaytaradi."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Jadvallarni yaratish."""
    with get_db() as conn:
        cursor = conn.cursor()
        # Foydalanuvchilar
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT,
                username TEXT,
                phone TEXT,
                address TEXT,
                location TEXT,
                registered_at TEXT,
                last_active TEXT,
                referred_by INTEGER,
                discount_count INTEGER DEFAULT 0,
                total_orders INTEGER DEFAULT 0
            )
        """)
        # Buyurtmalar
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                items TEXT,
                status TEXT DEFAULT 'yangi',
                created_at TEXT,
                admin_note TEXT
            )
        """)
        # Mahsulot takliflari
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                text TEXT,
                created_at TEXT
            )
        """)
        # Shikoyatlar
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS complaints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                text TEXT,
                created_at TEXT
            )
        """)
        # Aksiyalar
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS promotions (
                id INTEGER PRIMARY KEY CHECK (id=1),
                text TEXT
            )
        """)
        cursor.execute("INSERT OR IGNORE INTO promotions (id, text) VALUES (1, '🔥 Hozircha maxsus aksiyalar yoʻq')")
        conn.commit()

init_db()

# ==================== MAHSULOTLAR RO'YXATI ====================
SABZAVOTLAR = [
    "🥔 Kartoshka", "🧅 Piyoz", "🥕 Sabzi", "Sholgʻom", "🥒 Bodring", "🍅 Pomidor",
    "🌶️ Turp", "Rediska", "🧄 Chesnok", "🌶️ Qalampir", "🍆 Baqlajon", "🎃 Qovoq",
    "🥬 Karam", "🥦 Brokkoli", "🌿 Gulkaram", "Lavlagi", "Selderey", "Ismaloq",
    "Petrushka", "Ukrop", "Rayhon", "Shivit", "Qatiq oʻsimlik", "Hul", "Noʻxat",
    "Mosh", "Loviya", "Bodom", "Yongʻoq", "Qovoqcha", "Patisson", "Bamya",
    "Rokambol", "Qizilcha"
]

MEVALAR = [
    "🍎 Olma", "🍐 Nok", "🍌 Banan", "🍊 Mandarin", "🍊 Apelsin", "🍋 Limon",
    "🍊 Greypfrut", "🍎 Anor", "🍎 Xurmo", "🍇 Uzum", "🍒 Gilos", "Olcha",
    "🍑 Shaftoli", "Oʻrik", "🍍 Ananas", "🥝 Kivi", "🥭 Mango", "🥑 Avakado",
    "🍓 Qulupnay", "Malina", "Smorodina", "Bektoshi", "Tut", "Jiyda", "Olxoʻri",
    "Shaptoli", "Behi", "Yeryongʻoq", "Pista", "Findiq", "Kakos", "Papayya", "Guvayva"
]

POLIZ = [
    "🍉 Tarvuz", "🍈 Qovun", "🎃 Qovoq", "🥒 Bodring", "Qovoqcha", "Patisson", "Hul"
]

BARCHA_MAHSULOTLAR = SABZAVOTLAR + MEVALAR + POLIZ

KATEGORIYALAR = {
    "sabzavot": SABZAVOTLAR,
    "meva": MEVALAR,
    "poliz": POLIZ
}

# ==================== HOLATLAR (ConversationHandler uchun) ====================
(
    STATE_CUSTOM_PRODUCT,
    STATE_CUSTOM_QUANTITY,
    STATE_MULTI_SELECT,
    STATE_SUGGESTION,
    STATE_COMPLAINT,
    STATE_ORDER_NAME,
    STATE_ORDER_PHONE,
    STATE_ORDER_ADDRESS,
    STATE_ADMIN_PROMO,
    STATE_ADMIN_BROADCAST
) = range(10)

# ==================== YORDAMCHI FUNKSIYALAR ====================
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

def safe_str(text: str) -> str:
    return re.sub(r'[<>]', '', text) if text else ''

def validate_phone(phone: str) -> bool:
    return re.match(r'^\+998\d{9}$', phone) is not None

def update_user_activity(user_id: int):
    with get_db() as conn:
        conn.execute("UPDATE users SET last_active = ? WHERE user_id = ?",
                     (datetime.now().isoformat(), user_id))
        conn.commit()

def get_or_create_user(user_id: int, first_name: str, username: str = None, referred_by: int = None):
    with get_db() as conn:
        cur = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cur.fetchone()
        if not user:
            conn.execute("""
                INSERT INTO users (user_id, first_name, username, registered_at, last_active, referred_by)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, safe_str(first_name), username, datetime.now().isoformat(),
                  datetime.now().isoformat(), referred_by))
            conn.commit()
            return None  # yangi
        else:
            update_user_activity(user_id)
            return user

def add_discount(user_id: int, count: int = 1):
    with get_db() as conn:
        conn.execute("UPDATE users SET discount_count = discount_count + ? WHERE user_id = ?",
                     (count, user_id))
        conn.commit()

# ==================== KANAL TEKSHIRISH ====================
def check_subscription(bot, user_id: int) -> bool:
    """Foydalanuvchi kanalga a'zo yoki yo'qligini tekshiradi."""
    try:
        member = bot.get_chat_member(chat_id=CHANNEL, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Kanal tekshirishda xatolik: {e}")
        return False

def require_subscription(func):
    """Dekorator – kanalga a'zolikni talab qiladi."""
    def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
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
                    "🚫 *Botdan foydalanish uchun kanalimizga a'zo bo'ling!*",
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
            elif update.callback_query:
                update.callback_query.edit_message_text(
                    "🚫 *Botdan foydalanish uchun kanalimizga a'zo bo'ling!*",
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
            return
    return wrapper

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
            f"🌟 *Assalomu alaykum {user.first_name}!*\n\nBotdan foydalanish uchun kanalimizga a'zo bo'ling.",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

def check_sub_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    if check_subscription(context.bot, user_id):
        update_user_activity(user_id)
        query.edit_message_text("✅ *A'zo bo'lgansiz!*", parse_mode="Markdown")
        show_main_menu(update, context, edit=True)
    else:
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL.lstrip('@')}"),
            InlineKeyboardButton("🔄 Qayta tekshirish", callback_data="check_sub")
        ]])
        query.edit_message_text(
            "❌ *Siz kanalga a'zo emassiz.* Iltimos, avval a'zo bo'ling.",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

def show_main_menu(update: Update, context: CallbackContext, edit: bool = False):
    keyboard = [
        [InlineKeyboardButton("🛒 Mahsulotlar", callback_data="menu_products")],
        [InlineKeyboardButton("📢 Aksiyalar", callback_data="menu_promo")],
        [InlineKeyboardButton("🛍 Savatim", callback_data="menu_cart")],
        [InlineKeyboardButton("👤 Kabinet", callback_data="menu_cabinet")],
        [InlineKeyboardButton("📞 Admin bilan bogʻlanish", callback_data="menu_contact")],
        [InlineKeyboardButton("⚠️ Shikoyat / Taklif", callback_data="menu_complaint")],
        [InlineKeyboardButton("💡 Taklif qilish", callback_data="menu_referral")]
    ]
    text = "🏠 *Bosh menyu*"
    if edit:
        update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        update.message.reply_text(
            text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ==================== MAHSULOTLAR ====================
@require_subscription
def products_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    keyboard = [
        [InlineKeyboardButton("🥕 Sabzavotlar", callback_data="cat_sabzavot")],
        [InlineKeyboardButton("🍎 Mevalar", callback_data="cat_meva")],
        [InlineKeyboardButton("🍉 Poliz ekinlari", callback_data="cat_poliz")],
        [InlineKeyboardButton("📦 Kanalda koʻrgan mahsulot", callback_data="custom_product")],
        [InlineKeyboardButton("✅ Bir nechta tanlash", callback_data="multi_select")],
        [InlineKeyboardButton("💭 Yangi mahsulot taklifi", callback_data="suggestion")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ]
    query.edit_message_text(
        "🛒 *Kategoriyani tanlang:*", parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@require_subscription
def show_category(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    cat = query.data.split("_")[1]  # cat_sabzavot -> sabzavot
    products = KATEGORIYALAR.get(cat, [])
    keyboard = []
    for p in products:
        keyboard.append([InlineKeyboardButton(p, callback_data=f"add_{cat}_{p}")])
    keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_products")])
    query.edit_message_text(
        f"📋 *{cat.upper()} mahsulotlari*\n\n💡 Narxlar kanalda.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@require_subscription
def add_to_cart(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    data = query.data.split("_")  # add_sabzavot_Kartoshka
    cat = data[1]
    product = data[2]
    user_id = query.from_user.id
    cart = context.user_data.setdefault("cart", {})
    cart[product] = cart.get(product, 0) + 1
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Savatni koʻrish", callback_data="menu_cart")],
        [InlineKeyboardButton("⬅️ Davom etish", callback_data=f"cat_{cat}")]
    ])
    query.edit_message_text(
        f"✅ *{product}* savatga qoʻshildi!",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# ==================== QO'SHIMCHA MAHSULOT ====================
@require_subscription
def custom_product_start(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        "📝 *Kanalda koʻrgan mahsulot nomini yozing:*\n\nMasalan: Anor",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Bekor qilish", callback_data="menu_products")
        ]])
    )
    return STATE_CUSTOM_PRODUCT

def custom_product_receive(update: Update, context: CallbackContext):
    text = safe_str(update.message.text)
    if len(text) < 2:
        update.message.reply_text("❌ Mahsulot nomi juda qisqa. Qayta kiriting yoki bekor qiling:")
        return STATE_CUSTOM_PRODUCT
    context.user_data["custom_product"] = text
    update.message.reply_text(
        "🔢 *Nechta kerak?*\nMasalan: 2 kg yoki 5 dona",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Bekor qilish", callback_data="menu_products")
        ]])
    )
    return STATE_CUSTOM_QUANTITY

def custom_quantity_receive(update: Update, context: CallbackContext):
    quantity = safe_str(update.message.text)
    product = context.user_data.get("custom_product")
    if not product:
        update.message.reply_text("❌ Xatolik. Qaytadan urinib koʻring.")
        return ConversationHandler.END
    cart = context.user_data.setdefault("cart", {})
    cart[f"{product} ({quantity})"] = 1
    context.user_data.pop("custom_product", None)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Savatni koʻrish", callback_data="menu_cart")],
        [InlineKeyboardButton("⬅️ Mahsulotlar", callback_data="menu_products")]
    ])
    update.message.reply_text(
        f"✅ *{product}* savatga qoʻshildi!",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    return ConversationHandler.END

# ==================== BIR NECHTA TANLASH ====================
@require_subscription
def multi_select_start(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        "✍️ *Bir nechta mahsulotni vergul bilan ajratib yozing:*\n\nMasalan: `Kartoshka, Piyoz, Sabzi`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Bekor qilish", callback_data="menu_products")
        ]])
    )
    return STATE_MULTI_SELECT

def multi_select_receive(update: Update, context: CallbackContext):
    text = safe_str(update.message.text)
    items = [x.strip() for x in text.split(",") if x.strip()]
    if not items:
        update.message.reply_text("❌ Hech qanday mahsulot kiritilmadi. Qaytadan urinib koʻring:")
        return STATE_MULTI_SELECT
    cart = context.user_data.setdefault("cart", {})
    for item in items:
        cart[item] = cart.get(item, 0) + 1
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Savatni koʻrish", callback_data="menu_cart")],
        [InlineKeyboardButton("⬅️ Mahsulotlar", callback_data="menu_products")]
    ])
    update.message.reply_text(
        f"✅ {len(items)} ta mahsulot savatga qoʻshildi!",
        reply_markup=keyboard
    )
    return ConversationHandler.END

# ==================== YANGI MAHSULOT TAKLIFI ====================
@require_subscription
def suggestion_start(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        "💡 *Yangi mahsulot taklif qiling:*\nQanday mahsulot qo'shishimizni xohlaysiz?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Bekor qilish", callback_data="menu_products")
        ]])
    )
    return STATE_SUGGESTION

def suggestion_receive(update: Update, context: CallbackContext):
    text = safe_str(update.message.text)
    if len(text) < 3:
        update.message.reply_text("❌ Taklif juda qisqa. Qayta kiriting:")
        return STATE_SUGGESTION
    user_id = update.effective_user.id
    with get_db() as conn:
        conn.execute("INSERT INTO suggestions (user_id, text, created_at) VALUES (?, ?, ?)",
                     (user_id, text, datetime.now().isoformat()))
        conn.commit()
    if ADMIN_ID:
        try:
            context.bot.send_message(
                ADMIN_ID,
                f"💡 *Yangi mahsulot taklifi*\n👤 Foydalanuvchi: {user_id}\n📝 {text}",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Admin xabar yuborishda xatolik: {e}")
    update.message.reply_text(
        "✅ Taklifingiz qabul qilindi! Rahmat.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Asosiy menyu", callback_data="main_menu")
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
        text = row["text"] if row else "Aksiyalar mavjud emas."
    query.edit_message_text(
        f"📢 *Aksiyalar*\n\n{text}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")
        ]])
    )

# ==================== SAVAT ====================
@require_subscription
def view_cart(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    cart = context.user_data.get("cart", {})
    if not cart:
        query.edit_message_text(
            "🛒 *Savat boʻsh.*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Mahsulotlar", callback_data="menu_products")
            ]])
        )
        return
    lines = [f"• {item} x {count}" for item, count in cart.items()]
    text = "🛒 *Savat*\n\n" + "\n".join(lines)
    keyboard = [
        [InlineKeyboardButton("📦 Buyurtma berish", callback_data="order_start")],
        [InlineKeyboardButton("🗑 Savatni tozalash", callback_data="cart_clear")],
        [InlineKeyboardButton("⬅️ Mahsulotlar", callback_data="menu_products")]
    ]
    query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

@require_subscription
def clear_cart(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    context.user_data.pop("cart", None)
    query.edit_message_text(
        "🗑 *Savat tozalandi.*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Mahsulotlar", callback_data="menu_products")
        ]])
    )

# ==================== BUYURTMA ====================
@require_subscription
def order_start(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    if "cart" not in context.user_data or not context.user_data["cart"]:
        query.edit_message_text("❌ *Savat boʻsh.*")
        return
    query.edit_message_text(
        "📝 *Buyurtma berish*\n\nIltimos, ismingizni kiriting:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Bekor qilish", callback_data="main_menu")
        ]])
    )
    return STATE_ORDER_NAME

def order_name_receive(update: Update, context: CallbackContext):
    text = safe_str(update.message.text)
    if len(text) < 2:
        update.message.reply_text("❌ Ism juda qisqa. Qayta kiriting:")
        return STATE_ORDER_NAME
    context.user_data["order_name"] = text
    update.message.reply_text(
        "📞 *Telefon raqamingizni kiriting:*\nFormat: +998901234567",
        parse_mode="Markdown"
    )
    return STATE_ORDER_PHONE

def order_phone_receive(update: Update, context: CallbackContext):
    text = safe_str(update.message.text)
    if not validate_phone(text):
        update.message.reply_text("❌ Notoʻgʻri format. Qayta kiriting:")
        return STATE_ORDER_PHONE
    context.user_data["order_phone"] = text
    update.message.reply_text(
        "📍 *Manzilingizni kiriting:* (koʻcha, uy raqami)",
        parse_mode="Markdown"
    )
    return STATE_ORDER_ADDRESS

def order_address_receive(update: Update, context: CallbackContext):
    text = safe_str(update.message.text)
    if len(text) < 5:
        update.message.reply_text("❌ Manzil juda qisqa. Qayta kiriting:")
        return STATE_ORDER_ADDRESS
    user_id = update.effective_user.id
    name = context.user_data["order_name"]
    phone = context.user_data["order_phone"]
    address = text
    cart = context.user_data.get("cart", {})
    items_str = ", ".join([f"{item} ({count})" for item, count in cart.items()])

    with get_db() as conn:
        # Buyurtmani saqlash
        conn.execute("""
            INSERT INTO orders (user_id, items, status, created_at)
            VALUES (?, ?, ?, ?)
        """, (user_id, items_str, "yangi", datetime.now().isoformat()))
        order_id = conn.lastrowid

        # Foydalanuvchi ma'lumotlarini yangilash
        conn.execute("""
            UPDATE users SET phone=?, address=?, last_active=?, total_orders = total_orders + 1
            WHERE user_id=?
        """, (phone, address, datetime.now().isoformat(), user_id))

        # Referral tekshirish: birinchi buyurtma bo'lsa va referred_by bo'lsa
        cur = conn.execute("SELECT referred_by, total_orders FROM users WHERE user_id=?", (user_id,))
        row = cur.fetchone()
        if row and row["referred_by"] and row["total_orders"] == 0:
            # Birinchi buyurtma, refererga va yangi foydalanuvchiga chegirma
            add_discount(row["referred_by"])
            add_discount(user_id)

        conn.commit()

    context.user_data.pop("cart", None)
    context.user_data.pop("order_name", None)
    context.user_data.pop("order_phone", None)

    # Admin xabar
    if ADMIN_ID:
        try:
            context.bot.send_message(
                ADMIN_ID,
                f"🆕 *Yangi buyurtma!*\n\n"
                f"👤 Ism: {name}\n"
                f"📞 Tel: {phone}\n"
                f"📍 Manzil: {address}\n"
                f"🛍 Mahsulotlar: {items_str}\n"
                f"🆔 Buyurtma №: {order_id}",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Admin xabar yuborishda xatolik: {e}")

    update.message.reply_text(
        f"✅ *Buyurtmangiz qabul qilindi!*\n\n"
        f"Tez orada siz bilan bogʻlanamiz.\n"
        f"Buyurtma raqami: #{order_id}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")
        ]])
    )
    return ConversationHandler.END

# ==================== KABINET ====================
@require_subscription
def cabinet(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    with get_db() as conn:
        cur = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        user = cur.fetchone()
    if not user:
        query.edit_message_text("❌ Maʼlumot topilmadi.")
        return
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    text = (
        f"👤 *Kabinet*\n\n"
        f"Ism: {user['first_name']}\n"
        f"Telefon: {user['phone'] or 'yoʻq'}\n"
        f"Manzil: {user['address'] or 'yoʻq'}\n"
        f"Buyurtmalar: {user['total_orders']}\n"
        f"Chegirmalar: {user['discount_count']}\n\n"
        f"🔗 *Taklif havolangiz:*\n`{ref_link}`\n\n"
        "Doʻstingiz havola orqali birinchi buyurtma bersa, "
        "siz va doʻstingiz 1 tadan chegirma olasiz. Chegirma bilan mahsulotlarni "
        "kanaldagi narxlardan arzon olishingiz mumkin!"
    )
    keyboard = [
        [InlineKeyboardButton("📦 Buyurtmalarim", callback_data="my_orders")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ]
    query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

@require_subscription
def my_orders(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    with get_db() as conn:
        cur = conn.execute(
            "SELECT id, items, status, created_at FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 5",
            (user_id,)
        )
        orders = cur.fetchall()
    if not orders:
        query.edit_message_text(
            "Sizda hali buyurtmalar yoʻq.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_cabinet")
            ]])
        )
        return
    text = "📦 *Oxirgi buyurtmalar:*\n\n"
    for o in orders:
        text += f"#{o['id']}: {o['items'][:50]}...\n{o['status']} | {o['created_at'][:10]}\n\n"
    query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_cabinet")
    ]]))

@require_subscription
def referral_info(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    text = (
        "💡 *Taklif qilish tizimi*\n\n"
        "Doʻstlaringizni taklif qiling va chegirmalar oling!\n\n"
        "Qanday ishlaydi:\n"
        "1. Havolani doʻstingizga yuboring.\n"
        "2. Doʻstingiz havola orqali botga kirib, birinchi buyurtmasini bersa, siz va doʻstingiz 1 tadan chegirma olasiz.\n"
        "3. Chegirma bilan mahsulotlarni kanaldagi narxlardan arzon olishingiz mumkin.\n\n"
        f"🔗 *Sizning havolangiz:*\n`{ref_link}`"
    )
    query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")
        ]])
    )

# ==================== ADMIN BILAN BOG'LANISH ====================
@require_subscription
def admin_contact(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    admin_username = os.environ.get("ADMIN_USERNAME", "akmalyoriyev")
    query.edit_message_text(
        "📞 *Admin bilan bogʻlanish*\n\n"
        f"Admin: @{admin_username}\n"
        "Istalgan savol boʻyicha murojaat qiling.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")
        ]])
    )

# ==================== SHIKOYAT / TAKLIF ====================
@require_subscription
def complaint_start(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        "⚠️ *Shikoyat yoki taklifingizni yozing:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Bekor qilish", callback_data="main_menu")
        ]])
    )
    return STATE_COMPLAINT

def complaint_receive(update: Update, context: CallbackContext):
    text = safe_str(update.message.text)
    if len(text) < 5:
        update.message.reply_text("❌ Xabar juda qisqa. Qayta kiriting:")
        return STATE_COMPLAINT
    user_id = update.effective_user.id
    with get_db() as conn:
        conn.execute("INSERT INTO complaints (user_id, text, created_at) VALUES (?, ?, ?)",
                     (user_id, text, datetime.now().isoformat()))
        conn.commit()
    if ADMIN_ID:
        try:
            context.bot.send_message(
                ADMIN_ID,
                f"⚠️ *Yangi shikoyat/taklif*\n👤 Foydalanuvchi: {user_id}\n📝 {text}",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Admin xabar yuborishda xatolik: {e}")
    update.message.reply_text(
        "✅ Xabaringiz qabul qilindi! Rahmat.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Asosiy menyu", callback_data="main_menu")
        ]])
    )
    return ConversationHandler.END

# ==================== ADMIN PANEL ====================
def admin_panel(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ Siz admin emassiz.")
        return
    keyboard = [
        [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton("📦 Yangi buyurtmalar", callback_data="admin_orders")],
        [InlineKeyboardButton("💬 Takliflar", callback_data="admin_suggestions")],
        [InlineKeyboardButton("⚠️ Shikoyatlar", callback_data="admin_complaints")],
        [InlineKeyboardButton("📢 Aksiyani tahrirlash", callback_data="admin_promo")],
        [InlineKeyboardButton("📤 Xabar yuborish", callback_data="admin_broadcast")],
        [InlineKeyboardButton("⬅️ Yopish", callback_data="main_menu")]
    ]
    update.message.reply_text("⚙️ *Admin panel*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

def admin_stats(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    with get_db() as conn:
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        new_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE status='yangi'").fetchone()[0]
        today_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE date(created_at)=date('now')").fetchone()[0]
        suggestions = conn.execute("SELECT COUNT(*) FROM suggestions").fetchone()[0]
        complaints = conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
    text = (
        f"📊 *Statistika*\n\n"
        f"👥 Jami foydalanuvchilar: {users}\n"
        f"🆕 Yangi buyurtmalar: {new_orders}\n"
        f"📅 Bugungi buyurtmalar: {today_orders}\n"
        f"💬 Takliflar: {suggestions}\n"
        f"⚠️ Shikoyatlar: {complaints}"
    )
    query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
    ]]))

def admin_orders(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    with get_db() as conn:
        cur = conn.execute("SELECT id, user_id, items, created_at FROM orders WHERE status='yangi' ORDER BY id DESC LIMIT 10")
        orders = cur.fetchall()
    if not orders:
        query.edit_message_text("📦 Yangi buyurtmalar yoʻq.", reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
        ]]))
        return
    text = "📦 *Yangi buyurtmalar:*\n\n"
    for o in orders:
        text += f"#{o['id']} (User {o['user_id']}): {o['items'][:50]}...\n{o['created_at'][:10]}\n\n"
    query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
    ]]))

def admin_suggestions(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    with get_db() as conn:
        cur = conn.execute("SELECT id, user_id, text, created_at FROM suggestions ORDER BY id DESC LIMIT 10")
        rows = cur.fetchall()
    if not rows:
        query.edit_message_text("Takliflar yoʻq.", reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
        ]]))
        return
    text = "💬 *Takliflar:*\n\n"
    for r in rows:
        text += f"#{r['id']} (User {r['user_id']}): {r['text'][:50]}...\n{r['created_at'][:10]}\n\n"
    query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
    ]]))

def admin_complaints(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    with get_db() as conn:
        cur = conn.execute("SELECT id, user_id, text, created_at FROM complaints ORDER BY id DESC LIMIT 10")
        rows = cur.fetchall()
    if not rows:
        query.edit_message_text("Shikoyatlar yoʻq.", reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
        ]]))
        return
    text = "⚠️ *Shikoyatlar:*\n\n"
    for r in rows:
        text += f"#{r['id']} (User {r['user_id']}): {r['text'][:50]}...\n{r['created_at'][:10]}\n\n"
    query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
    ]]))

def admin_promo_start(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        "✍️ *Yangi aksiya matnini yozing:*",
        parse_mode="Markdown",
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
    update.message.reply_text("✅ Aksiya matni yangilandi!", reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ Admin panel", callback_data="admin_panel")
    ]]))
    return ConversationHandler.END

def admin_broadcast_start(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        "✍️ *Barcha foydalanuvchilarga yuboriladigan xabarni yozing:*",
        parse_mode="Markdown",
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

# ==================== CALLBACK HANDLER (asosiy) ====================
def callback_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    # Kanal tekshirishni talab qiladigan callbacklar (check_sub va main_menu bundan mustasno)
    if data not in ["check_sub", "main_menu"]:
        if not check_subscription(context.bot, user_id):
            query.answer("⚠️ Avval kanalga a'zo bo'ling!", show_alert=True)
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL.lstrip('@')}"),
                InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")
            ]])
            query.edit_message_text(
                "🚫 *Botdan foydalanish uchun kanalimizga a'zo bo'ling!*",
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            return

    if data == "check_sub":
        check_sub_callback(update, context)
    elif data == "main_menu":
        show_main_menu(update, context, edit=True)
    elif data == "menu_products":
        products_menu(update, context)
    elif data.startswith("cat_"):
        show_category(update, context)
    elif data.startswith("add_"):
        add_to_cart(update, context)
    elif data == "custom_product":
        context.user_data["state"] = STATE_CUSTOM_PRODUCT
        custom_product_start(update, context)
    elif data == "multi_select":
        context.user_data["state"] = STATE_MULTI_SELECT
        multi_select_start(update, context)
    elif data == "suggestion":
        context.user_data["state"] = STATE_SUGGESTION
        suggestion_start(update, context)
    elif data == "menu_promo":
        show_promotion(update, context)
    elif data == "menu_cart":
        view_cart(update, context)
    elif data == "cart_clear":
        clear_cart(update, context)
    elif data == "order_start":
        context.user_data["state"] = STATE_ORDER_NAME
        order_start(update, context)
    elif data == "menu_cabinet":
        cabinet(update, context)
    elif data == "my_orders":
        my_orders(update, context)
    elif data == "menu_referral":
        referral_info(update, context)
    elif data == "menu_contact":
        admin_contact(update, context)
    elif data == "menu_complaint":
        context.user_data["state"] = STATE_COMPLAINT
        complaint_start(update, context)
    elif data.startswith("admin_"):
        if not is_admin(user_id):
            query.answer("❌ Siz admin emassiz!", show_alert=True)
            return
        if data == "admin_stats":
            admin_stats(update, context)
        elif data == "admin_orders":
            admin_orders(update, context)
        elif data == "admin_suggestions":
            admin_suggestions(update, context)
        elif data == "admin_complaints":
            admin_complaints(update, context)
        elif data == "admin_promo":
            admin_promo_start(update, context)
        elif data == "admin_broadcast":
            admin_broadcast_start(update, context)
        elif data == "admin_panel":
            # call from text command, not callback
            pass

# ==================== MAIN ====================
def main():
    if not TOKEN:
        logger.error("BOT_TOKEN environment variable topilmadi!")
        return

    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    # ConversationHandler lar
    conv_custom = ConversationHandler(
        entry_points=[CallbackQueryHandler(custom_product_start, pattern="^custom_product$")],
        states={
            STATE_CUSTOM_PRODUCT: [MessageHandler(Filters.text & ~Filters.command, custom_product_receive)],
            STATE_CUSTOM_QUANTITY: [MessageHandler(Filters.text & ~Filters.command, custom_quantity_receive)],
        },
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(show_main_menu, pattern="^main_menu$")],
        map_to_parent={ConversationHandler.END: ConversationHandler.END}
    )
    conv_multi = ConversationHandler(
        entry_points=[CallbackQueryHandler(multi_select_start, pattern="^multi_select$")],
        states={
            STATE_MULTI_SELECT: [MessageHandler(Filters.text & ~Filters.command, multi_select_receive)],
        },
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(show_main_menu, pattern="^main_menu$")],
        map_to_parent={ConversationHandler.END: ConversationHandler.END}
    )
    conv_suggestion = ConversationHandler(
        entry_points=[CallbackQueryHandler(suggestion_start, pattern="^suggestion$")],
        states={
            STATE_SUGGESTION: [MessageHandler(Filters.text & ~Filters.command, suggestion_receive)],
        },
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(show_main_menu, pattern="^main_menu$")],
        map_to_parent={ConversationHandler.END: ConversationHandler.END}
    )
    conv_complaint = ConversationHandler(
        entry_points=[CallbackQueryHandler(complaint_start, pattern="^menu_complaint$")],
        states={
            STATE_COMPLAINT: [MessageHandler(Filters.text & ~Filters.command, complaint_receive)],
        },
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(show_main_menu, pattern="^main_menu$")],
        map_to_parent={ConversationHandler.END: ConversationHandler.END}
    )
    conv_order = ConversationHandler(
        entry_points=[CallbackQueryHandler(order_start, pattern="^order_start$")],
        states={
            STATE_ORDER_NAME: [MessageHandler(Filters.text & ~Filters.command, order_name_receive)],
            STATE_ORDER_PHONE: [MessageHandler(Filters.text & ~Filters.command, order_phone_receive)],
            STATE_ORDER_ADDRESS: [MessageHandler(Filters.text & ~Filters.command, order_address_receive)],
        },
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(show_main_menu, pattern="^main_menu$")],
        map_to_parent={ConversationHandler.END: ConversationHandler.END}
    )
    conv_admin_promo = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_promo_start, pattern="^admin_promo$")],
        states={
            STATE_ADMIN_PROMO: [MessageHandler(Filters.text & ~Filters.command, admin_promo_receive)],
        },
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(show_main_menu, pattern="^main_menu$")],
        map_to_parent={ConversationHandler.END: ConversationHandler.END}
    )
    conv_admin_broadcast = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_broadcast_start, pattern="^admin_broadcast$")],
        states={
            STATE_ADMIN_BROADCAST: [MessageHandler(Filters.text & ~Filters.command, admin_broadcast_receive)],
        },
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(show_main_menu, pattern="^main_menu$")],
        map_to_parent={ConversationHandler.END: ConversationHandler.END}
    )

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("admin", admin_panel))
    dp.add_handler(conv_custom)
    dp.add_handler(conv_multi)
    dp.add_handler(conv_suggestion)
    dp.add_handler(conv_complaint)
    dp.add_handler(conv_order)
    dp.add_handler(conv_admin_promo)
    dp.add_handler(conv_admin_broadcast)
    dp.add_handler(CallbackQueryHandler(callback_handler))

    # Fallback
    dp.add_handler(MessageHandler(Filters.all, lambda u,c: u.message.reply_text("Iltimos, menyudan tanlang.")))

    updater.start_polling()
    logger.info("✅ Bot ishga tushdi!")
    updater.idle()

if __name__ == "__main__":
    main()
  
