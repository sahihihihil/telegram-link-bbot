import os
import json
import uuid
import asyncio
import logging
from functools import wraps
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
    "button_url": "https://example.com"
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
        context.user_data.clear()
        data["required_channels"] = []
        save_data()
        await update.message.reply_text("❌ Channel setup cancelled and all required channels removed.")
    else:
        await update.message.reply_text("ℹ️ No channel setup in progress.")

@admin_only
async def removerequiredchannel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data["required_channels"] = []
    save_data()
    await update.message.reply_text("✅ All required channels have been removed.")

@admin_only
async def setbutton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📝 Send the new button text:")
    context.user_data.clear()
    context.user_data["awaiting_button_text"] = True

@admin_only
async def cancelsetbutton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_button_text") or context.user_data.get("awaiting_button_url"):
        context.user_data.clear()
        await update.message.reply_text("❌ Button setup cancelled.")
    else:
        await update.message.reply_text("ℹ️ No button setup in progress.")

@admin_only
async def listlinks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not data["single_inputs"]:
        await update.message.reply_text("🔍 No links generated yet.")
        return
    lines = []
    for token, info in data["single_inputs"].items():
        lines.append(f"🔗 [{token} - {info['type']}](https://t.me/{context.bot.username}?start={token})")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

@admin_only
async def deletelink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ Usage: /deletelink <token>")
        return
    token = context.args[0]
    if token in data["single_inputs"]:
        data["single_inputs"].pop(token)
        save_data()
        await update.message.reply_text(f"✅ Link `{token}` deleted.", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Token not found.")

@admin_only
async def deletealllinks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data["single_inputs"].clear()
    save_data()
    await update.message.reply_text("⚠️ All links deleted.")

@admin_only
async def allcommands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cmds = [
        "/batch - Start batch mode",
        "/generatebatch - Generate batch link",
        "/batchoff - Cancel batch",
        "/setchannels - Set required channels",
        "/cancelsetchannels - Cancel setting channels and remove all",
        "/removerequiredchannel - Remove all required channels",
        "/setbutton - Set button text and link",
        "/cancelsetbutton - Cancel setting button",
        "/listlinks - Show all generated links",
        "/deletelink <token> - Delete a specific link",
        "/deletealllinks - Delete all generated links",
        "/allcommands - Show all commands"
    ]
    await update.message.reply_text("\n".join(cmds))

# --- Message, Start, and Callback Handlers ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if context.user_data.get("awaiting_button_text"):
        context.user_data["button_text"] = update.message.text
        await update.message.reply_text("🔗 Now send the button URL:")
        context.user_data.pop("awaiting_button_text")
        context.user_data["awaiting_button_url"] = True
    elif context.user_data.get("awaiting_button_url"):
        data["button_text"] = context.user_data.pop("button_text")
        data["button_url"] = update.message.text
        context.user_data.clear()
        save_data()
        await update.message.reply_text("✅ Button text and URL updated.")
    elif context.user_data.get("awaiting_channels"):
        channels = update.message.text.splitlines()
        resolved = []
        for username in channels:
            try:
                chat = await context.bot.get_chat(username.strip())
                resolved.append({"chat_id": chat.id, "username": username.strip()})
            except:
                pass
        data["required_channels"] = resolved
        save_data()
        context.user_data.clear()
        await update.message.reply_text("✅ Required channels updated.")
    else:
        token = generate_token()
        data["single_inputs"][token] = {
            "type": "single",
            "message": {
                "chat_id": update.effective_chat.id,
                "message_id": update.message.message_id
            }
        }
        save_data()
        await update.message.reply_text(f"✅ Link generated: https://t.me/{context.bot.username}?start={token}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Invalid or missing token.")
        return
    token = context.args[0]
    if token not in data["single_inputs"]:
        await update.message.reply_text("❌ This link is no longer valid.")
        return

    if not await is_user_joined(update.effective_user.id, context):
        buttons = [[InlineKeyboardButton(ch["username"], url=f"https://t.me/{ch['username'].lstrip('@')}") for ch in data["required_channels"]]]
        buttons.append([InlineKeyboardButton("✅ Try Again", callback_data=f"tryagain|{token}")])
        await update.message.reply_text("🚫 Please join all required channels to continue:", reply_markup=InlineKeyboardMarkup(buttons))
        return

    info = data["single_inputs"][token]
    message_ids = []
    if info["type"] == "single":
        sent = await context.bot.copy_message(chat_id=update.effective_chat.id,
                                              from_chat_id=info["message"]["chat_id"],
                                              message_id=info["message"]["message_id"])
        message_ids.append(sent.message_id)
    elif info["type"] == "batch":
        for msg in info["messages"]:
            sent = await context.bot.copy_message(chat_id=update.effective_chat.id,
                                                  from_chat_id=msg["chat_id"],
                                                  message_id=msg["message_id"])
            message_ids.append(sent.message_id)

    footer = await update.message.reply_text("🕒 This will be auto-deleted after 30 min.",
                                             reply_markup=InlineKeyboardMarkup(
                                                 [[InlineKeyboardButton(data["button_text"], url=data["button_url"])]])
                                             )
    message_ids.append(footer.message_id)
    asyncio.create_task(schedule_deletion(context, update.effective_chat.id, message_ids))

async def try_again(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    token = query.data.split("|")[1]
    update.message = query.message
    context.args = [token]
    await start(update, context)

# --- Main ---
app = ApplicationBuilder().token(TOKEN).drop_pending_updates(True).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("batch", batch))
app.add_handler(CommandHandler("batchoff", batchoff))
app.add_handler(CommandHandler("generatebatch", generatebatch))
app.add_handler(CommandHandler("setchannels", setchannels))
app.add_handler(CommandHandler("cancelsetchannels", cancelsetchannels))
app.add_handler(CommandHandler("removerequiredchannel", removerequiredchannel))
app.add_handler(CommandHandler("setbutton", setbutton))
app.add_handler(CommandHandler("cancelsetbutton", cancelsetbutton))
app.add_handler(CommandHandler("listlinks", listlinks))
app.add_handler(CommandHandler("deletelink", deletelink))
app.add_handler(CommandHandler("deletealllinks", deletealllinks))
app.add_handler(CommandHandler("allcommands", allcommands))
app.add_handler(CallbackQueryHandler(try_again))
app.add_handler(MessageHandler(filters.ALL, handle_message))

app.run_polling()
