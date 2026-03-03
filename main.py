# -*- coding: utf-8 -*-
"""YORIYEV MARKET BOT – HTML format (kanal nomidagi _ muammosi hal qilindi)"""

import logging
import os
import sqlite3
import re
from datetime import datetime

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
                location TEXT,
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
            CREATE TABLE IF NOT EXISTS suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                text TEXT,
                created_at TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS complaints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                text TEXT,
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
    # HTML uchun xavfli belgilarni tozalash (va & ni ham)
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
    STATE_SUGGESTION,
    STATE_COMPLAINT,
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
        [InlineKeyboardButton("👤 Kabinet", callback_data="menu_cabinet")],
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
        InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")
    ]])
    query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
    context.user_data['state'] = STATE_PRODUCT_TEXT
    return

def handle_product_text(update: Update, context: CallbackContext):
    text = safe_str(update.message.text)
    context.user_data['product_items'] = text
    update_user_activity(update.effective_user.id)
    reply_keyboard = [[KeyboardButton("📱 Profilni yuborish", request_contact=True)]]
    update.message.reply_text(
        "📝 <b>Iltimos, ismingizni kiriting yoki profilni yuboring:</b>",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=True)
    )
    return STATE_ORDER_NAME

def order_name_receive(update: Update, context: CallbackContext):
    if update.message.contact:
        contact = update.message.contact
        context.user_data['order_name'] = contact.first_name
        context.user_data['order_phone'] = contact.phone_number
        with get_db() as conn:
            conn.execute("UPDATE users SET phone=? WHERE user_id=?", (contact.phone_number, update.effective_user.id))
            conn.commit()
        if ADMIN_ID:
            context.bot.send_message(
                ADMIN_ID,
                f"📱 <b>Yangi kontakt (profil):</b>\n👤 {contact.first_name}\n📞 {contact.phone_number}\n🆔 {update.effective_user.id}",
                parse_mode="HTML"
            )
        reply_keyboard = [[KeyboardButton("📱 Profilni yuborish", request_contact=True)]]
        update.message.reply_text(
            "📍 <b>Manzilingizni kiriting:</b>\n(masalan: Chalmagadoy qishlog'i, Paynet ro'parasi)",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=True)
        )
        return STATE_ORDER_ADDRESS
    else:
        name = safe_str(update.message.text)
        if len(name) < 2:
            update.message.reply_text("❌ Ism juda qisqa. Qayta kiriting:")
            return STATE_ORDER_NAME
        context.user_data['order_name'] = name
        reply_keyboard = [[KeyboardButton("📱 Profilni yuborish", request_contact=True)]]
        update.message.reply_text(
            "📞 <b>Telefon raqamingizni kiriting:</b>\nFormat: +998901234567",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=True)
        )
        return STATE_ORDER_PHONE

def order_phone_receive(update: Update, context: CallbackContext):
    if update.message.contact:
        contact = update.message.contact
        context.user_data['order_phone'] = contact.phone_number
        with get_db() as conn:
            conn.execute("UPDATE users SET phone=? WHERE user_id=?", (contact.phone_number, update.effective_user.id))
            conn.commit()
        if ADMIN_ID:
            context.bot.send_message(
                ADMIN_ID,
                f"📱 <b>Yangi kontakt (profil):</b>\n👤 {contact.first_name}\n📞 {contact.phone_number}\n🆔 {update.effective_user.id}",
                parse_mode="HTML"
            )
        reply_keyboard = [[KeyboardButton("📱 Profilni yuborish", request_contact=True)]]
        update.message.reply_text(
            "📍 <b>Manzilingizni kiriting:</b>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=True)
        )
        return STATE_ORDER_ADDRESS
    else:
        phone = safe_str(update.message.text)
        if not validate_phone(phone):
            update.message.reply_text("❌ Noto'g'ri format. Qayta kiriting (masalan: +998901234567):")
            return STATE_ORDER_PHONE
        context.user_data['order_phone'] = phone
        with get_db() as conn:
            conn.execute("UPDATE users SET phone=? WHERE user_id=?", (phone, update.effective_user.id))
            conn.commit()
        reply_keyboard = [[KeyboardButton("📱 Profilni yuborish", request_contact=True)]]
        update.message.reply_text(
            "📍 <b>Manzilingizni kiriting:</b>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=True)
        )
        return STATE_ORDER_ADDRESS

def order_address_receive(update: Update, context: CallbackContext):
    if update.message.contact:
        contact = update.message.contact
        context.user_data['order_address'] = "Kontakt orqali yuborilgan"
        with get_db() as conn:
            conn.execute("UPDATE users SET phone=? WHERE user_id=?", (contact.phone_number, update.effective_user.id))
            conn.commit()
        if ADMIN_ID:
            context.bot.send_message(
                ADMIN_ID,
                f"📱 <b>Yangi kontakt (profil):</b>\n👤 {contact.first_name}\n📞 {contact.phone_number}\n🆔 {update.effective_user.id}",
                parse_mode="HTML"
            )
    else:
        address = safe_str(update.message.text)
        if len(address) < 5:
            update.message.reply_text("❌ Manzil juda qisqa. Qayta kiriting:")
            return STATE_ORDER_ADDRESS
        context.user_data['order_address'] = address
        with get_db() as conn:
            conn.execute("UPDATE users SET address=? WHERE user_id=?", (address, update.effective_user.id))
            conn.commit()

    # Buyurtmani saqlash
    user_id = update.effective_user.id
    name = context.user_data.get('order_name', '')
    phone = context.user_data.get('order_phone', '')
    address = context.user_data.get('order_address', '')
    items = context.user_data.get('product_items', '')
    with get_db() as conn:
        conn.execute("""
            INSERT INTO orders (user_id, items, status, created_at)
            VALUES (?, ?, ?, ?)
        """, (user_id, items, "yangi", datetime.now().isoformat()))
        order_id = conn.lastrowid
        conn.execute("UPDATE users SET total_orders = total_orders + 1 WHERE user_id=?", (user_id,))
        cur = conn.execute("SELECT referred_by, total_orders FROM users WHERE user_id=?", (user_id,))
        row = cur.fetchone()
        if row and row['referred_by'] and row['total_orders'] == 0:
            add_discount(row['referred_by'])
            add_discount(user_id)
            try:
                context.bot.send_message(
                    row['referred_by'],
                    "🎉 Siz taklif qilgan do'stingiz birinchi buyurtmasini berdi! Endi siz navbatdagi buyurtmangizda maxsus chegirmaga ega bo'lasiz. Chegirmani admin bilan kelishingiz mumkin."
                )
            except:
                pass
        conn.commit()

    if ADMIN_ID:
        try:
            context.bot.send_message(
                ADMIN_ID,
                f"🆕 <b>Yangi buyurtma!</b>\n\n"
                f"👤 Ism: {name}\n"
                f"📞 Tel: {phone}\n"
                f"📍 Manzil: {address}\n"
                f"🛍 Mahsulotlar: {items}\n"
                f"🆔 Buyurtma №: {order_id}",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Admin xabar yuborishda xatolik: {e}")

    context.user_data.pop('product_items', None)
    context.user_data.pop('order_name', None)
    context.user_data.pop('order_phone', None)
    context.user_data.pop('order_address', None)
    context.user_data.pop('state', None)

    update.message.reply_text(
        f"✅ <b>Buyurtmangiz qabul qilindi!</b>\n\n"
        f"Tez orada siz bilan bog'lanamiz.\n"
        f"Buyurtma raqami: #{order_id}",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )
    show_main_menu(update, context)
    return ConversationHandler.END

# ==================== AKSIYALAR ====================
@require_subscription
def show_promotion(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    text = (
        "📢 <b>Aksiyalar</b>\n\n"
        f"Aksiyalar haqida batafsil kanalimizda:\n\n"
        f"👉 @{CHANNEL.lstrip('@')}"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL.lstrip('@')}"),
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
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ])
    query.edit_message_text(
        "📞 <b>Admin bilan bog'lanish</b>\n\n"
        "Quyidagi tugmalar orqali admin bilan bog'lanishingiz mumkin:",
        parse_mode="HTML",
        reply_markup=keyboard
    )

# ==================== SHIKOYAT / TAKLIF ====================
@require_subscription
def complaint_start(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        "⚠️ <b>Shikoyat yoki taklifingizni yozing:</b>",
        parse_mode="HTML",
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
                f"⚠️ <b>Yangi shikoyat/taklif</b>\n👤 Foydalanuvchi: {user_id}\n📝 {text}",
                parse_mode="HTML"
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
    text = (
        "💡 <b>Taklif qilish tizimi</b>\n\n"
        "Do'stlaringizni taklif qiling va chegirmalar oling!\n\n"
        "Qanday ishlaydi:\n"
        "1. Havolani do'stingizga yuboring.\n"
        "2. Do'stingiz havola orqali botga kirib, birinchi buyurtmasini bersa, siz va do'stingiz 1 tadan chegirma olasiz.\n"
        "3. Chegirma bilan mahsulotlarni kanaldagi narxlardan arzon olishingiz mumkin (chegirmani admin bilan kelishasiz).\n\n"
        f"🔗 <b>Sizning havolangiz:</b>\n<code>{ref_link}</code>\n\n"
        f"Taklif qilganlaringiz soni: {count}"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")
    ]])
    query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

# ==================== KABINET ====================
@require_subscription
def cabinet(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        orders = conn.execute(
            "SELECT id, items, status, created_at FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 5",
            (user_id,)
        ).fetchall()
        referrals = conn.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (user_id,)).fetchone()[0]
    if not user:
        query.edit_message_text("❌ Ma'lumot topilmadi.")
        return
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    text = (
        f"👤 <b>Kabinet</b>\n\n"
        f"Ism: {user['first_name']}\n"
        f"Telefon: {user['phone'] or 'yoʻq'}\n"
        f"Manzil: {user['address'] or 'yoʻq'}\n"
        f"Buyurtmalar: {user['total_orders']}\n"
        f"Chegirmalar: {user['discount_count']}\n"
        f"Taklif qilganlar: {referrals}\n\n"
        f"🔗 <b>Taklif havolangiz:</b>\n<code>{ref_link}</code>\n\n"
    )
    if orders:
        text += "📦 <b>Oxirgi buyurtmalar:</b>\n"
        for o in orders:
            text += f"#{o['id']}: {o['items'][:50]}...\n{o['created_at'][:10]}\n\n"
    else:
        text += "📦 <b>Hali buyurtmalar yoʻq.</b>"
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
        "Buyurtma berish jarayonida to'lov haqida admin bilan kelishasiz."
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
        [InlineKeyboardButton("💬 Takliflar", callback_data="admin_suggestions")],
        [InlineKeyboardButton("⚠️ Shikoyatlar", callback_data="admin_complaints")],
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
        suggestions = conn.execute("SELECT COUNT(*) FROM suggestions").fetchone()[0]
        complaints = conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
    text = (
        f"📊 <b>Statistika</b>\n\n"
        f"👥 Jami foydalanuvchilar: {users}\n"
        f"🆕 Yangi buyurtmalar: {new_orders}\n"
        f"📅 Bugungi buyurtmalar: {today_orders}\n"
        f"💬 Takliflar: {suggestions}\n"
        f"⚠️ Shikoyatlar: {complaints}"
    )
    query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[
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
    text = "📦 <b>Yangi buyurtmalar:</b>\n\n"
    for o in orders:
        text += f"#{o['id']} (User {o['user_id']}): {o['items'][:50]}...\n{o['created_at'][:10]}\n\n"
    query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[
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
    text = "💬 <b>Takliflar:</b>\n\n"
    for r in rows:
        text += f"#{r['id']} (User {r['user_id']}): {r['text'][:50]}...\n{r['created_at'][:10]}\n\n"
    query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[
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
    text = "⚠️ <b>Shikoyatlar:</b>\n\n"
    for r in rows:
        text += f"#{r['id']} (User {r['user_id']}): {r['text'][:50]}...\n{r['created_at'][:10]}\n\n"
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
    update.message.reply_text("✅ Aksiya matni yangilandi!", reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ Admin panel", callback_data="admin_panel")
    ]]))
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

# ==================== CALLBACK HANDLER ====================
def callback_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    if data not in ["check_sub", "main_menu"]:
        if not check_subscription(context.bot, user_id):
            query.answer("⚠️ Avval kanalga a'zo bo'ling!", show_alert=True)
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL.lstrip('@')}"),
                InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")
            ]])
            query.edit_message_text(
                "🚫 <b>Botdan foydalanish uchun kanalimizga a'zo bo'ling!</b>",
                parse_mode="HTML",
                reply_markup=keyboard
            )
            return

    if data == "check_sub":
        check_sub_callback(update, context)
    elif data == "main_menu":
        show_main_menu(update, context, edit=True)
    elif data == "menu_products":
        products_menu(update, context)
    elif data == "menu_promo":
        show_promotion(update, context)
    elif data == "menu_contact":
        admin_contact(update, context)
    elif data == "menu_complaint":
        complaint_start(update, context)
    elif data == "menu_referral":
        referral_info(update, context)
    elif data == "menu_cabinet":
        cabinet(update, context)
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
        elif data == "admin_suggestions":
            admin_suggestions(update, context)
        elif data == "admin_complaints":
            admin_complaints(update, context)
        elif data == "admin_promo":
            admin_promo_start(update, context)
        elif data == "admin_broadcast":
            admin_broadcast_start(update, context)

# ==================== MAIN ====================
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    # Conversation handlers
    product_conv = ConversationHandler(
        entry_points=[MessageHandler(Filters.text & ~Filters.command, handle_product_text)],
        states={
            STATE_ORDER_NAME: [MessageHandler(Filters.all, order_name_receive)],
            STATE_ORDER_PHONE: [MessageHandler(Filters.all, order_phone_receive)],
            STATE_ORDER_ADDRESS: [MessageHandler(Filters.all, order_address_receive)],
        },
        fallbacks=[CommandHandler("start", start)],
        map_to_parent={ConversationHandler.END: ConversationHandler.END}
    )
    complaint_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(complaint_start, pattern="^menu_complaint$")],
        states={
            STATE_COMPLAINT: [MessageHandler(Filters.text & ~Filters.command, complaint_receive)],
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
    dp.add_handler(product_conv)
    dp.add_handler(complaint_conv)
    dp.add_handler(admin_promo_conv)
    dp.add_handler(admin_broadcast_conv)
    dp.add_handler(CallbackQueryHandler(callback_handler))

    # Fallback
    dp.add_handler(MessageHandler(Filters.all, lambda u,c: u.message.reply_text("Iltimos, menyudan tanlang.")))

    updater.start_polling()
    logger.info("✅ Bot ishga tushdi!")
    updater.idle()

if __name__ == "__main__":
    main()
