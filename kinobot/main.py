from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackQueryHandler,
    CallbackContext,
    CallbackDataCache,
    ConversationHandler
)
import sqlite3

TOKEN = ""
ADMIN_ID = 123456789

db = sqlite3.connect("movies.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS movies (
    code TEXT PRIMARY KEY,
    file_id TEXT,
    captions TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS channels (
    channel TEXT PRIMARY KEY
)
""")
db.commit()

MOVIE_CODE, MOVIE_FILE, MOVIE_CAPTION = range(3)


def get_channels():
    cursor.execute("SELECT channel FROM channels")
    return [i[0] for i in cursor.fetchall()]


def check_subscription(bot, user_id):
    channels = get_channels()
    if not channels:
        return True

    for channel in channels:
        try:
            member = bot.get_chat_member(channel, user_id)
            if member.status in ["left", "kicked"]:
                return False
        except:
            return False
    return True


def subscription_keyboard():
    keyboard = []

    for ch in get_channels():
        if ch.startswith("@"):
            url = f"https://t.me/{ch[1:]}"
        else:
            url = ch

        keyboard.append([
            InlineKeyboardButton(f"📢 {ch}", url=url)
        ])
    keyboard.append([
        InlineKeyboardButton("Tekshirish ✅", callback_data="check_sub")
    ])
    return InlineKeyboardMarkup(keyboard)


def start(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id

    if not check_subscription(context.bot, user_id):
        update.message.reply_text("Botdan foydalanish uchun kanallarga obuna bo'ling !",
                                  reply_markup=subscription_keyboard())
        return

    update.message.reply_text("🎬 Assalomu ALaykum\n"
                              "Kino kodini kiriting: ")


def get_movies(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id

    if not check_subscription(context.bot, user_id):
        update.message.reply_text("Avval kanalga obuna bo'l, shoptoli ⛔",
                                  reply_markup=subscription_keyboard())
        return

    code = update.message.text.strip()
    cursor.execute("SELECT file_id, captions FROM movies WHERE code = ?", (code,))
    result = cursor.fetchone()

    if result:
        file_id, caption = result
        update.message.reply_video(video=file_id, caption=caption)
    else:
        update.message.reply_text("❌ Kechirasiz, kod noto'g'ri.")


def check_subscription_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    query.answer()

    if check_subscription(context.bot, user_id):
        query.message.edit_text(
            "✅ Obuna tasqilandi \n\n"
            "🎬 Endi kod bo'yicha kino yuklab olishingiz mumkin"
        )
    else:
        query.answer(
            "Hali barcha kanallarga obuna bo'lmagansiz ❌",
            show_alert=True
        )


def add_channels(update: Update, context: CallbackContext):
    if update.message.from_user.id != ADMIN_ID:
        return

    if not context.args:
        update.message.reply_text("Misol: /addchannels @kanal")
        return

    channel = context.args[0]
    cursor.execute("INSERT OR IGNORE INTO channels VALUES (?)", (channel,))
    db.commit()

    update.message.reply_text(f"Kanal qo'shildi: {channel} ✅")


def delete_channels(update: Update, context: CallbackContext):
    if update.message.from_user.id != ADMIN_ID:
        return

    if not context.args:
        update.message.reply_text("Misol: /delchannel @kanal")
        return

    channel = context.args[0]
    cursor.execute("DELETE FROM channels WHERE channel=?", (channel,))
    db.commit()

    update.message.reply_text(f"🗑 Kanal o'chirildi: {channel} ✅")


def list_channels(update: Update, context: CallbackContext):
    if update.message.from_user.id != ADMIN_ID:
        return

    channels = get_channels()
    if not channels:
        update.message.reply_text("📭 Kanallar yo'q.")

    text = "📢 Kanallar ro'yhati\n\n"
    for ch in channels:
        text += f"{ch}\n"

    update.message.reply_text(text)


def admin_start(update: Update, context: CallbackContext):
    if update.message.from_user.id != ADMIN_ID:
        update.message.reply_text("Siz admin emasiz ⛔")
        return ConversationHandler.END

    update.message.reply_text("📝 Kino kodini kiriting: ")
    return MOVIE_CODE


def admin_code(update: Update, context: CallbackContext):
    context.user_data['code'] = update.message.text.strip()
    update.message.reply_text("Endi kino, yoki videoni yuboring: ")
    return MOVIE_FILE


def admin_file(update: Update, context: CallbackContext):
    if not update.message.video:
        update.message.reply_text("Faqat video yuboring !")
        return MOVIE_FILE

    context.user_data["file_id"] = update.message.video.file_id
    update.message.reply_text("Video tagidagi matinni yuboring...")
    return MOVIE_CAPTION


def admin_caption(update: Update, context: CallbackContext):
    cursor.execute("""
    INSERT OR REPLACE INTO movies VALUES (?, ?, ?)
    """, (
        context.user_data["code"],
        context.user_data["file_id"],
        update.message.text
    ))
    db.commit()

    update.message.reply_text("Kino saqlandi ✅")
    return ConversationHandler.END


def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("Bekor qilindi")
    return ConversationHandler.END


def main():
    updater = Updater(TOKEN)
    dp = updater.dispatcher

    admin_conv = ConversationHandler(
        entry_points=[CommandHandler("admin", admin_start)],
        states={
            MOVIE_CODE: [MessageHandler(Filters.text & ~Filters.command, admin_code)],
            MOVIE_FILE: [MessageHandler(Filters.video & ~Filters.command, admin_file)],
            MOVIE_CAPTION: [MessageHandler(Filters.text, admin_caption)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("addchannels", add_channels))
    dp.add_handler(CommandHandler("delchannel", delete_channels))
    dp.add_handler(CommandHandler("channel", list_channels))

    dp.add_handler(admin_conv)
    dp.add_handler(CallbackQueryHandler(check_subscription_callback, pattern="check_sub"))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, get_movies))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
