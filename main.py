# -*- coding: utf-8 -*-
"""Yoriyev Market Bot - Railway version"""

import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext
import sqlite3
from datetime import datetime
import re

# ==================== KONFIGURATSIYA ====================
TOKEN = os.environ.get("BOT_TOKEN")
KANAL = os.environ.get("KANAL_USERNAME", "@yoriyev_market")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

# ==================== LOGGING ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== MA'LUMOTLAR BAZASI ====================
conn = sqlite3.connect('yoriyev_market.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS mijozlar (
    user_id INTEGER PRIMARY KEY,
    ism TEXT,
    telefon TEXT,
    manzil TEXT,
    lokatsiya TEXT,
    qoshilgan_sana TEXT,
    oxirgi_faollik TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS buyurtmalar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    mahsulotlar TEXT,
    umumiy_narx INTEGER,
    holat TEXT,
    sana TEXT,
    admin_izoh TEXT
)
''')
conn.commit()

# ==================== YORDAMCHI FUNKSIYALAR ====================
def is_admin(user_id):
    return user_id == ADMIN_ID

def safe_str(text):
    return re.sub(r'[<>]', '', text) if text else ''

def validate_phone(phone):
    return re.match(r'^\+998\d{9}$', phone) is not None

# ==================== START ====================
def start(update: Update, context: CallbackContext):
    user = update.effective_user
    cursor.execute('''
        INSERT OR REPLACE INTO mijozlar (user_id, ism, qoshilgan_sana, oxirgi_faollik)
        VALUES (?, ?, ?, ?)
    ''', (user.id, safe_str(user.first_name), datetime.now(), datetime.now()))
    conn.commit()
    
    update.message.reply_text(
        f"🌟 *Assalomu alaykum {user.first_name}!*\n\n"
        f"Yoriyev market botiga xush kelibsiz.\n"
        f"✅ Mahsulot narxlarini ko'rish va buyurtma berish uchun kanalimizga a'zo bo'ling.",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📢 Kanalga o'tish", url="https://t.me/yoriyev_market"),
            InlineKeyboardButton("✅ Tekshirish", callback_data="check")
        ]])
    )

def check_subscription(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    
    try:
        member = context.bot.get_chat_member(KANAL, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            cursor.execute('UPDATE mijozlar SET oxirgi_faollik = ? WHERE user_id = ?', 
                          (datetime.now(), user_id))
            conn.commit()
            
            query.edit_message_text(
                "✅ *A'zo bo'lgansiz!*\n\nEndi buyurtma berishingiz mumkin.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🛍 Mahsulotlar", callback_data="kategoriyalar")
                ]])
            )
        else:
            query.edit_message_text(
                "❌ *Siz kanalga a'zo emassiz.*\n\nIltimos, avval kanalga a'zo bo'ling.",
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
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Qayta tekshirish", callback_data="check")
            ]])
        )

def kategoriyalar(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🥕 Sabzavotlar", callback_data="cat_sabzavot")],
        [InlineKeyboardButton("🍎 Mevalar", callback_data="cat_meva")],
        [InlineKeyboardButton("🍉 Poliz ekinlari", callback_data="cat_poliz")],
        [InlineKeyboardButton("📥 Savatim", callback_data="savat_ko'rish")],
        [InlineKeyboardButton("📦 Buyurtma berish", callback_data="buyurtma_berish")]
    ]
    
    if is_admin(query.from_user.id):
        keyboard.append([InlineKeyboardButton("⚙️ Admin panel", callback_data="admin_panel")])
    
    keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="start")])
    
    query.edit_message_text(
        "🛍 *Kategoriyalardan birini tanlang:*",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

MAHSULOTLAR = {
    "sabzavot": [
        ("Kartoshka", 5000, "kg"),
        ("Piyoz", 3000, "kg"),
        ("Sabzi", 4000, "kg"),
        ("Sholg'om", 3000, "kg"),
        ("Bodring", 6000, "kg"),
        ("Pomidor", 8000, "kg"),
        ("Turp", 4000, "kg"),
        ("Rediska", 5000, "kg"),
        ("Chesnok", 15000, "kg")
    ],
    "meva": [
        ("Olma", 10000, "kg"),
        ("Nok", 12000, "kg"),
        ("Banan", 15000, "kg"),
        ("Mandarin", 14000, "kg"),
        ("Gilos", 18000, "kg"),
        ("Qulupnay", 20000, "kg")
    ],
    "poliz": [
        ("Qovun", 8000, "dona"),
        ("Tarvuz", 6000, "dona")
    ]
}

savatlar = {}

def show_products(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    kat = query.data.replace("cat_", "")
    
    products = MAHSULOTLAR.get(kat, [])
    keyboard = []
    for nom, narx, birlik in products:
        keyboard.append([InlineKeyboardButton(
            f"{nom} - {narx} so'm/{birlik}",
            callback_data=f"add_{kat}_{nom}"
        )])
    
    keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="kategoriyalar")])
    
    query.edit_message_text(
        f"📋 *{kat.upper()} mahsulotlari:*\n\n"
        f"💡 Narxlar taxminiy. Aniq narxni kanaldan oling.",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def add_to_cart(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    data = query.data.split("_")
    kat = data[1]
    nom = data[2]
    
    product = next((p for p in MAHSULOTLAR[kat] if p[0] == nom), None)
    if not product:
        query.edit_message_text("❌ Mahsulot topilmadi.")
        return
    
    user_id = query.from_user.id
    if user_id not in savatlar:
        savatlar[user_id] = []
    
    for item in savatlar[user_id]:
        if item['nom'] == nom:
            item['soni'] += 1
            break
    else:
        savatlar[user_id].append({
            'nom': nom,
            'narx': product[1],
            'birlik': product[2],
            'soni': 1
        })
    
    query.edit_message_text(
        f"✅ *{nom}* savatga qo'shildi!",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Savatni ko'rish", callback_data="savat_ko'rish")],
            [InlineKeyboardButton("⬅️ Davom etish", callback_data=f"cat_{kat}")]
        ])
    )

def view_cart(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    
    if user_id not in savatlar or not savatlar[user_id]:
        query.edit_message_text(
            "🛒 *Savat bo'sh.*",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Kategoriyalar", callback_data="kategoriyalar")
            ]])
        )
        return
    
    cart = savatlar[user_id]
    text = "🛒 *Savat:*\n\n"
    total = 0
    for item in cart:
        item_total = item['narx'] * item['soni']
        text += f"• {item['nom']} x {item['soni']} {item['birlik']} = {item_total} so'm\n"
        total += item_total
    text += f"\n💰 *Jami: {total} so'm*"
    
    keyboard = [
        [InlineKeyboardButton("📦 Buyurtma berish", callback_data="buyurtma_berish")],
        [InlineKeyboardButton("🗑 Savatni tozalash", callback_data="savat_tozalash")],
        [InlineKeyboardButton("⬅️ Kategoriyalar", callback_data="kategoriyalar")]
    ]
    
    query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def clear_cart(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    
    if user_id in savatlar:
        savatlar[user_id] = []
    
    query.edit_message_text(
        "🗑 *Savat tozalandi.*",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Kategoriyalar", callback_data="kategoriyalar")
        ]])
    )

def order_start(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    
    if user_id not in savatlar or not savatlar[user_id]:
        query.edit_message_text(
            "❌ *Savat bo'sh.* Avval mahsulot qo'shing.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Kategoriyalar", callback_data="kategoriyalar")
            ]])
        )
        return
    
    query.edit_message_text(
        "📝 *Buyurtma berish*\n\n"
        "Iltimos, ismingizni kiriting:",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Bekor qilish", callback_data="kategoriyalar")
        ]])
    )
    context.user_data['step'] = 'ism'

def handle_text(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = safe_str(update.message.text)
    
    if 'step' not in context.user_data:
        update.message.reply_text("Iltimos, /start buyrug'ini bosing.")
        return
    
    step = context.user_data['step']
    
    if step == 'ism':
        if len(text) < 2:
            update.message.reply_text("❌ Ism juda qisqa. Qayta kiriting:")
            return
        context.user_data['ism'] = text
        context.user_data['step'] = 'telefon'
        update.message.reply_text(
            "📞 *Telefon raqamingizni kiriting:*\n"
            "Format: +998901234567",
            parse_mode='Markdown'
        )
    
    elif step == 'telefon':
        if not validate_phone(text):
            update.message.reply_text(
                "❌ Noto'g'ri format. Qayta kiriting:\n"
                "Masalan: +998901234567"
            )
            return
        context.user_data['telefon'] = text
        context.user_data['step'] = 'manzil'
        update.message.reply_text("📍 *Manzilingizni kiriting:* (ko'cha, uy raqami)", parse_mode='Markdown')
    
    elif step == 'manzil':
        if len(text) < 5:
            update.message.reply_text("❌ Manzil juda qisqa. Qayta kiriting:")
            return
        context.user_data['manzil'] = text
        save_order(update, context)
        context.user_data.clear()

def save_order(update, context):
    user_id = update.effective_user.id
    
    cursor.execute('''
        INSERT OR REPLACE INTO mijozlar 
        (user_id, ism, telefon, manzil, qoshilgan_sana, oxirgi_faollik) 
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        context.user_data.get('ism', ''),
        context.user_data.get('telefon', ''),
        context.user_data.get('manzil', ''),
        datetime.now(),
        datetime.now()
    ))
    conn.commit()
    
    cart = savatlar.get(user_id, [])
    product_text = ", ".join([f"{item['nom']} x{item['soni']}" for item in cart])
    total = sum(item['narx'] * item['soni'] for item in cart)
    
    cursor.execute('''
        INSERT INTO buyurtmalar (user_id, mahsulotlar, umumiy_narx, holat, sana) 
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, product_text, total, "yangi", datetime.now()))
    order_id = cursor.lastrowid
    conn.commit()
    
    try:
        context.bot.send_message(
            ADMIN_ID,
            f"🆕 *Yangi buyurtma!*\n\n"
            f"👤 Ism: {context.user_data['ism']}\n"
            f"📞 Tel: {context.user_data['telefon']}\n"
            f"📍 Manzil: {context.user_data['manzil']}\n"
            f"🛍 Mahsulotlar: {product_text}\n"
            f"💰 Jami: {total} so'm\n"
            f"🆔 Buyurtma №: {order_id}",
            parse_mode='Markdown'
        )
    except:
        pass
    
    savatlar[user_id] = []
    
    update.message.reply_text(
        f"✅ *Buyurtmangiz qabul qilindi!*\n\n"
        f"Tez orada siz bilan bog'lanamiz.\n"
        f"Buyurtma raqami: #{order_id}",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 Bosh menyu", callback_data="kategoriyalar")
        ]])
    )

def admin_panel(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    
    if not is_admin(user_id):
        query.edit_message_text("❌ Siz admin emassiz.")
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton("📦 Yangi buyurtmalar", callback_data="admin_orders")],
        [InlineKeyboardButton("👥 Mijozlar", callback_data="admin_users")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="kategoriyalar")]
    ]
    
    query.edit_message_text(
        "⚙️ *Admin panel*",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def admin_stats(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    cursor.execute("SELECT COUNT(*) FROM mijozlar")
    users_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM buyurtmalar WHERE holat='yangi'")
    new_orders = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM buyurtmalar WHERE date(sana)=date('now')")
    today_orders = cursor.fetchone()[0]
    
    query.edit_message_text(
        f"📊 *Statistika*\n\n"
        f"👥 Jami mijozlar: {users_count}\n"
        f"🆕 Yangi buyurtmalar: {new_orders}\n"
        f"📅 Bugungi buyurtmalar: {today_orders}",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
        ]])
    )

def admin_orders(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    cursor.execute("SELECT id, ism, mahsulotlar, umumiy_narx, sana FROM buyurtmalar WHERE holat='yangi' ORDER BY id DESC LIMIT 5")
    orders = cursor.fetchall()
    
    if not orders:
        query.edit_message_text(
            "📦 *Yangi buyurtmalar yo'q*",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
            ]])
        )
        return
    
    text = "📦 *Yangi buyurtmalar:*\n\n"
    for o in orders:
        text += f"#{o[0]} - {o[1]}: {o[2]} = {o[3]} so'm\n"
    
    query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
        ]])
    )

def admin_users(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    cursor.execute("SELECT ism, telefon, user_id FROM mijozlar ORDER BY oxirgi_faollik DESC LIMIT 5")
    users = cursor.fetchall()
    
    text = "👥 *Oxirgi mijozlar:*\n\n"
    for u in users:
        text += f"• {u[0]} - {u[1] or 'tel yoʻq'}\n"
    
    query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")
        ]])
    )

def error_handler(update: Update, context: CallbackContext):
    logger.error(f"Xatolik: {context.error}")

def main():
    if not TOKEN:
        logger.error("TOKEN topilmadi! BOT_TOKEN environment variable ni sozlang.")
        return
    
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(check_subscription, pattern="check"))
    dp.add_handler(CallbackQueryHandler(kategoriyalar, pattern="kategoriyalar"))
    dp.add_handler(CallbackQueryHandler(show_products, pattern="^cat_"))
    dp.add_handler(CallbackQueryHandler(add_to_cart, pattern="^add_"))
    dp.add_handler(CallbackQueryHandler(view_cart, pattern="savat_ko'rish"))
    dp.add_handler(CallbackQueryHandler(clear_cart, pattern="savat_tozalash"))
    dp.add_handler(CallbackQueryHandler(order_start, pattern="buyurtma_berish"))
    dp.add_handler(CallbackQueryHandler(admin_panel, pattern="admin_panel"))
    dp.add_handler(CallbackQueryHandler(admin_stats, pattern="admin_stats"))
    dp.add_handler(CallbackQueryHandler(admin_orders, pattern="admin_orders"))
    dp.add_handler(CallbackQueryHandler(admin_users, pattern="admin_users"))
    dp.add_handler(CallbackQueryHandler(kategoriyalar, pattern="start"))
    
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
    dp.add_error_handler(error_handler)
    
    updater.start_polling()
    logger.info("✅ Bot ishga tushdi! @Yoriyev_market ga yozib ko'ring.")
    updater.idle()

if __name__ == "__main__":
    main()
