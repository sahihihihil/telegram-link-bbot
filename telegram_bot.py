# ... [existing imports stay the same] ...
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                          filters, CallbackQueryHandler, ContextTypes)

# --- Logging ---
logging.basicConfig(level=logging.INFO)

# --- Config ---
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
DATA_FILE = "data.json"

# --- Load or initialize data ---
data = {
    "single_inputs": {},
    "batch_sessions": {},
    "required_channels": [],
    "button_text": "Open",
    "button_url": "https://example.com",
    "promo_text": ""
}
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data.update(json.load(f))
else:
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

# --- Helpers ---
def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        return await func(update, context)
    return wrapper

def generate_token():
    return uuid.uuid4().hex[:8]

async def is_user_joined(user_id, context):
    for ch in data["required_channels"]:
        try:
            member = await context.bot.get_chat_member(ch["chat_id"], user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except:
            return False
    return True

async def schedule_deletion(context: ContextTypes.DEFAULT_TYPE, chat_id, message_ids):
    await asyncio.sleep(1800)
    for msg_id in message_ids:
        try:
            await context.bot.delete_message(chat_id, msg_id)
        except:
            pass

# --- Command Handlers ---
@admin_only
async def batch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data["batch_sessions"][str(ADMIN_ID)] = []
    save_data()
    await update.message.reply_text("📦 Batch mode ON. Send your messages.")

@admin_only
async def batchoff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data["batch_sessions"].pop(str(ADMIN_ID), None)
    save_data()
    await update.message.reply_text("❌ Batch mode cancelled.")

@admin_only
async def generatebatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = data["batch_sessions"].get(str(ADMIN_ID), [])
    if not session:
        await update.message.reply_text("❌ No inputs in batch.")
        return
    token = generate_token()
    data["single_inputs"][token] = {"type": "batch", "messages": session}
    data["batch_sessions"].pop(str(ADMIN_ID), None)
    save_data()
    await update.message.reply_text(f"✅ Batch link generated: https://t.me/{context.bot.username}?start={token}")

@admin_only
async def setchannels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📥 Send @channel usernames (one per line):")
    context.user_data["awaiting_channels"] = True

@admin_only
async def cancelsetchannels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_channels"):
        context.user_data["awaiting_channels"] = False
        await update.message.reply_text("❌ Channel setup cancelled.")
    else:
        await update.message.reply_text("ℹ️ No channel setup in progress.")

# --- NEW: clearsetchannels ---
@admin_only
async def clearsetchannels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data["required_channels"] = []
    save_data()
    await update.message.reply_text("✅ All required channels have been cleared.")  # NEW

# --- NEW: viewchannels ---
@admin_only
async def viewchannels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channels = data.get("required_channels", [])
    if not channels:
        await update.message.reply_text("ℹ️ No required channels are currently set.")
    else:
        channel_list = "\n".join(f"• {c['chat_id']}" for c in channels)
        await update.message.reply_text(f"📋 Required channels:\n{channel_list}")  # NEW

@admin_only
async def setbutton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📝 Send the new button text:")
    context.user_data["awaiting_button_text"] = True

@admin_only
async def cancelsetbutton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    changed = False
    for key in ["awaiting_button_text", "awaiting_button_url", "new_button_text"]:
        if context.user_data.pop(key, None) is not None:
            changed = True
    if changed:
        await update.message.reply_text("❌ Button setup cancelled.")
    else:
        await update.message.reply_text("ℹ️ No button setup in progress.")

@admin_only
async def allcommands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cmds = [
        "/batch - Start batch mode",
        "/generatebatch - Generate batch link",
        "/batchoff - Cancel batch",
        "/setchannels - Set required channels",
        "/cancelsetchannels - Cancel channel setup",
        "/clearsetchannels - Clear all required channels",  # NEW
        "/viewchannels - View current required channels",   # NEW
        "/setbutton - Set button text and link",
        "/cancelsetbutton - Cancel button setup",
        "/promotext - Set or clear promo message",
        "/allcommands - Show all commands"
    ]
    await update.message.reply_text("\n".join(cmds))

@admin_only
async def promotext(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("❌ Usage: /promotext <your promo text> or /promotext clear")
        return

    if args[0].lower() == "clear":
        data["promo_text"] = ""
        save_data()
        await update.message.reply_text("✅ Promo text cleared.")
    else:
        text = " ".join(args)
        data["promo_text"] = text
        save_data()
        await update.message.reply_text(f"✅ Promo text set to:\n\n{text}")

# --- Message Input Handler (Admin Only) ---
# [unchanged section below here]

# --- Token-based Delivery (/start <token>) ---
# [unchanged section here too]

# --- Callback Handler for "✅ Try Again" Button ---
# [unchanged section here too]

# --- Fallback for unknown commands ---
async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❓ Unknown command. Use /allcommands to see available commands.")

# --- Main ---
if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("batch", batch))
    app.add_handler(CommandHandler("batchoff", batchoff))
    app.add_handler(CommandHandler("generatebatch", generatebatch))
    app.add_handler(CommandHandler("setchannels", setchannels))
    app.add_handler(CommandHandler("cancelsetchannels", cancelsetchannels))
    app.add_handler(CommandHandler("clearsetchannels", clearsetchannels))  # NEW
    app.add_handler(CommandHandler("viewchannels", viewchannels))          # NEW
    app.add_handler(CommandHandler("setbutton", setbutton))
    app.add_handler(CommandHandler("cancelsetbutton", cancelsetbutton))
    app.add_handler(CommandHandler("promotext", promotext))
    app.add_handler(CommandHandler("allcommands", allcommands))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(tryagain_callback, pattern=r"^tryagain|"))
    app.add_handler(MessageHandler(filters.ALL, handle_input))
    app.add_handler(MessageHandler(filters.COMMAND, fallback))

    app.run_polling(drop_pending_updates=True)
