# telegram_bot.py
import os
import json
import time
import threading
import uuid
from functools import wraps
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                          filters, CallbackQueryHandler, ContextTypes)

# --- Config ---
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
DATA_FILE = "data.json"

# --- Data Storage ---
data = {
    "single_inputs": {},  # token: message dict
    "batch_sessions": {}, # user_id: [messages]
    "required_channels": [],
}

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data.update(json.load(f))

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

async def send_required_channel_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, token):
    buttons = [[InlineKeyboardButton("Join", url=ch)] for ch in data["required_channels"]]
    buttons.append([InlineKeyboardButton("✅ Try Again", callback_data=f"tryagain|{token}")])
    await update.message.reply_text(
        "📢 Please join all required channels before proceeding:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

def is_user_joined(user_id, context):
    for ch_url in data["required_channels"]:
        chat_id = ch_url.split("/")[-1]
        try:
            member = context.bot.get_chat_member(chat_id, user_id)
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
    await update.message.reply_text("📥 Send channel links (one per line):")
    context.user_data["awaiting_channels"] = True

@admin_only
async def allcommands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cmds = [
        "/batch - Start batch mode",
        "/generatebatch - Generate batch link",
        "/batchoff - Cancel batch",
        "/setchannels - Set required channels",
        "/allcommands - Show all commands"
    ]
    await update.message.reply_text("\n".join(cmds))

# --- Input Handler ---
async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_channels"):
        links = update.message.text.splitlines()
        data["required_channels"] = [link.strip() for link in links if link.strip()]
        save_data()
        context.user_data["awaiting_channels"] = False
        await update.message.reply_text("✅ Required channels updated.")
        return

    if str(ADMIN_ID) in data["batch_sessions"]:
        msg = update.message.to_dict()
        data["batch_sessions"][str(ADMIN_ID)].append(msg)
        save_data()
        return

    token = generate_token()
    data["single_inputs"][token] = {"type": "single", "message": update.message.to_dict()}
    save_data()
    await update.message.reply_text(f"🔗 Link generated: https://t.me/{context.bot.username}?start={token}")

# --- /start <token> handler ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("👋 Welcome!")
        return

    token = args[0]
    if token not in data["single_inputs"]:
        await update.message.reply_text("❌ Invalid or expired link.")
        return

    if data["required_channels"]:
        if not is_user_joined(update.effective_user.id, context):
            await send_required_channel_prompt(update, context, token)
            return

    record = data["single_inputs"][token]
    sent_ids = []

    if record["type"] == "single":
        msg = await context.bot.send_message(update.effective_chat.id, record["message"]["text"])
        sent_ids.append(msg.message_id)
    else:
        for msg_data in record["messages"]:
            msg = await context.bot.send_message(update.effective_chat.id, msg_data.get("text", ""))
            sent_ids.append(msg.message_id)

    footer = await update.message.reply_text(
        "This will be auto-deleted after 30 min",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Open", url="https://example.com")]]
        )
    )
    sent_ids.append(footer.message_id)
    threading.Thread(target=lambda: asyncio.run(schedule_deletion(context, update.effective_chat.id, sent_ids))).start()

async def tryagain_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, token = query.data.split("|")
    await start(update, context)
    await query.answer()

async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❓ Unknown command. Use /allcommands to see available commands.")

if __name__ == '__main__':
    import asyncio
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("batch", batch))
    app.add_handler(CommandHandler("batchoff", batchoff))
    app.add_handler(CommandHandler("generatebatch", generatebatch))
    app.add_handler(CommandHandler("setchannels", setchannels))
    app.add_handler(CommandHandler("allcommands", allcommands))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(tryagain_callback, pattern=r"^tryagain|"))
    app.add_handler(MessageHandler(filters.ALL, handle_input))
    app.add_handler(MessageHandler(filters.COMMAND, fallback))

    app.run_polling(drop_pending_updates=True)

