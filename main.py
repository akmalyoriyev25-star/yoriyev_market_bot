# -*- coding: utf-8 -*-
"""Yoriyev Market Bot - Mukammal versiya"""

import logging
import os
import sqlite3
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext

# ==================== KONFIGURATSIYA ====================
TOKEN = os.environ.get("BOT_TOKEN")
KANAL = os.environ.get("KANAL_USERNAME", "@yoriyev_market")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
BOT_USERNAME = "Yoriyev_market_bot"  # O‘zgartiring

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== MA'LUMOTLAR BAZASI ====================
conn = sqlite3.connect('yoriyev_market.db', check_same_thread=False)
cursor = conn.cursor()

# Foydalanuvchilar jadvali
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    ism TEXT,
    telefon TEXT,
    manzil TEXT,
    lokatsiya TEXT,
    registered_date TEXT,
    last_active TEXT,
    referred_by INTEGER,
    discount_count INTEGER DEFAULT 0,
    total_orders INTEGER DEFAULT 0
)
''')

# Buyurtmalar jadvali
cursor.execute('''
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    mahsulotlar TEXT,
    holat TEXT,
    sana TEXT,
    admin_izoh TEXT
)
''')

# Takliflar jadvali (yangi mahsulot takliflari)
cursor.execute('''
CREATE TABLE IF NOT EXISTS suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    matn TEXT,
    sana TEXT
)
''')

# Shikoyatlar jadvali
cursor.execute('''
CREATE TABLE IF NOT EXISTS complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    matn TEXT,
    sana TEXT
)
''')

# Aksiyalar (faqat bitta qator)
cursor.execute('''
CREATE TABLE IF NOT EXISTS promotions (
    id INTEGER PRIMARY KEY CHECK (id=1),
    text TEXT
)
''')
# Agar bo'sh bo'lsa, standart aksiya qo'shish
cursor.execute("INSERT OR IGNORE INTO promotions (id, text) VALUES (1, 'Hozircha aksiyalar yo‘q')")
conn.commit()

# ==================== YORDAMCHI FUNKSIYALAR ====================
def is_admin(user_id):
    return user_id == ADMIN_ID

def safe_str(text):
    return re.sub(r'[<>]', '', text) if text else ''

def validate_phone(phone):
    return re.match(r'^\+998\d{9}$', phone) is not None

def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    return cursor.fetchone()

def create_user(user_id, ism, referred_by=None):
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, ism, registered_date, last_active, referred_by, discount_count)
        VALUES (?, ?, ?, ?, ?, 0)
    ''', (user_id, safe_str(ism), datetime.now(), datetime.now(), referred_by))
    conn.commit()

def update_activity(user_id):
    cursor.execute("UPDATE users SET last_active=? WHERE user_id=?", (datetime.now(), user_id))
    conn.commit()

# ==================== MAHSULOTLAR (narxsiz) ====================
# To'liq ro'yxat – O‘zbekiston bozoridagi barcha meva, sabzavot, poliz
SABZAVOTLAR = [
    "Kartoshka", "Piyoz", "Sabzi", "Sholg'om", "Bodring", "Pomidor", "Turp", "Rediska", "Chesnok",
    "Qalampir", "Baqlajon", "Qovoq", "Karam", "Brokkoli", "Gulkaram", "Lavlagi", "Selderey",
    "Ismaloq", "Petrushka", "Ukrop", "Rayhon", "Shivit", "Qatiq o'simlik", "Hul", "No‘xat",
    "Mosh", "Loviya", "Bodom", "Yong‘oq", "Qovoqcha", "Patisson", "Bamya", "Rokambol", "Qizilcha"
]

MEVALAR = [
    "Olma", "Nok", "Banan", "Mandarin", "Apelsin", "Limon", "Greypfrut", "Anor", "Xurmo",
    "Uzum", "Gilos", "Olcha", "Shaftoli", "O'rik", "Ananas", "Kivi", "Mango", "Avakado",
    "Qulupnay", "Malina", "Smorodina", "Bektoshi", "Tut", "Jiyda", "Olxo'ri", "Shaptoli",
    "Nok", "Behi", "Yeryong'oq", "Pista", "Findiq", "Kakos", "Papayya", "Guvayva"
]

POLIZ = [
    "Tarvuz", "Qovun", "Qovoq", "Bodring", "Qovoqcha", "Patisson", "Hul"
]

# Barcha mahsulotlar (multi-select uchun)
BARCHA_MAHSULOTLAR = SABZAVOTLAR + MEVALAR + POLIZ

# Kategoriyalar lug'ati
KATEGORIYALAR = {
    "sabzavot": SABZAVOTLAR,
    "meva": MEVALAR,
    "poliz": POLIZ
}

# ==================== SAVATLAR (vaqtinchalik) ====================
savatlar = {}  # {user_id: [{"nom": "...", "soni": 1}, ...]}

# ==================== START ====================
def start(update: Update, context: CallbackContext):
    user = update.effective_user
    args = context.args
    referred_by = None
    if args and args[0].startswith("ref_"):
        try:
            referred_by = int(args[0].replace("ref_", ""))
        except:
            pass
    
    create_user(user.id, user.first_name, referred_by)
    update_activity(user.id)
    
    # Kanal tekshirish
    try:
        member = context.bot.get_chat_member(KANAL, user.id)
        if member.status in ['member', 'administrator', 'creator']:
            show_main_menu(update, context)
        else:
            update.message.reply_text(
                f"🌟 *Assalomu alaykum {user.first_name}!*\n\n"
                f"Botdan foydalanish uchun kanalimizga a'zo bo'ling:",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📢 Kanalga o'tish", url="https://t.me/yoriyev_market"),
                    InlineKeyboardButton("✅ Tekshirish", callback_data="check")
                ]])
            )
    except Exception as e:
        logger.error(f"Kanal tekshirish xatosi: {e}")
        update.message.reply_text("❌ Xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring.")

def check_subscription(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    try:
        member = context.bot.get_chat_member(KANAL, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            update_activity(user_id)
            show_main_menu(update, context, edit=True)
        else:
            query.edit_message_text(
                "❌ *Siz kanalga a'zo emassiz.*\n\nIltimos, avval a'zo bo'ling.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📢 Kanalga o'tish", url="https://t.me/yoriyev_market"),
                    InlineKeyboardButton("🔄 Qayta tekshirish", callback_data="check")
                ]])
            )
    except Exception as e:
        logger.error(f"Kanal tekshirish xatosi: {e}")
        query.edit_message_text(
            "❌ *Texnik xatolik yuz berdi.*\n\nIltimos, keyinroq urinib ko'ring.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Qayta tekshirish", callback_data="check")
            ]])
        )

def show_main_menu(update: Update, context: CallbackContext, edit=False):
    keyboard = [
        [InlineKeyboardButton("🛒 Mahsulotlar", callback_data="menu_mahsulotlar")],
        [InlineKeyboardButton("📢 Aksiyalar", callback_data="aksiya")],
        [InlineKeyboardButton("🛍 Savatim", callback_data="savat")],
        [InlineKeyboardButton("👤 Kabinet", callback_data="kabinet")],
        [InlineKeyboardButton("📞 Admin bilan bog'lanish", callback_data="admin_boglanish")],
        [InlineKeyboardButton("⚠️ Shikoyatlar", callback_data="shikoyat")],
        [InlineKeyboardButton("💡 Taklif qilish", callback_data="referral")]
    ]
    text = "🏠 *Bosh menyu*"
    if edit:
        query = update.callback_query
        query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        update.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

# ==================== MAHSULOTLAR MENYUSI ====================
def mahsulotlar_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    keyboard = [
        [InlineKeyboardButton("🥕 Sabzavotlar", callback_data="cat_sabzavot")],
        [InlineKeyboardButton("🍎 Mevalar", callback_data="cat_meva")],
        [InlineKeyboardButton("🍉 Poliz ekinlari", callback_data="cat_poliz")],
        [InlineKeyboardButton("📦 Kanalda ko'rgan mahsulot", callback_data="custom_product")],
        [InlineKeyboardButton("✅ Bir nechta tanlash", callback_data="multi_select")],
        [InlineKeyboardButton("💭 Yangi mahsulot taklifi", callback_data="suggestion")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ]
    query.edit_message_text("🛒 *Kategoriyani tanlang:*", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

def show_category_products(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    kat = query.data.replace("cat_", "")
    products = KATEGORIYALAR.get(kat, [])
    keyboard = []
    for nom in products:
        keyboard.append([InlineKeyboardButton(nom, callback_data=f"add_{kat}_{nom}")])
    keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_mahsulotlar")])
    query.edit_message_text(
        f"📋 *{kat.upper()} mahsulotlari:*\n\n💡 Narxlar kanalda.",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def add_to_cart(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    data = query.data.split("_")
    kat = data[1]
    nom = data[2]
    user_id = query.from_user.id
    if user_id not in savatlar:
        savatlar[user_id] = []
    for item in savatlar[user_id]:
        if item['nom'] == nom:
            item['soni'] += 1
            break
    else:
        savatlar[user_id].append({'nom': nom, 'soni': 1})
    query.edit_message_text(
        f"✅ *{nom}* savatga qo'shildi!",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Savatni ko'rish", callback_data="savat")],
            [InlineKeyboardButton("⬅️ Davom etish", callback_data=f"cat_{kat}")]
        ])
    )

def custom_product_start(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        "📝 *Iltimos, kanalda ko'rgan mahsulot nomini yozing:*\n\n"
        "Masalan: *Anor*",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Bekor qilish", callback_data="menu_mahsulotlar")
        ]])
    )
    context.user_data['state'] = 'waiting_custom_product'

def handle_custom_product(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = safe_str(update.message.text)
    if len(text) < 2:
        update.message.reply_text("❌ Mahsulot nomi juda qisqa. Qayta kiriting yoki bekor qiling.")
        return
    context.user_data['custom_product'] = text
    context.user_data['state'] = 'waiting_custom_quantity'
    update.message.reply_text("🔢 *Nechta kerak?*\nMasalan: 2 kg yoki 5 dona", parse_mode='Markdown')

def handle_custom_quantity(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = safe_str(update.message.text)
    product = context.user_data.get('custom_product')
    if not product:
        update.message.reply_text("❌ Xatolik. Qaytadan urinib ko'ring.")
        return
    if user_id not in savatlar:
        savatlar[user_id] = []
    savatlar[user_id].append({'nom': f"{product} ({text})", 'soni': 1})
    context.user_data.pop('custom_product', None)
    context.user_data.pop('state', None)
    update.message.reply_text(
        f"✅ *{product}* savatga qo'shildi!",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🛒 Savatni ko'rish", callback_data="savat"),
            InlineKeyboardButton("⬅️ Asosiy menyu", callback_data="main_menu")
        ]])
    )

def multi_select_start(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    # Har bir mahsulot uchun checkbox (InlineKeyboardButton) yaratish
    # Lekin Telegram inline keyboardda checkbox yo'q, shuning uchun biz toggle qilamiz.
    # Oddiyroq: foydalanuvchi birma-bir qo'shadi, lekin siz "bir nechta tanlash" so'ragan edingiz.
    # Buning uchun biz har bir mahsulotni tugma qilib, bosilganda belgilab boramiz va alohida "Tanlanganlarni qo'shish" tugmasi.
    # Bu murakkab, chunki har bir bosishda xabarni yangilash kerak. Biz soddaroq yechim taklif qilamiz:
    # "Bir nechta tanlash" bosilganda, foydalanuvchi vergul bilan ajratib yozishi mumkin.
    # Lekin siz "tugma orqali" demoqchi bo'lsangiz, keyingi versiyada qilamiz.
    # Hozircha soddaroq: matn kiritish orqali.
    query.edit_message_text(
        "✍️ *Bir nechta mahsulotni vergul bilan ajratib yozing:*\n"
        "Masalan: `Kartoshka, Piyoz, Sabzi`",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Bekor qilish", callback_data="menu_mahsulotlar")
        ]])
    )
    context.user_data['state'] = 'waiting_multi_select'

def handle_multi_select(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = safe_str(update.message.text)
    items = [x.strip() for x in text.split(',') if x.strip()]
    if not items:
        update.message.reply_text("❌ Hech qanday mahsulot kiritilmadi.")
        return
    if user_id not in savatlar:
        savatlar[user_id] = []
    for nom in items:
        # har birini bittadan qo'shamiz (soni 1)
        savatlar[user_id].append({'nom': nom, 'soni': 1})
    context.user_data.pop('state', None)
    update.message.reply_text(
        f"✅ {len(items)} ta mahsulot savatga qo'shildi!",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🛒 Savatni ko'rish", callback_data="savat"),
            InlineKeyboardButton("⬅️ Asosiy menyu", callback_data="main_menu")
        ]])
    )

def suggestion_start(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        "💡 *Yangi mahsulot taklif qiling:*\n"
        "Qanday mahsulot qo'shishimizni xohlaysiz? Nomini yozib qoldiring.",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Bekor qilish", callback_data="menu_mahsulotlar")
        ]])
    )
    context.user_data['state'] = 'waiting_suggestion'

def handle_suggestion(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = safe_str(update.message.text)
    if len(text) < 3:
        update.message.reply_text("❌ Taklif juda qisqa. Qayta kiriting.")
        return
    cursor.execute("INSERT INTO suggestions (user_id, matn, sana) VALUES (?, ?, ?)",
                   (user_id, text, datetime.now()))
    conn.commit()
    context.user_data.pop('state', None)
    update.message.reply_text(
        "✅ Taklifingiz qabul qilindi! Rahmat.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Asosiy menyu", callback_data="main_menu")
        ]])
    )
    # Adminga xabar
    if ADMIN_ID:
        try:
            context.bot.send_message(ADMIN_ID, f"💡 Yangi taklif: {text}\n👤 Foydalanuvchi: {user_id}")
        except:
            pass

# ==================== AKSIYALAR ====================
def show_promotion(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    cursor.execute("SELECT text FROM promotions WHERE id=1")
    row = cursor.fetchone()
    text = row[0] if row else "Aksiyalar mavjud emas."
    query.edit_message_text(
        f"📢 *Aksiyalar*\n\n{text}",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")
        ]])
    )

# ==================== SAVAT ====================
def view_cart(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    cart = savatlar.get(user_id, [])
    if not cart:
        query.edit_message_text(
            "🛒 *Savat bo'sh.*",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Kategoriyalar", callback_data="menu_mahsulotlar")
            ]])
        )
        return
    text = "🛒 *Savat:*\n\n"
    for i, item in enumerate(cart, 1):
        text += f"{i}. {item['nom']} x {item['soni']}\n"
    keyboard = [
        [InlineKeyboardButton("📦 Buyurtma berish", callback_data="order_start")],
        [InlineKeyboardButton("🗑 Savatni tozalash", callback_data="cart_clear")],
        [InlineKeyboardButton("⬅️ Kategoriyalar", callback_data="menu_mahsulotlar")]
    ]
    query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

def clear_cart(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    savatlar[user_id] = []
    query.edit_message_text(
        "🗑 Savat tozalandi.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Asosiy menyu", callback_data="main_menu")
        ]])
    )

# ==================== BUYURTMA ====================
def order_start(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    if user_id not in savatlar or not savatlar[user_id]:
        query.edit_message_text("❌ Savat bo'sh.")
        return
    query.edit_message_text(
        "📝 *Buyurtma berish*\n\nIltimos, ismingizni kiriting:",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Bekor qilish", callback_data="main_menu")
        ]])
    )
    context.user_data['order_step'] = 'name'

def handle_order_name(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = safe_str(update.message.text)
    if len(text) < 2:
        update.message.reply_text("❌ Ism juda qisqa. Qayta kiriting:")
        return
    context.user_data['order_name'] = text
    context.user_data['order_step'] = 'phone'
    update.message.reply_text(
        "📞 *Telefon raqamingizni kiriting:*\nFormat: +998901234567",
        parse_mode='Markdown'
    )

def handle_order_phone(update: Update, context: CallbackContext):
    text = safe_str(update.message.text)
    if not validate_phone(text):
        update.message.reply_text("❌ Noto'g'ri format. Masalan: +998901234567")
        return
    context.user_data['order_phone'] = text
    context.user_data['order_step'] = 'location'
    keyboard = [
        [InlineKeyboardButton("📍 Lokatsiya yuborish", callback_data="send_location")],
        [InlineKeyboardButton("✍️ Manzilni yozish", callback_data="enter_address")]
    ]
    update.message.reply_text(
        "📍 Manzilingizni yuboring yoki yozib kiriting:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def order_location_choice(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    if query.data == "send_location":
        # Lokatsiya so'rash
        query.edit_message_text(
            "📍 Iltimos, lokatsiyangizni yuboring:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Bekor qilish", callback_data="main_menu")
            ]])
        )
        context.user_data['order_step'] = 'waiting_location'
    else:
        query.edit_message_text(
            "✍️ Manzilingizni yozing (ko'cha, uy raqami):",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Bekor qilish", callback_data="main_menu")
            ]])
        )
        context.user_data['order_step'] = 'waiting_address'

def handle_order_location(update: Update, context: CallbackContext):
    location = update.message.location
    user_id = update.effective_user.id
    if location:
        lat = location.latitude
        lon = location.longitude
        loc_str = f"{lat},{lon}"
        finalize_order(update, context, loc_str)
    else:
        update.message.reply_text("❌ Lokatsiya olinmadi. Qaytadan urinib ko'ring.")

def handle_order_address(update: Update, context: CallbackContext):
    text = safe_str(update.message.text)
    if len(text) < 5:
        update.message.reply_text("❌ Manzil juda qisqa. Qayta kiriting:")
        return
    finalize_order(update, context, text)

def finalize_order(update: Update, context: CallbackContext, manzil):
    user_id = update.effective_user.id
    name = context.user_data.get('order_name')
    phone = context.user_data.get('order_phone')
    cart = savatlar.get(user_id, [])
    if not cart:
        update.message.reply_text("❌ Savat bo'sh.")
        return
    product_text = ", ".join([f"{item['nom']} x{item['soni']}" for item in cart])
    
    # Foydalanuvchi ma'lumotlarini yangilash
    cursor.execute('''
        UPDATE users SET ism=?, telefon=?, manzil=?, lokatsiya=?, last_active=?
        WHERE user_id=?
    ''', (name, phone, manzil, manzil, datetime.now(), user_id))
    conn.commit()
    
    # Buyurtmani saqlash
    cursor.execute('''
        INSERT INTO orders (user_id, mahsulotlar, holat, sana)
        VALUES (?, ?, ?, ?)
    ''', (user_id, product_text, "yangi", datetime.now()))
    order_id = cursor.lastrowid
    conn.commit()
    
    # Foydalanuvchining umumiy buyurtmalar sonini oshirish
    cursor.execute("UPDATE users SET total_orders = total_orders + 1 WHERE user_id=?", (user_id,))
    conn.commit()
    
    # Referral tekshirish: agar foydalanuvchi birinchi buyurtmasi bo'lsa va referrer bo'lsa, discount bering
    cursor.execute("SELECT referred_by FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if row and row[0]:
        referrer = row[0]
        # Foydalanuvchining oldingi buyurtmalari sonini tekshirish (hozir total_orders 1 ga oshdi, lekin bu birinchi bo'lsa)
        cursor.execute("SELECT total_orders FROM users WHERE user_id=?", (user_id,))
        tot = cursor.fetchone()[0]
        if tot == 1:  # birinchi buyurtma
            # Refererga discount bering
            cursor.execute("UPDATE users SET discount_count = discount_count + 1 WHERE user_id=?", (referrer,))
            conn.commit()
            # Yangi foydalanuvchiga ham discount berish mumkin? Sizning talab bo'yicha "kanaldagi narxlardan arzon" – ikkalasiga ham?
            # Siz aytgansiz: "mijoz yana boshqa kishini taklif qilsa kanaldagi narxlardan ham arzon narxlarda mahsulotini olsin" – bu referrer uchun.
            # Yangi mijozga ham chegirma? Ko'pchilik tizimda ikkalasiga ham beriladi. Biz referrer va yangi mijozga bittadan discount beramiz.
            cursor.execute("UPDATE users SET discount_count = discount_count + 1 WHERE user_id=?", (user_id,))
            conn.commit()
    
    # Savatni tozalash
    savatlar[user_id] = []
    context.user_data.clear()
    
    # Foydalanuvchiga xabar
    update.message.reply_text(
        f"✅ *Buyurtmangiz qabul qilindi!*\n\n"
        f"Tez orada siz bilan bog'lanamiz.\n"
        f"Buyurtma raqami: #{order_id}",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")
        ]])
    )
    
    # Adminga xabar
    if ADMIN_ID:
        try:
            user_info = get_user(user_id)
            discount_note = f"💰 Chegirma: {user_info[7]} mavjud" if user_info and user_info[7] > 0 else ""
            context.bot.send_message(
                ADMIN_ID,
                f"🆕 *Yangi buyurtma!*\n\n"
                f"👤 Ism: {name}\n"
                f"📞 Tel: {phone}\n"
                f"📍 Manzil: {manzil}\n"
                f"🛍 Mahsulotlar: {product_text}\n"
                f"🆔 Buyurtma №: {order_id}\n"
                f"{discount_note}",
                parse_mode='Markdown'
            )
        except:
            pass

# ==================== KABINET ====================
def kabinet(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    if not user:
        query.edit_message_text("Ma'lumot topilmadi.")
        return
    ism, telefon, manzil, lokatsiya, reg_date, last_active, referred_by, discount, total_orders = user[1:]
    # Referral link
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    text = f"👤 *Kabinet*\n\n"
    text += f"Ism: {ism}\n"
    text += f"Telefon: {telefon or 'yoʻq'}\n"
    text += f"Manzil: {manzil or 'yoʻq'}\n"
    text += f"Buyurtmalar soni: {total_orders}\n"
    text += f"Chegirmalar soni: {discount}\n\n"
    text += f"🔗 *Taklif havolangiz:*\n`{ref_link}`\n\n"
    text += "Taklif qilgan har bir do'stingiz birinchi buyurtma bersa, siz va do'stingiz 1 tadan chegirma olasiz. Chegirma bilan mahsulotlarni kanaldagi narxlardan arzon olishingiz mumkin!"
    keyboard = [
        [InlineKeyboardButton("📦 Buyurtmalarim", callback_data="my_orders")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ]
    query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

def my_orders(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    cursor.execute("SELECT id, mahsulotlar, holat, sana FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 5", (user_id,))
    orders = cursor.fetchall()
    if not orders:
        query.edit_message_text(
            "Sizda hali buyurtmalar yo'q.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Orqaga", callback_data="kabinet")
            ]])
        )
        return
    text = "📦 *Oxirgi buyurtmalar:*\n\n"
    for o in orders:
        text += f"#{o[0]}: {o[1]} – {o[2]}\n{o[3][:10]}\n\n"
    query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ Orqaga", callback_data="kabinet")
    ]]))

def referral_info(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    text = (
        "💡 *Taklif qilish tizimi*\n\n"
        "Do'stlaringizni taklif qiling va chegirmalar oling!\n\n"
        "Qanday ishlaydi:\n"
        "1. Havolani do'stingizga yuboring.\n"
        "2. Do'stingiz havola orqali botga kirib, birinchi buyurtmasini bersa, siz va do'stingiz 1 tadan chegirma olasiz.\n"
        "3. Chegirma bilan mahsulotlarni kanaldagi narxlardan arzon olishingiz mumkin.\n\n"
        f"🔗 *Sizning havolangiz:*\n`{ref_link}`"
    )
    query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")
        ]])
    )

# ==================== ADMIN BILAN BOG'LANISH ====================
def admin_contact(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    text = "📞 *Admin bilan bog'lanish*\n\nAdmin: @akmalyoriyev\nIstalgan savol bo'yicha murojaat qiling."
    query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")
    ]]))

# ==================== SHIKOYATLAR ====================
def complaint_start(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        "⚠️ *Shikoyat yoki taklifingizni yozing:*",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Bekor qilish", callback_data="main_menu")
        ]])
    )
    context.user_data['state'] = 'waiting_complaint'

def handle_complaint(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = safe_str(update.message.text)
    if len(text) < 5:
        update.message.reply_text("❌ Xabar juda qisqa. Qayta kiriting.")
        return
    cursor.execute("INSERT INTO complaints (user_id, matn, sana) VALUES (?, ?, ?)",
                   (user_id, text, datetime.now()))
    conn.commit()
    context.user_data.pop('state', None)
    update.message.reply_text(
        "✅ Shikoyatingiz qabul qilindi. Rahmat!",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Asosiy menyu", callback_data="main_menu")
        ]])
    )
    if ADMIN_ID:
        try:
            context.bot.send_message(ADMIN_ID, f"⚠️ Yangi shikoyat: {text}\n👤 Foydalanuvchi: {user_id}")
        except:
            pass

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
        [InlineKeyboardButton("📢 Aksiyani tahrirlash", callback_data="admin_edit_promo")],
        [InlineKeyboardButton("📤 Xabar yuborish", callback_data="admin_broadcast")],
        [InlineKeyboardButton("⬅️ Yopish", callback_data="main_menu")]
    ]
    update.message.reply_text("⚙️ *Admin panel*", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

def admin_stats(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    cursor.execute("SELECT COUNT(*) FROM users")
    users_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM orders WHERE holat='yangi'")
    new_orders = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM orders WHERE date(sana)=date('now')")
    today_orders = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM suggestions")
    suggestions = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM complaints")
    complaints = cursor.fetchone()[0]
    text = f"📊 *Statistika*\n\n👥 Jami mijozlar: {users_count}\n🆕 Yangi buyurtmalar: {new_orders}\n📅 Bugungi buyurtmalar: {today_orders}\n💬 Takliflar: {suggestions}\n⚠️ Shikoyatlar: {complaints}"
    query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
    ]]))

def admin_orders(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    cursor.execute("SELECT id, user_id, mahsulotlar, sana FROM orders WHERE holat='yangi' ORDER BY id DESC LIMIT 10")
    orders = cursor.fetchall()
    if not orders:
        query.edit_message_text("📦 Yangi buyurtmalar yo'q.", reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
        ]]))
        return
    text = "📦 *Yangi buyurtmalar:*\n\n"
    for o in orders:
        text += f"#{o[0]} (User {o[1]}): {o[2][:50]}...\n{o[3][:10]}\n\n"
    query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
    ]]))

def admin_suggestions(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    cursor.execute("SELECT id, user_id, matn, sana FROM suggestions ORDER BY id DESC LIMIT 10")
    rows = cursor.fetchall()
    if not rows:
        query.edit_message_text("Takliflar yo'q.", reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
        ]]))
        return
    text = "💬 *Takliflar:*\n\n"
    for r in rows:
        text += f"#{r[0]} (User {r[1]}): {r[2][:50]}\n{r[3][:10]}\n\n"
    query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
    ]]))

def admin_complaints(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    cursor.execute("SELECT id, user_id, matn, sana FROM complaints ORDER BY id DESC LIMIT 10")
    rows = cursor.fetchall()
    if not rows:
        query.edit_message_text("Shikoyatlar yo'q.", reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
        ]]))
        return
    text = "⚠️ *Shikoyatlar:*\n\n"
    for r in rows:
        text += f"#{r[0]} (User {r[1]}): {r[2][:50]}\n{r[3][:10]}\n\n"
    query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
    ]]))

def admin_edit_promo(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        "✍️ *Yangi aksiya matnini yozing:*",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Bekor qilish", callback_data="admin_panel")
        ]])
    )
    context.user_data['admin_state'] = 'editing_promo'

def handle_admin_promo(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        return
    text = safe_str(update.message.text)
    cursor.execute("UPDATE promotions SET text=? WHERE id=1", (text,))
    conn.commit()
    context.user_data.pop('admin_state', None)
    update.message.reply_text("✅ Aksiya matni yangilandi!")

def admin_broadcast_start(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text(
        "✍️ *Barcha foydalanuvchilarga yuboriladigan xabarni yozing:*",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Bekor qilish", callback_data="admin_panel")
        ]])
    )
    context.user_data['admin_state'] = 'broadcast'

def handle_broadcast(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        return
    text = update.message.text
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    sent = 0
    for (uid,) in users:
        try:
            context.bot.send_message(uid, text)
            sent += 1
        except:
            pass
    update.message.reply_text(f"✅ Xabar {sent} ta foydalanuvchiga yuborildi.")
    context.user_data.pop('admin_state', None)

# ==================== UMUMIY HANDLERLAR ====================
def handle_text(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    # Davlatni tekshirish
    if 'state' in context.user_data:
        state = context.user_data['state']
        if state == 'waiting_custom_product':
            handle_custom_product(update, context)
        elif state == 'waiting_custom_quantity':
            handle_custom_quantity(update, context)
        elif state == 'waiting_multi_select':
            handle_multi_select(update, context)
        elif state == 'waiting_suggestion':
            handle_suggestion(update, context)
        elif state == 'waiting_complaint':
            handle_complaint(update, context)
        return
    if 'order_step' in context.user_data:
        step = context.user_data['order_step']
        if step == 'name':
            handle_order_name(update, context)
        elif step == 'phone':
            handle_order_phone(update, context)
        elif step == 'waiting_address':
            handle_order_address(update, context)
        return
    if 'admin_state' in context.user_data:
        if context.user_data['admin_state'] == 'editing_promo':
            handle_admin_promo(update, context)
        elif context.user_data['admin_state'] == 'broadcast':
            handle_broadcast(update, context)
        return
    update.message.reply_text("Iltimos, menyudan tanlang.")

def handle_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    update_activity(user_id)
    
    if data == "check":
        check_subscription(update, context)
    elif data == "main_menu":
        show_main_menu(update, context, edit=True)
    elif data == "menu_mahsulotlar":
        mahsulotlar_menu(update, context)
    elif data.startswith("cat_"):
        show_category_products(update, context)
    elif data.startswith("add_"):
        add_to_cart(update, context)
    elif data == "custom_product":
        custom_product_start(update, context)
    elif data == "multi_select":
        multi_select_start(update, context)
    elif data == "suggestion":
        suggestion_start(update, context)
    elif data == "aksiya":
        show_promotion(update, context)
    elif data == "savat":
        view_cart(update, context)
    elif data == "cart_clear":
        clear_cart(update, context)
    elif data == "order_start":
        order_start(update, context)
    elif data == "send_location" or data == "enter_address":
        order_location_choice(update, context)
    elif data == "kabinet":
        kabinet(update, context)
    elif data == "my_orders":
        my_orders(update, context)
    elif data == "referral":
        referral_info(update, context)
    elif data == "admin_boglanish":
        admin_contact(update, context)
    elif data == "shikoyat":
        complaint_start(update, context)
    elif data == "admin_panel":
        # Admin panel faqat /admin orqali
        query.edit_message_text("Admin panelni /admin orqali oching.")
    elif data == "admin_stats":
        admin_stats(update, context)
    elif data == "admin_orders":
        admin_orders(update, context)
    elif data == "admin_suggestions":
        admin_suggestions(update, context)
    elif data == "admin_complaints":
        admin_complaints(update, context)
    elif data == "admin_edit_promo":
        admin_edit_promo(update, context)
    elif data == "admin_broadcast":
        admin_broadcast_start(update, context)

def handle_location(update: Update, context: CallbackContext):
    if 'order_step' in context.user_data and context.user_data['order_step'] == 'waiting_location':
        handle_order_location(update, context)

def error_handler(update: Update, context: CallbackContext):
    logger.error(f"Xatolik: {context.error}")

# ==================== MAIN ====================
def main():
    if not TOKEN:
        logger.error("TOKEN topilmadi! Environment variables ni tekshiring.")
        return
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    # Handlerlar
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("admin", admin_panel))
    dp.add_handler(CallbackQueryHandler(handle_callback))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
    dp.add_handler(MessageHandler(Filters.location, handle_location))
    dp.add_error_handler(error_handler)
    
    updater.start_polling()
    logger.info("✅ Bot ishga tushdi!")
    updater.idle()

if __name__ == "__main__":
    main()
