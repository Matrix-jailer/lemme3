import asyncio
import logging
import json
import os
import aiofiles
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Replace with your bot token
BOT_TOKEN = "992401756:AAGouNmAdufry38HC0E6zz6Q7rWA0z642Nw"

# API endpoint for credit card checking
API_ENDPOINT = "https://lamme2.onrender.com/ccngate/"

# File to store user data
USERS_DATA_FILE = "users_data.json"

# Admin user IDs (replace with actual admin user IDs)
ADMIN_IDS = [7451622773]  # Add your admin user IDs here

# Global variable to store users data
users_data = {}

async def load_users():
    """Load users data from file."""
    global users_data
    try:
        async with aiofiles.open(USERS_DATA_FILE, 'r') as f:
            content = await f.read()
            users_data = json.loads(content)
    except FileNotFoundError:
        users_data = {}
        await save_users()
    except json.JSONDecodeError:
        users_data = {}
        await save_users()

async def save_users():
    """Save users data to file."""
    async with aiofiles.open(USERS_DATA_FILE, 'w') as f:
        await f.write(json.dumps(users_data, indent=2))

def get_user_data(user_id):
    """Get user data, create if doesn't exist."""
    user_id = str(user_id)
    if user_id not in users_data:
        users_data[user_id] = {
            "credits": 0,
            "premium": False,
            "banned": False,
            "total_checks": 0
        }
    return users_data[user_id]

def is_admin(user_id):
    """Check if user is admin."""
    return user_id in ADMIN_IDS

def is_user_banned(user_id):
    """Check if user is banned."""
    user_data = get_user_data(user_id)
    return user_data.get("banned", False)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    
    if is_user_banned(user_id):
        await update.message.reply_text("❌ You are banned from using this bot.")
        return
    
    keyboard = [
        [InlineKeyboardButton("💳 Check CC", callback_data="check_cc")],
        [InlineKeyboardButton("📊 My Stats", callback_data="stats")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")]
    ]
    
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"""🤖 **Welcome to Apex Checker Bot!**

👤 User: {update.effective_user.first_name}
💰 Credits: {user_data['credits']}
⭐ Premium: {'Yes' if user_data['premium'] else 'No'}
📈 Total Checks: {user_data['total_checks']}

Use the buttons below to navigate:"""
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    await save_users()

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send help message."""
    help_text = """🔧 **Apex Checker Bot Commands:**

**User Commands:**
• `.ccn <cc|mm|yyyy|cvv>` - Check single credit card
• `.ccnm` - Check multiple cards (reply to file)
• `/start` - Show main menu
• `/stats` - Show your statistics

**Admin Commands:**
• `/addcredits <user_id> <amount>` - Add credits to user
• `/removecredits <user_id> <amount>` - Remove credits from user
• `/premium <user_id>` - Toggle premium status
• `/ban <user_id>` - Ban/unban user
• `/broadcast <message>` - Send message to all users
• `/stats_all` - Show bot statistics

**Format Examples:**
• `.ccn 4400667077773319|11|2028|823`
• Upload a .txt file with cards and reply with `.ccnm`

💡 **Tips:**
• Premium users get unlimited checks
• Free users get limited daily credits
• Contact admin for premium access"""
    
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback queries from inline keyboards."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if is_user_banned(user_id):
        await query.edit_message_text("❌ You are banned from using this bot.")
        return
    
    if query.data == "check_cc":
        await query.edit_message_text(
            "💳 **Credit Card Checker**\n\n"
            "Send me a credit card in this format:\n"
            "`.ccn 4400667077773319|11|2028|823`\n\n"
            "Or upload a .txt file with multiple cards and reply with `.ccnm`",
            parse_mode=ParseMode.MARKDOWN
        )
    elif query.data == "stats":
        user_data = get_user_data(user_id)
        stats_text = f"""📊 **Your Statistics**

👤 User ID: {user_id}
💰 Credits: {user_data['credits']}
⭐ Premium: {'Yes' if user_data['premium'] else 'No'}
📈 Total Checks: {user_data['total_checks']}
🚫 Banned: {'Yes' if user_data['banned'] else 'No'}"""
        await query.edit_message_text(stats_text, parse_mode=ParseMode.MARKDOWN)
    elif query.data == "help":
        await help_command(update, context)
    elif query.data == "admin" and is_admin(user_id):
        await show_admin_panel(query)

async def show_admin_panel(query):
    """Show admin panel."""
    total_users = len(users_data)
    premium_users = sum(1 for user in users_data.values() if user.get('premium', False))
    banned_users = sum(1 for user in users_data.values() if user.get('banned', False))
    total_checks = sum(user.get('total_checks', 0) for user in users_data.values())
    
    admin_text = f"""👑 **Admin Panel**

📊 **Bot Statistics:**
• Total Users: {total_users}
• Premium Users: {premium_users}
• Banned Users: {banned_users}
• Total Checks: {total_checks}

**Available Commands:**
• `/addcredits <user_id> <amount>`
• `/removecredits <user_id> <amount>`
• `/premium <user_id>`
• `/ban <user_id>`
• `/broadcast <message>`
• `/stats_all`"""
    
    await query.edit_message_text(admin_text, parse_mode=ParseMode.MARKDOWN)

async def check_single_cc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle single credit card check."""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    
    if is_user_banned(user_id):
        await update.message.reply_text("❌ You are banned from using this bot.")
        return
    
    # Check if user has credits or is premium
    if not user_data['premium'] and user_data['credits'] <= 0:
        await update.message.reply_text(
            "❌ **Insufficient Credits!**\n\n"
            "You need credits to check cards. Contact admin for premium access.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Extract CC data from message
    message_text = update.message.text
    if not message_text.startswith('.ccn '):
        await update.message.reply_text(
            "❌ **Invalid Format!**\n\n"
            "Use: `.ccn 4400667077773319|11|2028|823`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    cc_data = message_text[5:].strip()  # Remove '.ccn ' prefix
    
    # Validate CC format
    if '|' not in cc_data or len(cc_data.split('|')) != 4:
        await update.message.reply_text(
            "❌ **Invalid CC Format!**\n\n"
            "Use: `4400667077773319|11|2028|823`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Send processing message
    processing_msg = await update.message.reply_text(
        "🔄 **Processing your request...**\n\n"
        f"💳 Card: `{cc_data}`\n"
        "⏳ Please wait...",
        parse_mode=ParseMode.MARKDOWN
    )
    
    try:
        # Make API request
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_ENDPOINT}{cc_data}") as response:
                if response.status == 200:
                    result = await response.json()
                    
                    # Deduct credit if not premium
                    if not user_data['premium']:
                        user_data['credits'] -= 1
                    
                    user_data['total_checks'] += 1
                    await save_users()
                    
                    # Format result
                    if result.get('results') and len(result['results']) > 0:
                        card_result = result['results'][0]
                        status = card_result.get('status', 'unknown')
                        message = card_result.get('message', 'No message')
                        
                        if status == 'success':
                            status_emoji = "✅"
                            status_text = "**LIVE**"
                        elif status == 'success_3ds':
                            status_emoji = "⚠️"
                            status_text = "**LIVE (3DS)**"
                        elif status == 'invalid_cvv':
                            status_emoji = "🔶"
                            status_text = "**CCN (Invalid CVV)**"
                        else:
                            status_emoji = "❌"
                            status_text = "**DEAD**"
                        
                        result_text = f"""{status_emoji} **Card Check Result**

💳 **Card:** `{cc_data}`
📊 **Status:** {status_text}
💬 **Message:** {message}
👤 **Checked by:** {update.effective_user.first_name}
💰 **Credits Left:** {user_data['credits']}

🤖 **Apex Checker Bot**"""
                    else:
                        result_text = f"""❌ **Check Failed**

💳 **Card:** `{cc_data}`
📊 **Status:** Unknown Error
💬 **Message:** No valid response from API

🤖 **Apex Checker Bot**"""
                else:
                    result_text = f"""❌ **API Error**

💳 **Card:** `{cc_data}`
📊 **Status:** API Error ({response.status})
💬 **Message:** Failed to connect to checking service

🤖 **Apex Checker Bot**"""
    
    except Exception as e:
        result_text = f"""❌ **Error**

💳 **Card:** `{cc_data}`
📊 **Status:** System Error
💬 **Message:** {str(e)}

🤖 **Apex Checker Bot**"""
    
    await processing_msg.edit_text(result_text, parse_mode=ParseMode.MARKDOWN)

async def check_multiple_cc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle multiple credit card check from file."""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    
    if is_user_banned(user_id):
        await update.message.reply_text("❌ You are banned from using this bot.")
        return
    
    # Check if message is a reply to a document
    if not update.message.reply_to_message or not update.message.reply_to_message.document:
        await update.message.reply_text(
            "❌ **No File Found!**\n\n"
            "Please reply to a .txt file containing credit cards with `.ccnm`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    document = update.message.reply_to_message.document
    
    # Check file type
    if not document.file_name.endswith('.txt'):
        await update.message.reply_text(
            "❌ **Invalid File Type!**\n\n"
            "Please upload a .txt file containing credit cards.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    try:
        # Download and read file
        file = await context.bot.get_file(document.file_id)
        file_content = await file.download_as_bytearray()
        cc_list = file_content.decode('utf-8').strip().split('\n')
        
        # Filter valid CCs
        valid_ccs = []
        for cc in cc_list:
            cc = cc.strip()
            if cc and '|' in cc and len(cc.split('|')) == 4:
                valid_ccs.append(cc)
        
        if not valid_ccs:
            await update.message.reply_text(
                "❌ **No Valid Cards Found!**\n\n"
                "Make sure your file contains cards in format:\n"
                "`4400667077773319|11|2028|823`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Check credits
        required_credits = len(valid_ccs)
        if not user_data['premium'] and user_data['credits'] < required_credits:
            await update.message.reply_text(
                f"❌ **Insufficient Credits!**\n\n"
                f"Required: {required_credits}\n"
                f"Available: {user_data['credits']}\n\n"
                "Contact admin for more credits or premium access.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Limit for non-premium users
        if not user_data['premium'] and len(valid_ccs) > 10:
            await update.message.reply_text(
                "❌ **Limit Exceeded!**\n\n"
                "Free users can check maximum 10 cards at once.\n"
                "Upgrade to premium for unlimited checks.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Send processing message
        processing_msg = await update.message.reply_text(
            f"🔄 **Processing {len(valid_ccs)} cards...**\n\n"
            "⏳ This may take a while. Please wait...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Process cards
        cc_data_string = ','.join(valid_ccs)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{API_ENDPOINT}{cc_data_string}") as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        # Deduct credits if not premium
                        if not user_data['premium']:
                            user_data['credits'] -= len(valid_ccs)
                        
                        user_data['total_checks'] += len(valid_ccs)
                        await save_users()
                        
                        # Format results
                        if result.get('results'):
                            live_cards = []
                            dead_cards = []
                            ccn_cards = []
                            
                            for card_result in result['results']:
                                cc = card_result.get('cc', 'Unknown')
                                status = card_result.get('status', 'unknown')
                                message = card_result.get('message', 'No message')
                                
                                if status in ['success', 'success_3ds']:
                                    live_cards.append(f"✅ `{cc}` - {message}")
                                elif status == 'invalid_cvv':
                                    ccn_cards.append(f"🔶 `{cc}` - {message}")
                                else:
                                    dead_cards.append(f"❌ `{cc}` - {message}")
                            
                            result_text = f"""📊 **Bulk Check Results**

📈 **Summary:**
• Total Checked: {len(valid_ccs)}
• Live: {len(live_cards)}
• CCN: {len(ccn_cards)}
• Dead: {len(dead_cards)}

"""
                            
                            if live_cards:
                                result_text += "\n✅ **LIVE CARDS:**\n" + "\n".join(live_cards[:5])
                                if len(live_cards) > 5:
                                    result_text += f"\n... and {len(live_cards) - 5} more"
                            
                            if ccn_cards:
                                result_text += "\n\n🔶 **CCN CARDS:**\n" + "\n".join(ccn_cards[:3])
                                if len(ccn_cards) > 3:
                                    result_text += f"\n... and {len(ccn_cards) - 3} more"
                            
                            result_text += f"\n\n👤 **Checked by:** {update.effective_user.first_name}\n💰 **Credits Left:** {user_data['credits']}\n\n🤖 **Apex Checker Bot**"
                        else:
                            result_text = f"""❌ **Bulk Check Failed**

📊 **Status:** No valid response from API
💬 **Message:** Failed to process cards

🤖 **Apex Checker Bot**"""
                    else:
                        result_text = f"""❌ **API Error**

📊 **Status:** API Error ({response.status})
💬 **Message:** Failed to connect to checking service

🤖 **Apex Checker Bot**"""
        
        except Exception as e:
            result_text = f"""❌ **Error**

📊 **Status:** System Error
💬 **Message:** {str(e)}

🤖 **Apex Checker Bot**"""
        
        await processing_msg.edit_text(result_text, parse_mode=ParseMode.MARKDOWN)
    
    except Exception as e:
        await update.message.reply_text(
            f"❌ **File Processing Error**\n\n"
            f"Error: {str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )

# Admin Commands
async def add_credits_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add credits to a user (Admin only)."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ You don't have permission to use this command.")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text(
            "❌ **Invalid Usage!**\n\n"
            "Use: `/addcredits <user_id> <amount>`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    try:
        target_user_id = str(context.args[0])
        amount = int(context.args[1])
        
        user_data = get_user_data(target_user_id)
        user_data['credits'] += amount
        await save_users()
        
        await update.message.reply_text(
            f"✅ **Credits Added!**\n\n"
            f"👤 User ID: `{target_user_id}`\n"
            f"💰 Added: {amount} credits\n"
            f"💳 New Balance: {user_data['credits']} credits",
            parse_mode=ParseMode.MARKDOWN
        )
    
    except ValueError:
        await update.message.reply_text(
            "❌ **Invalid Amount!**\n\n"
            "Amount must be a number.",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def remove_credits_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove credits from a user (Admin only)."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ You don't have permission to use this command.")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text(
            "❌ **Invalid Usage!**\n\n"
            "Use: `/removecredits <user_id> <amount>`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    try:
        target_user_id = str(context.args[0])
        amount = int(context.args[1])
        
        user_data = get_user_data(target_user_id)
        user_data['credits'] = max(0, user_data['credits'] - amount)
        await save_users()
        
        await update.message.reply_text(
            f"✅ **Credits Removed!**\n\n"
            f"👤 User ID: `{target_user_id}`\n"
            f"💰 Removed: {amount} credits\n"
            f"💳 New Balance: {user_data['credits']} credits",
            parse_mode=ParseMode.MARKDOWN
        )
    
    except ValueError:
        await update.message.reply_text(
            "❌ **Invalid Amount!**\n\n"
            "Amount must be a number.",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle premium status for a user (Admin only)."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ You don't have permission to use this command.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text(
            "❌ **Invalid Usage!**\n\n"
            "Use: `/premium <user_id>`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    try:
        target_user_id = str(context.args[0])
        user_data = get_user_data(target_user_id)
        user_data['premium'] = not user_data['premium']
        await save_users()
        
        status = "Enabled" if user_data['premium'] else "Disabled"
        await update.message.reply_text(
            f"✅ **Premium Status Updated!**\n\n"
            f"👤 User ID: `{target_user_id}`\n"
            f"⭐ Premium: {status}",
            parse_mode=ParseMode.MARKDOWN
        )
    
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle ban status for a user (Admin only)."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ You don't have permission to use this command.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text(
            "❌ **Invalid Usage!**\n\n"
            "Use: `/ban <user_id>`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    try:
        target_user_id = str(context.args[0])
        user_data = get_user_data(target_user_id)
        user_data['banned'] = not user_data['banned']
        await save_users()
        
        status = "Banned" if user_data['banned'] else "Unbanned"
        await update.message.reply_text(
            f"✅ **Ban Status Updated!**\n\n"
            f"👤 User ID: `{target_user_id}`\n"
            f"🚫 Status: {status}",
            parse_mode=ParseMode.MARKDOWN
        )
    
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Broadcast message to all users (Admin only)."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ You don't have permission to use this command.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ **Invalid Usage!**\n\n"
            "Use: `/broadcast <message>`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    message = ' '.join(context.args)
    broadcast_text = f"📢 **Broadcast Message**\n\n{message}\n\n🤖 **Apex Checker Bot**"
    
    sent_count = 0
    failed_count = 0
    
    for user_id in users_data.keys():
        try:
            await context.bot.send_message(
                chat_id=int(user_id),
                text=broadcast_text,
                parse_mode=ParseMode.MARKDOWN
            )
            sent_count += 1
        except Exception:
            failed_count += 1
    
    await update.message.reply_text(
        f"✅ **Broadcast Complete!**\n\n"
        f"📤 Sent: {sent_count}\n"
        f"❌ Failed: {failed_count}",
        parse_mode=ParseMode.MARKDOWN
    )

async def stats_all_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show bot statistics (Admin only)."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ You don't have permission to use this command.")
        return
    
    total_users = len(users_data)
    premium_users = sum(1 for user in users_data.values() if user.get('premium', False))
    banned_users = sum(1 for user in users_data.values() if user.get('banned', False))
    total_checks = sum(user.get('total_checks', 0) for user in users_data.values())
    total_credits = sum(user.get('credits', 0) for user in users_data.values())
    
    stats_text = f"""📊 **Bot Statistics**

👥 **Users:**
• Total Users: {total_users}
• Premium Users: {premium_users}
• Banned Users: {banned_users}
• Active Users: {total_users - banned_users}

💳 **Activity:**
• Total Checks: {total_checks}
• Total Credits: {total_credits}

🤖 **Apex Checker Bot**"""
    
    await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages."""
    message_text = update.message.text
    
    if message_text.startswith('.ccn '):
        await check_single_cc(update, context)
    elif message_text == '.ccnm':
        await check_multiple_cc(update, context)
    else:
        # Show help for unknown commands
        await update.message.reply_text(
            "❓ **Unknown Command**\n\n"
            "Use `/start` to see available options or `/help` for command list.",
            parse_mode=ParseMode.MARKDOWN
        )

# Initialize function
async def initialize():
    """Initialize the bot data."""
    await load_users()

def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("addcredits", add_credits_command))
    application.add_handler(CommandHandler("removecredits", remove_credits_command))
    application.add_handler(CommandHandler("premium", premium_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("stats_all", stats_all_command))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Initialize bot data
    asyncio.create_task(initialize())

    # Check if we're already in an event loop
    try:
        loop = asyncio.get_running_loop()
        # If we're already in a loop, schedule the polling as a task
        logger.info("Event loop already running, scheduling bot as task")
        task = loop.create_task(application.run_polling())
        return task
    except RuntimeError:
        # No event loop running, we can use asyncio.run()
        logger.info("No event loop running, starting new one")
        asyncio.run(application.run_polling())

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot error: {e}")
