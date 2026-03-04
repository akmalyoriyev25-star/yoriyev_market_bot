import logging
import sqlite3
from datetime import datetime
from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, Update
)
from telegram.ext import (
    Updater, CommandHandler, CallbackQueryHandler, 
    MessageHandler, Filters, ConversationHandler, CallbackContext
)

# --- KONFIGURATSIYA ---
TOKEN = "8743932506:AAG38yzOL7ohnfsFE7-YGtCBbUdPZ0JEDVs"
ADMIN_ID = 123456789  # O'zingizning Telegram ID'ingizni shu yerga yozing!
CHANNEL_USERNAME = "@yoriyev_market"
BOT_USERNAME = "Yoriyev_market_bot"
ADMIN_PHONE = "+998883092500"

# Loglarni sozlash
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- MA'LUMOTLAR BAZASI ---
def init_db():
    conn = sqlite3.connect('market.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    # Users jadvali
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, first_name TEXT, username TEXT, 
        phone TEXT, address TEXT, registered_at TEXT, 
        referred_by INTEGER, discount_count INTEGER DEFAULT 0, total_orders INTEGER DEFAULT 0)''')
    # Orders jadvali
    cursor.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, 
        items TEXT, status TEXT DEFAULT 'yangi', created_at TEXT)''')
    # Feedback jadvali
    cursor.execute('''CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, 
        text TEXT, type TEXT, created_at TEXT)''')
    # Promotions jadvali
    cursor.execute('''CREATE TABLE IF NOT EXISTS promotions (id INTEGER PRIMARY KEY, text TEXT)''')
    cursor.execute("INSERT OR IGNORE INTO promotions (id, text) VALUES (1, 'Hozircha aksiyalar yoʻq.')")
    conn.commit()
    return conn

db = init_db()

# --- HOLATLAR (States) ---
(ORDER_ITEMS, ORDER_NAME, ORDER_PHONE, ORDER_ADDRESS, 
 FEEDBACK_TYPE, FEEDBACK_TEXT, ADMIN_BROADCAST, EDIT_PROMO) = range(8)

# --- YORDAMCHI FUNKSIYALAR ---
def is_subscribed(bot, user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def get_main_menu():
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
    return InlineKeyboardMarkup(keyboard)

# --- START VA RO'YXATDAN O'TISH ---
def start(update: Update, context: CallbackContext):
    user = update.effective_user
    args = context.args
    
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user.id,))
    if not cursor.fetchone():
        ref_by = None
        if args and args[0].startswith('ref_'):
            ref_id = args[0].split('_')[1]
            if ref_id.isdigit() and int(ref_id) != user.id:
                ref_by = int(ref_id)
        
        cursor.execute("INSERT INTO users (user_id, first_name, username, registered_at, referred_by) VALUES (?,?,?,?,?)",
                       (user.id, user.first_name, user.username, datetime.now().strftime("%Y-%m-%d %H:%M"), ref_by))
        db.commit()

    if not is_subscribed(context.bot, user.id):
        text = f"🌟 Assalomu alaykum {user.first_name}!\nBotdan foydalanish uchun kanalimizga a'zo bo'ling."
        btns = [[InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")],
                [InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")]]
        update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(btns))
        return

    update.message.reply_text("🏠 Yoriyev Market botiga xush kelibsiz!", reply_markup=get_main_menu())

# --- ASOSIY HANDLERLAR ---
def handle_callbacks(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    cursor = db.cursor()

    if data == "check_sub":
        if is_subscribed(context.bot, user_id):
            query.answer("✅ Rahmat!")
            query.edit_message_text("🏠 Bosh menyu", reply_markup=get_main_menu())
        else:
            query.answer("❌ Kanalga a'zo bo'lmadingiz!", show_alert=True)

    elif data == "main_menu":
        query.edit_message_text("🏠 Bosh menyu", reply_markup=get_main_menu())

    elif data == "menu_products":
        text = f"🛒 Mahsulotlar\n\nKerakli mahsulotlarni tanlab, buyurtma bering.\n👉 {CHANNEL_USERNAME}"
        kb = [[InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL_USERNAME[1:]}"),
               InlineKeyboardButton("✅ Buyurtma berish", callback_data="order_start")]]
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

    elif data == "menu_promo":
        promo = cursor.execute("SELECT text FROM promotions WHERE id=1").fetchone()
        text = f"📢 Aksiyalar\n\n{promo['text'] if promo else 'Hozircha yoq.'}"
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]))

    elif data == "menu_partners":
        text = "🤝 Hamkorlarimiz\n\nBiz bilan hamkorlik qilayotgan kanallar va do'konlar."
        kb = [[InlineKeyboardButton("🔗 Kanalga o'tish", url="https://t.me/hamkorlarimiz_yoriyev_market")],
              [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

    elif data == "menu_about":
        text = f"📌 Yoriyev Market – Peshku tumanidagi xizmat.\n\n📍 Manzil: Buxoro, Chalmagadoy.\n📞 Tel: {ADMIN_PHONE}"
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]))

    elif data == "menu_contact":
        text = f"📞 Admin bilan bog'lanish\n\nAdmin: @akmalyoriyev\nTel: {ADMIN_PHONE}"
        kb = [[InlineKeyboardButton("👤 Profil", url="https://t.me/akmalyoriyev")],
              [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

    elif data == "menu_referral":
        count = cursor.execute("SELECT COUNT(*) as c FROM users WHERE referred_by=?", (user_id,)).fetchone()['c']
        discount = cursor.execute("SELECT discount_count FROM users WHERE user_id=?", (user_id,)).fetchone()['discount_count']
        link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
        text = f"💡 Taklif qilish tizimi\n\n🔗 Havolangiz:\n{link}\n\nTakliflar: {count}\nChegirmalar: {discount}"
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]))

    elif data == "menu_complaint":
        kb = [[InlineKeyboardButton("⚠️ Shikoyat", callback_data="type_shikoyat"),
               InlineKeyboardButton("💡 Taklif", callback_data="type_taklif")],
              [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]
        query.edit_message_text("Shikoyat yoki taklifingizni qoldiring:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("type_"):
        context.user_data['fb_type'] = data.split('_')[1]
        query.edit_message_text(f"📝 {context.user_data['fb_type'].capitalize()}ingizni batafsil yozing:")
        return FEEDBACK_TEXT

    elif data == "menu_payment":
        text = "💳 To'lov tizimi\n\nTo'lov: Naqd, Click, Payme.\nMahsulot kelgandan so'ng amalga oshiriladi."
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]))

# --- BUYURTMA CONVERSATION ---
def order_init(update: Update, context: CallbackContext):
    update.callback_query.answer()
    update.callback_query.edit_message_text("📝 Mahsulotlar ro'yxatini va miqdorini yozing:")
    return ORDER_ITEMS

def order_get_items(update: Update, context: CallbackContext):
    context.user_data['items'] = update.message.text
    kb = [[KeyboardButton("👤 Profilni yuborish", request_contact=True)], [KeyboardButton("✍️ Ism yozish")]]
    update.message.reply_text("Ismingizni kiriting:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return ORDER_NAME

def order_get_name(update: Update, context: CallbackContext):
    if update.message.contact:
        context.user_data['name'] = update.message.contact.first_name
        context.user_data['phone'] = update.message.contact.phone_number
        update.message.reply_text("📍 Manzilingizni to'liq yozing:", reply_markup=ReplyKeyboardRemove())
        return ORDER_ADDRESS
    context.user_data['name'] = update.message.text
    kb = [[KeyboardButton("📱 Telefon raqamni yuborish", request_contact=True)]]
    update.message.reply_text("Telefon raqamingizni yuboring:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return ORDER_PHONE

def order_get_phone(update: Update, context: CallbackContext):
    context.user_data['phone'] = update.message.contact.phone_number if update.message.contact else update.message.text
    update.message.reply_text("📍 Manzilingizni to'liq yozing:", reply_markup=ReplyKeyboardRemove())
    return ORDER_ADDRESS

def order_finish(update: Update, context: CallbackContext):
    addr = update.message.text
    u_id = update.effective_user.id
    ud = context.user_data
    
    cursor = db.cursor()
    cursor.execute("INSERT INTO orders (user_id, items, created_at) VALUES (?, ?, ?)",
                   (u_id, ud['items'], datetime.now().strftime("%Y-%m-%d %H:%M")))
    order_id = cursor.lastrowid
    
    # Referral Logic: Agar birinchi buyurtma bo'lsa
    user_info = cursor.execute("SELECT * FROM users WHERE user_id=?", (u_id,)).fetchone()
    if user_info['total_orders'] == 0 and user_info['referred_by']:
        ref_id = user_info['referred_by']
        cursor.execute("UPDATE users SET discount_count = discount_count + 1 WHERE user_id=?", (ref_id,))
        cursor.execute("UPDATE users SET discount_count = discount_count + 1 WHERE user_id=?", (u_id,))
        try: context.bot.send_message(ref_id, "🎉 Do'stingiz buyurtma berdi! Sizga chegirma qo'shildi.")
        except: pass
    
    cursor.execute("UPDATE users SET total_orders = total_orders + 1 WHERE user_id=?", (u_id,))
    db.commit()

    # Admin notification
    admin_msg = (f"🆕 YANGI BUYURTMA №{order_id}\n👤 Ism: {ud['name']}\n📞 Tel: {ud['phone']}\n"
                 f"📍 Manzil: {addr}\n📦 Mahsulotlar: {ud['items']}\n🔗 Profil: tg://user?id={u_id}")
    context.bot.send_message(ADMIN_ID, admin_msg)

    update.message.reply_text("✅ Buyurtmangiz qabul qilindi! Admin bog'lanadi.", reply_markup=get_main_menu())
    return ConversationHandler.END

# --- FEEDBACK VA ADMIN ---
def feedback_save(update: Update, context: CallbackContext):
    text = update.message.text
    f_type = context.user_data.get('fb_type', 'shikoyat')
    u_id = update.effective_user.id
    
    db.execute("INSERT INTO feedback (user_id, text, type, created_at) VALUES (?,?,?,?)",
               (u_id, text, f_type, datetime.now().strftime("%Y-%m-%d %H:%M")))
    db.commit()
    
    context.bot.send_message(ADMIN_ID, f"⚠️ Yangi {f_type}:\n👤 ID: {u_id}\n📝 {text}")
    update.message.reply_text(f"✅ {f_type.capitalize()}ingiz yuborildi!", reply_markup=get_main_menu())
    return ConversationHandler.END

def admin_panel(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID: return
    cursor = db.cursor()
    users = cursor.execute("SELECT COUNT(*) as c FROM users").fetchone()['c']
    orders = cursor.execute("SELECT COUNT(*) as c FROM orders WHERE status='yangi'").fetchone()['c']
    
    text = f"📊 Statistika\n\n👥 Foydalanuvchilar: {users}\n🆕 Yangi buyurtmalar: {orders}"
    kb = [[InlineKeyboardButton("📢 Xabar yuborish", callback_data="adm_broadcast")],
          [InlineKeyboardButton("✏️ Aksiyani o'zgartirish", callback_data="adm_promo")]]
    update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

# --- MAIN RUNNER ---
def main():
    updater = Updater(TOKEN)
    dp = updater.dispatcher

    # Conversation Handlers
    order_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(order_init, pattern="order_start")],
        states={
            ORDER_ITEMS: [MessageHandler(Filters.text & ~Filters.command, order_get_items)],
            ORDER_NAME: [MessageHandler(Filters.text | Filters.contact, order_get_name)],
            ORDER_PHONE: [MessageHandler(Filters.text | Filters.contact, order_get_phone)],
            ORDER_ADDRESS: [MessageHandler(Filters.text & ~Filters.command, order_finish)],
        },
        fallbacks=[CommandHandler('cancel', lambda u,c: u.message.reply_text("Bekor qilindi.", reply_markup=get_main_menu()))]
    )
    
    fb_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_callbacks, pattern="type_")],
        states={FEEDBACK_TEXT: [MessageHandler(Filters.text & ~Filters.command, feedback_save)]},
        fallbacks=[]
    )

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("admin", admin_panel))
    dp.add_handler(order_conv)
    dp.add_handler(fb_conv)
    dp.add_handler(CallbackQueryHandler(handle_callbacks))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
