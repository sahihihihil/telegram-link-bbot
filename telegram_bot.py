import os
import json
import uuid
import asyncio
import threading
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
    "button_url": "https://example.com",
    "button_caption": "🔘 Tap below to continue",
    "join_text": "📢 Please join all required channels:",
    "auto_delete_time": 1800
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
    await asyncio.sleep(data.get("auto_delete_time", 1800))
    for msg_id in message_ids:
        try:
            await context.bot.delete_message(chat_id, msg_id)
        except:
            pass

# --- Command Handlers ---

@admin_only
async def setjointitle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("❌ Usage: /setjointitle <your message>")
        return

    data["join_text"] = " ".join(args)
    save_data()
    await update.message.reply_text(f"✅ Join prompt updated to:\n\n{data['join_text']}")

@admin_only
async def resetjointitle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data["join_text"] = "📢 Please join all required channels:"
    save_data()
    await update.message.reply_text("🔄 Join prompt reset to default.")

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

@admin_only
async def clearsetchannels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data["required_channels"] = []
    save_data()
    await update.message.reply_text("✅ Required channel list has been cleared.")

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
        "/clearsetchannels - Clear required channel list",
        "/setbutton - Set button text and link",
        "/cancelsetbutton - Cancel button setup",
        "/promotext - Set or clear promo message",
        "/listlinks - List all active links",
        "/deletelink <token> - Delete a specific link",
        "/deletealllinks - Delete all links",
        "/setjointitle - Set the join prompt message",
        "/resetjointitle - Reset join prompt to default",
        "/setautodeletetime <seconds> - Set message auto-delete time",
        "/showconfig - View current bot configuration",
        "/allcommands - Show all commands"
    ]
    await update.message.reply_text("\n".join(cmds))



@admin_only
async def promotext(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("❌ Usage: /promotext <button caption> or /promotext clear")
        return

    if args[0].lower() == "clear":
        data["button_caption"] = "🔘 Tap below to continue"
        save_data()
        await update.message.reply_text("✅ Button caption reset to default.")
    else:
        text = " ".join(args)
        data["button_caption"] = text
        save_data()
        await update.message.reply_text(f"""✅ Button caption set to:

{text}""")


@admin_only
async def listlinks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    messages = []
    if data["single_inputs"]:
        messages.append("🔗 *Single Links:*")
        for token, record in data["single_inputs"].items():
            type_label = "Batch" if record.get("type") == "batch" else "Single"
            messages.append(f"- `{token}` ({type_label})")
    else:
        messages.append("ℹ️ No single or batch links found.")

    await update.message.reply_text("\n".join(messages), parse_mode="Markdown")

@admin_only
async def deletelink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("❌ Usage: /deletelink <token>")
        return

    token = args[0]
    if token in data["single_inputs"]:
        del data["single_inputs"][token]
        save_data()
        await update.message.reply_text(f"✅ Link `{token}` deleted.", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Token not found.")

@admin_only
async def deletealllinks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data["single_inputs"].clear()
    data["batch_sessions"].clear()
    save_data()
    await update.message.reply_text("🗑️ All links (single & batch) have been deleted.")

# --- Message Input Handler (Admin Only) ---
async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this bot.")
        return

    if context.user_data.get("awaiting_channels"):
        usernames = update.message.text.splitlines()
        data["required_channels"] = []
        for u in usernames:
            u = u.strip()
            if u.startswith("@"):
                data["required_channels"].append({
                    "chat_id": u,
                    "url": f"https://t.me/{u[1:]}"
                })
        save_data()
        context.user_data["awaiting_channels"] = False
        await update.message.reply_text("✅ Required channels updated.")
        return

    if context.user_data.get("awaiting_button_text"):
        context.user_data["new_button_text"] = update.message.text.strip()
        await update.message.reply_text("🔗 Now send the new button URL:")
        context.user_data.pop("awaiting_button_text")
        context.user_data["awaiting_button_url"] = True
        return

    if context.user_data.get("awaiting_button_url"):
        url = update.message.text.strip()
        text = context.user_data.pop("new_button_text")
        data["button_text"] = text
        data["button_url"] = url
        save_data()
        context.user_data.pop("awaiting_button_url")
        await update.message.reply_text(f"✅ Button updated to: [{text}]({url})", parse_mode="Markdown")
        return

    if str(ADMIN_ID) in data["batch_sessions"]:
        msg_id = update.message.message_id
        data["batch_sessions"][str(ADMIN_ID)].append(msg_id)
        save_data()
        return

    token = generate_token()
    data["single_inputs"][token] = {"type": "single", "message_id": update.message.message_id}
    save_data()
    await update.message.reply_text(f"🖓 Link generated: https://t.me/{context.bot.username}?start={token}")

# --- Token-based Delivery (/start <token>) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("👋 Welcome!")
        return

    token = args[0]
    if token not in data["single_inputs"]:
        await update.message.reply_text("❌ Invalid or expired link.")
        return

    if data["required_channels"] and not await is_user_joined(update.effective_user.id, context):
        buttons = [[InlineKeyboardButton("Join", url=ch["url"])] for ch in data["required_channels"]]
        buttons.append([InlineKeyboardButton("✅ Try Again", callback_data=f"tryagain|{token}")])
        await update.message.reply_text(
            data.get("join_text", "📢 Please join all required channels:"),
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    record = data["single_inputs"][token]
    sent_ids = []

    if record["type"] == "single":
        copied = await context.bot.copy_message(update.effective_chat.id, ADMIN_ID, record["message_id"])
        sent_ids.append(copied.message_id)
    else:
        for msg_id in record["messages"]:
            copied = await context.bot.copy_message(update.effective_chat.id, ADMIN_ID, msg_id)
            sent_ids.append(copied.message_id)

    if data.get("promo_text"):
        promo = await update.message.reply_text(data["promo_text"])
        sent_ids.append(promo.message_id)

    button_msg = await update.message.reply_text(
        data.get("button_caption", "🔘 Tap below to continue"),
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton(data["button_text"], url=data["button_url"] or "https://example.com")]]
        )
    )
    sent_ids.append(button_msg.message_id)

    delete_note = await update.message.reply_text("_This will be auto-deleted after 30 min_", parse_mode="Markdown")
    sent_ids.append(delete_note.message_id)

    threading.Thread(target=lambda: asyncio.run(schedule_deletion(context, update.effective_chat.id, sent_ids))).start()

# --- Callback Handler for "✅ Try Again" Button ---
async def tryagain_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, token = query.data.split("|")
    user_id = query.from_user.id
    chat_id = query.message.chat.id

    if data["required_channels"] and not await is_user_joined(user_id, context):
        await query.answer("❌ You haven't joined all required channels.", show_alert=True)
        return

    record = data["single_inputs"].get(token)
    if not record:
        await query.message.reply_text("❌ Invalid or expired link.")
        await query.answer()
        return

    sent_ids = []

    if record["type"] == "single":
        copied = await context.bot.copy_message(chat_id, ADMIN_ID, record["message_id"])
        sent_ids.append(copied.message_id)
    else:
        for msg_id in record["messages"]:
            copied = await context.bot.copy_message(chat_id, ADMIN_ID, msg_id)
            sent_ids.append(copied.message_id)

    if data.get("promo_text"):
        promo = await context.bot.send_message(chat_id, data["promo_text"])
        sent_ids.append(promo.message_id)

    button_msg = await context.bot.send_message(
        chat_id,
        data.get("button_caption", "🔘 Tap below to continue"),
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton(data["button_text"], url=data["button_url"] or "https://example.com")]]
        )
    )
    sent_ids.append(button_msg.message_id)

    delete_note = await context.bot.send_message(chat_id, "_This will be auto-deleted after 30 min_", parse_mode="Markdown")
    sent_ids.append(delete_note.message_id)

    threading.Thread(target=lambda: asyncio.run(schedule_deletion(context, chat_id, sent_ids))).start()
    await query.answer()
    await query.message.delete()


@admin_only
async def setautodeletetime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("❌ Usage: /setautodeletetime <seconds>")
        return

    seconds = int(args[0])
    if seconds < 30 or seconds > 86400:
        await update.message.reply_text("⚠️ Please provide a time between 30 and 86400 seconds (24 hours).")
        return

    data["auto_delete_time"] = seconds
    save_data()
    await update.message.reply_text(f"✅ Auto-delete time set to {seconds} seconds ({seconds // 60} minutes).")

@admin_only
async def showconfig(update: Update, context: ContextTypes.DEFAULT_TYPE):
    def escape_md(text):
    # Use raw strings to avoid invalid escape sequences
    replacements = [("*", "\\*"), ("_", "\\_"), ("[", "\\["), ("]", "\\]"), ("(", "\\("), (")", "\\)"), ("`", "\\`")]
    for old, new in replacements:
        text = text.replace(old, new)
    return text

        return text.replace("*", "\*").replace("_", "\_").replace("[", "\[").replace("`", "\`")

    channel_list = "
".join(
        f"- {escape_md(ch['chat_id'])}" for ch in data.get("required_channels", [])
    ) or "None"

    msg = f"""🔧 *Current Bot Configuration:*

📍 *Join Prompt:*
{escape_md(data.get("join_text", "N/A"))}

🔘 *Button:*
• Text: {escape_md(data.get("button_text", "N/A"))}
• URL: {escape_md(data.get("button_url", "N/A"))}
• Caption: {escape_md(data.get("button_caption", "N/A"))}

🕒 *Auto-delete time:* {data.get("auto_delete_time", 1800)} seconds ({data.get("auto_delete_time", 1800)//60} minutes)

📢 *Required Channels:*
{channel_list}
"""
    await update.message.reply_text(msg, parse_mode="Markdown")
        f"- {ch['chat_id']}" for ch in data.get("required_channels", [])
    ) or "None"

    msg = f"""🔧 *Current Bot Configuration:*

📍 *Join Prompt:*
{data.get("join_text", "N/A")}

🔘 *Button:*
• Text: {data.get("button_text", "N/A")}
• URL: {data.get("button_url", "N/A")}
• Caption: {data.get("button_caption", "N/A")}

🕒 *Auto-delete time:* {data.get("auto_delete_time", 1800)} seconds ({data.get("auto_delete_time", 1800)//60} minutes)

📢 *Required Channels:*
{channel_list}
"""
    await update.message.reply_text(msg, parse_mode="Markdown")


# --- Fallback for unknown commands ---
async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❓ Unknown command. Use /allcommands to see available commands.")

# --- Main ---
if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("setjointitle", setjointitle))
    app.add_handler(CommandHandler("resetjointitle", resetjointitle))
    app.add_handler(CommandHandler("batch", batch))
    app.add_handler(CommandHandler("batchoff", batchoff))
    app.add_handler(CommandHandler("generatebatch", generatebatch))
    app.add_handler(CommandHandler("setchannels", setchannels))
    app.add_handler(CommandHandler("cancelsetchannels", cancelsetchannels))
    app.add_handler(CommandHandler("clearsetchannels", clearsetchannels))
    app.add_handler(CommandHandler("setbutton", setbutton))
    app.add_handler(CommandHandler("cancelsetbutton", cancelsetbutton))
    app.add_handler(CommandHandler("promotext", promotext))
    app.add_handler(CommandHandler("listlinks", listlinks))
    app.add_handler(CommandHandler("deletelink", deletelink))
    app.add_handler(CommandHandler("deletealllinks", deletealllinks))
    app.add_handler(CommandHandler("allcommands", allcommands))
    app.add_handler(CommandHandler("setautodeletetime", setautodeletetime))
    app.add_handler(CommandHandler("showconfig", showconfig))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(tryagain_callback, pattern=r"^tryagain|"))
    app.add_handler(MessageHandler(filters.ALL, handle_input))

    app.add_handler(MessageHandler(filters.COMMAND, fallback))
    app.run_polling(drop_pending_updates=True)
