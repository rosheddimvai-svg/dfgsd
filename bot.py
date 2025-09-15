# This bot is designed for a public audience to sell Master/Visa cards.
# It uses webhooks for deployment on a platform like Render.
# Ensure you have the required libraries installed:
# pip install python-telegram-bot flask

import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler
)
from flask import Flask, request, jsonify

# --- Environment Variables (Your provided details) ---
BOT_TOKEN = "7845699149:AAEEKpzHFt5gd6LbApfXSsE8de64f8IaGx0"
ADMIN_USER_ID = int("7574558427")  # Admin's Telegram User ID
CARD_REVIEW_CHANNEL_ID = "-1003036699455"
APPROVED_CARDS_CHANNEL_ID = "-1002944346537"
ADMIN_BROADCAST_CHANNEL_ID = "-1003018121134"

# --- In-memory state for each user ---
user_states = {}

app = Flask(__name__)
application = Application.builder().token(BOT_TOKEN).build()

# --- Main menu with InlineKeyboard buttons ---
main_menu_keyboard = [
    [
        InlineKeyboardButton("💳 Card Sell", callback_data="card_sell"),
        InlineKeyboardButton("💰 Wallet Setup", callback_data="wallet_setup")
    ],
    [
        InlineKeyboardButton("📜 Rules", callback_data="rules"),
        InlineKeyboardButton("👨‍💻 Contact Admin", callback_data="contact_admin")
    ]
]

# --- Bot Command Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends the main menu when the /start command is issued."""
    await update.message.reply_text(
        "Welcome! I am a bot for buying and selling Master/Visa cards. Please choose an option:",
        reply_markup=InlineKeyboardMarkup(main_menu_keyboard)
    )

async def handle_button_press(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles callback queries from the main menu buttons."""
    query = update.callback_query
    await query.answer()

    if query.data == "card_sell":
        user_states[query.from_user.id] = "waiting_for_card"
        await query.edit_message_text(
            "Please send me your card details (text or photo). After sending, your card will be reviewed. Type 'cancel' to return."
        )
    elif query.data == "wallet_setup":
        await query.edit_message_text("Send your wallet address here. This is where you will receive your payments.")
    elif query.data == "rules":
        await query.edit_message_text("Here are the rules for selling cards:\n1. All cards must be valid.\n2. We are not responsible for invalid cards.\n3. The amount will be transferred to your provided wallet address after verification.")
    elif query.data == "contact_admin":
        await query.edit_message_text("To contact an admin, simply type your message and send it. It will be forwarded.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming messages based on user's current state."""
    user_id = update.effective_user.id
    user_state = user_states.get(user_id)

    if user_state == "waiting_for_card":
        message = update.message
        user_full_name = message.from_user.full_name
        user_username = f"@{message.from_user.username}" if message.from_user.username else "N/A"
        
        # Prepare the message to be sent to the admin channel
        caption_text = (
            f"**💳 New Card Submission**\n\n"
            f"**User:** {user_full_name} ({user_username})\n"
            f"**User ID:** `{user_id}`"
        )
        
        # Add the Confirm/Reject inline keyboard
        review_keyboard = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_{user_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}")
            ]]
        )
        
        if message.photo:
            photo = message.photo[-1]
            await context.bot.send_photo(
                chat_id=CARD_REVIEW_CHANNEL_ID,
                photo=photo.file_id,
                caption=caption_text,
                reply_markup=review_keyboard,
                parse_mode="Markdown"
            )
        elif message.text:
            if message.text.lower() == "cancel":
                user_states.pop(user_id, None)
                await message.reply_text("Card submission cancelled.", reply_markup=InlineKeyboardMarkup(main_menu_keyboard))
                return
            
            full_text = f"{caption_text}\n\n**Card Details:**\n{message.text}"
            await context.bot.send_message(
                chat_id=CARD_REVIEW_CHANNEL_ID,
                text=full_text,
                reply_markup=review_keyboard,
                parse_mode="Markdown"
            )
        else:
            await message.reply_text("Please send your card details as a photo or text.")
            return
            
        await message.reply_text("Your card details have been sent for review. We will notify you of the result.")
        user_states.pop(user_id, None)

    elif update.effective_user.id != ADMIN_USER_ID:
        # For non-admin users, forward their message to the admin
        message_text = f"**New message from user:** {update.effective_user.full_name}\n" \
                       f"**User ID:** `{update.effective_user.id}`\n" \
                       f"**Message:** {update.message.text}"
        
        await context.bot.send_message(
            chat_id=ADMIN_BROADCAST_CHANNEL_ID, # Use this channel to notify admin
            text=message_text,
            parse_mode="Markdown"
        )
        await update.message.reply_text("Your message has been sent to the admin.")

# --- Admin Callback Handler ---
async def handle_admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles admin's Confirm/Reject button presses."""
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_USER_ID:
        await query.answer("You are not authorized to perform this action.")
        return

    action, user_id = query.data.split('_')
    user_id = int(user_id)
    
    original_message_text = query.message.caption or query.message.text
    
    if action == "confirm":
        # Forward the card to the Approved channel
        try:
            await context.bot.forward_message(
                chat_id=APPROVED_CARDS_CHANNEL_ID,
                from_chat_id=query.message.chat_id,
                message_id=query.message.message_id
            )
            # Notify the original user
            await context.bot.send_message(
                chat_id=user_id,
                text="✅ Good news! Your card has been successfully approved. We will proceed with the payment."
            )
            await query.edit_message_text(f"{original_message_text}\n\n**Status: ✅ APPROVED**")
        except Exception as e:
            await query.edit_message_text(f"An error occurred: {e}")
            
    elif action == "reject":
        # Notify the original user of rejection
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Your card has been rejected. Please check the details and try again."
        )
        await query.edit_message_text(f"{original_message_text}\n\n**Status: ❌ REJECTED**")

# --- Broadcast Command for Admins ---
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Allows the admin to broadcast a message to a channel."""
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("You are not authorized to use this command.")
        return
    
    message_text = " ".join(context.args)
    if not message_text:
        await update.message.reply_text("Please provide a message to broadcast. E.g., /broadcast Hello everyone!")
        return

    # Send the broadcast message to the designated channel
    await context.bot.send_message(
        chat_id=ADMIN_BROADCAST_CHANNEL_ID,
        text=message_text,
    )
    await update.message.reply_text("Broadcast message sent successfully.")

# --- Application Setup ---
application.add_handler(CommandHandler("start", start_command))
application.add_handler(CommandHandler("broadcast", broadcast_command))
application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, handle_message))
application.add_handler(CallbackQueryHandler(handle_button_press, pattern="^card_sell|wallet_setup|rules|contact_admin$"))
application.add_handler(CallbackQueryHandler(handle_admin_action, pattern="^confirm_|^reject_"))

# --- Flask Webhook Configuration ---
@app.route("/", methods=["POST"])
def webhook_handler():
    """Handles incoming webhook requests from Telegram."""
    if request.method == "POST":
        update = Update.de_json(request.json, application.bot)
        application.process_update(update)
    return "ok"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)