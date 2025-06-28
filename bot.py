import telebot
from telebot import types
import json
import os
import time
from datetime import datetime
from web3 import Web3
from eth_account import Account
from config import BOT_TOKEN, UserState, TOKENS_FILE, USERS_FILE, POOLS_FILE, ERC20_ABI
from storage import (
    get_user_wallet, save_user_wallet, save_token_to_db, save_pool_to_db
)
from wallet import (
    create_wallet, get_web3, sign_and_send_transaction,
    wait_for_transaction_receipt, get_explorer_url
)
from contracts import deploy_token
from pool import create_uniswap_pool, execute_pool_creation
from uncx_locker import LiquidityLocker, Position, LockedPosition
from contract_renouncement import renounce_contract_ownership, get_token_info

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN)

# Store callback data
callback_data_store = {}

# User state management
user_states = {}
user_data = {}

# Bot handlers
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    user_states[user_id] = UserState.MAIN_MENU
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton('🔐 Setup Wallet')
    btn2 = types.KeyboardButton('🪙 Create Token')
    btn3 = types.KeyboardButton('💧 Create Pool')
    btn4 = types.KeyboardButton('📊 My Tokens')
    btn5 = types.KeyboardButton('🔒 Manage Liquidity')
    btn6 = types.KeyboardButton('⚓ Renounce Contract')
    btn7 = types.KeyboardButton('ℹ️ Help')
    btn8 = types.KeyboardButton('⚙️ Settings')

    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7, btn8)


    welcome_text = f"""
🚀 Welcome to **Token Deployer Bot**, {username}!

This bot helps you:
• Deploy custom ERC20 tokens with advanced features
• Create Uniswap V3 pools
• Add liquidity to your tokens
• Manage your token portfolio
• Renounce contract ownership

**Supported Networks:**
• Polygon (MATIC)
• Ethereum (ETH)

**Token Features Available:**
• Burnable Tokens
• Mintable Supply
• Pausable Transfers
• Access Control Roles
• Flash Minting
• Custom Buy/Sell Taxes

Get started by setting up your wallet! 👇
    """

    bot.send_message(message.chat.id,
                     welcome_text,
                     reply_markup=markup,
                     parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == '🔐 Setup Wallet')
def setup_wallet(message):
    user_id = message.from_user.id
    user_states[user_id] = UserState.WALLET_SETUP

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton('🆕 Create New Wallet',
                                      callback_data='create_wallet')
    btn2 = types.InlineKeyboardButton('📥 Import Existing',
                                      callback_data='import_wallet')
    markup.add(btn1, btn2)

    bot.send_message(message.chat.id,
                     "🔐 **Wallet Setup**\n\nChoose an option:",
                     reply_markup=markup,
                     parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == 'create_wallet')
def create_new_wallet(call):
    user_id = call.from_user.id
    username = call.from_user.username or call.from_user.first_name

    wallet_data = create_wallet()
    save_user_wallet(user_id, username, wallet_data)

    bot.edit_message_text(
        f"✅ **Wallet Created Successfully!**\n\n"
        f"🏦 **Address:** `{wallet_data['address']}`\n\n"
        f"🔑 **Private Key:** `{wallet_data['private_key']}`\n\n"
        f"⚠️ **IMPORTANT:** Save your private key securely! This is the only time it will be shown.\n\n"
        f"💰 **Next Steps:**\n"
        f"1. Send MATIC/ETH to your wallet for gas fees\n"
        f"2. Use /start to return to main menu",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == 'import_wallet')
def import_wallet_prompt(call):
    user_id = call.from_user.id
    user_states[user_id] = UserState.WALLET_SETUP

    bot.edit_message_text(
        "🔑 **Import Wallet**\n\n"
        "Send your private key (it will be deleted after processing):",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == '🪙 Create Token')
def create_token_start(message):
    user_id = message.from_user.id

    # Check if user has wallet
    wallet = get_user_wallet(user_id)
    if not wallet:
        bot.send_message(
            message.chat.id,
            "❌ **No wallet found!**\n\nPlease setup your wallet first using the '🔐 Setup Wallet' button.",
            parse_mode='Markdown')
        return

    user_states[user_id] = UserState.TOKEN_CREATION
    user_data[user_id] = {'step': 'name'}

    bot.send_message(message.chat.id, "🪙 **Token Creation Wizard**\n\n"
                     "Let's create your custom ERC20 token!\n\n"
                     "**Step 1/7:** Enter your token name:\n"
                     "(e.g., 'My Awesome Token')",
                     parse_mode='Markdown')

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == UserState.TOKEN_CREATION)
def handle_token_creation(message):
    user_id = message.from_user.id

    if user_id not in user_data:
        user_data[user_id] = {}

    step = user_data[user_id].get('step', 'name')

    if step == 'name':
        user_data[user_id]['token_name'] = message.text
        user_data[user_id]['step'] = 'symbol'
        bot.send_message(message.chat.id,
                         f"✅ Token name: **{message.text}**\n\n"
                         f"**Step 2/7:** Enter your token symbol:\n"
                         f"(e.g., 'MAT' - usually 3-5 characters)",
                         parse_mode='Markdown')

    elif step == 'symbol':
        user_data[user_id]['token_symbol'] = message.text.upper()
        user_data[user_id]['step'] = 'supply'
        
        # Add suggested supply buttons
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn1 = types.InlineKeyboardButton('100,000', callback_data='supply_100000')
        btn2 = types.InlineKeyboardButton('1,000,000', callback_data='supply_1000000')
        btn3 = types.InlineKeyboardButton('10,000,000', callback_data='supply_10000000')
        btn4 = types.InlineKeyboardButton('100,000,000', callback_data='supply_100000000')
        btn5 = types.InlineKeyboardButton('Custom Amount', callback_data='supply_custom')
        markup.add(btn1, btn2, btn3, btn4, btn5)
        
        bot.send_message(message.chat.id,
                         f"✅ Token symbol: **{message.text.upper()}**\n\n"
                         f"**Step 3/7:** Select total supply or enter a custom amount:",
                         reply_markup=markup,
                         parse_mode='Markdown')

    elif step == 'supply':
        try:
            supply = int(message.text)
            user_data[user_id]['total_supply'] = supply
            user_data[user_id]['step'] = 'decimals'
            
            # Add suggested decimals buttons
            markup = types.InlineKeyboardMarkup(row_width=3)
            btn1 = types.InlineKeyboardButton('6', callback_data='decimals_6')
            btn2 = types.InlineKeyboardButton('9', callback_data='decimals_9')
            btn3 = types.InlineKeyboardButton('18', callback_data='decimals_18')
            btn4 = types.InlineKeyboardButton('Custom', callback_data='decimals_custom')
            markup.add(btn1, btn2, btn3, btn4)
            
            bot.send_message(message.chat.id,
                             f"✅ Total supply: **{supply:,}**\n\n"
                             f"**Step 4/7:** Select decimals or enter a custom value:",
                             reply_markup=markup,
                             parse_mode='Markdown')
        except ValueError:
            bot.send_message(
                message.chat.id,
                "❌ Please enter a valid number for total supply.")

    elif step == 'decimals':
        try:
            decimals = int(message.text)
            if decimals < 0 or decimals > 18:
                bot.send_message(message.chat.id,
                                 "❌ Decimals must be between 0 and 18.")
                return

            user_data[user_id]['decimals'] = decimals
            user_states[user_id] = UserState.SELECTING_FEATURES

            # Show feature selection
            markup = types.InlineKeyboardMarkup(row_width=1)
            btn1 = types.InlineKeyboardButton('🔥 Burnable',
                                              callback_data='toggle_feature_0')
            btn2 = types.InlineKeyboardButton('➕ Mintable',
                                              callback_data='toggle_feature_1')
            btn3 = types.InlineKeyboardButton('⏸️ Pausable',
                                              callback_data='toggle_feature_2')
            btn4 = types.InlineKeyboardButton('🔒 Access Control',
                                              callback_data='toggle_feature_3')
            btn5 = types.InlineKeyboardButton('⚡ Flash Minting',
                                              callback_data='toggle_feature_4')
            btn6 = types.InlineKeyboardButton(
                '✅ Continue to Taxes', callback_data='continue_to_taxes')

            markup.add(btn1, btn2, btn3, btn4, btn5, btn6)

            user_data[user_id]['features'] = [
                False, False, False, False, False
            ]

            bot.send_message(
                message.chat.id, f"✅ Decimals: **{decimals}**\n\n"
                f"**Step 5/7:** Select token features (click to toggle):\n\n"
                f"🔥 Burnable: ❌\n"
                f"➕ Mintable: ❌\n"
                f"⏸️ Pausable: ❌\n"
                f"🔒 Access Control: ❌\n"
                f"⚡ Flash Minting: ❌\n\n"
                f"Select features, then click 'Continue to Taxes'",
                reply_markup=markup,
                parse_mode='Markdown')
        except ValueError:
            bot.send_message(message.chat.id,
                             "❌ Please enter a valid number for decimals.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('supply_'))
def handle_supply_selection(call):
    user_id = call.from_user.id
    supply_option = call.data.split('_')[1]
    
    if supply_option == 'custom':
        bot.send_message(
            call.message.chat.id,
            "Please enter your custom token supply amount:",
            parse_mode='Markdown')
    else:
        supply = int(supply_option)
        user_data[user_id]['total_supply'] = supply
        user_data[user_id]['step'] = 'decimals'
        
        # Add suggested decimals buttons
        markup = types.InlineKeyboardMarkup(row_width=3)
        btn1 = types.InlineKeyboardButton('6', callback_data='decimals_6')
        btn2 = types.InlineKeyboardButton('9', callback_data='decimals_9')
        btn3 = types.InlineKeyboardButton('18', callback_data='decimals_18')
        btn4 = types.InlineKeyboardButton('Custom', callback_data='decimals_custom')
        markup.add(btn1, btn2, btn3, btn4)
        
        bot.send_message(
            call.message.chat.id,
            f"✅ Total supply: **{supply:,}**\n\n"
            f"**Step 4/7:** Select decimals or enter a custom value:",
            reply_markup=markup,
            parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('decimals_'))
def handle_decimals_selection(call):
    user_id = call.from_user.id
    decimals_option = call.data.split('_')[1]
    
    if decimals_option == 'custom':
        bot.send_message(
            call.message.chat.id,
            "Please enter your custom decimals value (0-18):",
            parse_mode='Markdown')
    else:
        decimals = int(decimals_option)
        user_data[user_id]['decimals'] = decimals
        user_states[user_id] = UserState.SELECTING_FEATURES

        # Show feature selection
        markup = types.InlineKeyboardMarkup(row_width=1)
        btn1 = types.InlineKeyboardButton('🔥 Burnable',
                                          callback_data='toggle_feature_0')
        btn2 = types.InlineKeyboardButton('➕ Mintable',
                                          callback_data='toggle_feature_1')
        btn3 = types.InlineKeyboardButton('⏸️ Pausable',
                                          callback_data='toggle_feature_2')
        btn4 = types.InlineKeyboardButton('🔒 Access Control',
                                          callback_data='toggle_feature_3')
        btn5 = types.InlineKeyboardButton('⚡ Flash Minting',
                                          callback_data='toggle_feature_4')
        btn6 = types.InlineKeyboardButton(
            '✅ Continue to Taxes', callback_data='continue_to_taxes')

        markup.add(btn1, btn2, btn3, btn4, btn5, btn6)

        user_data[user_id]['features'] = [
            False, False, False, False, False
        ]

        bot.send_message(
            call.message.chat.id, f"✅ Decimals: **{decimals}**\n\n"
            f"**Step 5/7:** Select token features (click to toggle):\n\n"
            f"🔥 Burnable: ❌\n"
            f"➕ Mintable: ❌\n"
            f"⏸️ Pausable: ❌\n"
            f"🔒 Access Control: ❌\n"
            f"⚡ Flash Minting: ❌\n\n"
            f"Select features, then click 'Continue to Taxes'",
            reply_markup=markup,
            parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('toggle_feature_'))
def toggle_feature(call):
    user_id = call.from_user.id
    feature_index = int(call.data.split('_')[-1])

    if user_id not in user_data:
        return

    # Toggle feature
    user_data[user_id]['features'][feature_index] = not user_data[user_id]['features'][feature_index]
    features = user_data[user_id]['features']

    feature_names = [
        "🔥 Burnable", "➕ Mintable", "⏸️ Pausable", "🔒 Access Control", "⚡ Flash Minting"
    ]

    feature_text = ""
    for i, (name, enabled) in enumerate(zip(feature_names, features)):
        status = "✅" if enabled else "❌"
        feature_text += f"{name}: {status}\n"

    markup = types.InlineKeyboardMarkup(row_width=1)
    btn1 = types.InlineKeyboardButton('🔥 Burnable',
                                      callback_data='toggle_feature_0')
    btn2 = types.InlineKeyboardButton('➕ Mintable',
                                      callback_data='toggle_feature_1')
    btn3 = types.InlineKeyboardButton('⏸️ Pausable',
                                      callback_data='toggle_feature_2')
    btn4 = types.InlineKeyboardButton('🔒 Access Control',
                                      callback_data='toggle_feature_3')
    btn5 = types.InlineKeyboardButton('⚡ Flash Minting',
                                      callback_data='toggle_feature_4')
    btn6 = types.InlineKeyboardButton('✅ Continue to Taxes',
                                      callback_data='continue_to_taxes')

    markup.add(btn1, btn2, btn3, btn4, btn5, btn6)

    bot.edit_message_text(
        f"**Step 5/7:** Select token features (click to toggle):\n\n{feature_text}\n"
        f"Select up to 5 features, then click 'Continue to Taxes'",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == 'continue_to_taxes')
def continue_to_taxes(call):
    user_id = call.from_user.id
    user_states[user_id] = UserState.SETTING_TAXES
    user_data[user_id]['tax_step'] = 'buy'

    # Add suggested buy tax buttons
    markup = types.InlineKeyboardMarkup(row_width=3)
    btn1 = types.InlineKeyboardButton('0%', callback_data='buy_tax_0')
    btn2 = types.InlineKeyboardButton('3%', callback_data='buy_tax_3')
    btn3 = types.InlineKeyboardButton('5%', callback_data='buy_tax_5')
    btn4 = types.InlineKeyboardButton('10%', callback_data='buy_tax_10')
    btn5 = types.InlineKeyboardButton('15%', callback_data='buy_tax_15')
    btn6 = types.InlineKeyboardButton('Custom', callback_data='buy_tax_custom')
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6)

    bot.edit_message_text(
        "**Step 6/7:** Set Buy Tax\n\n"
        "Select a buy tax percentage or enter a custom value (0-25%):",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_tax_'))
def handle_buy_tax_selection(call):
    user_id = call.from_user.id
    tax_option = call.data.split('_')[2]
    
    if tax_option == 'custom':
        bot.send_message(
            call.message.chat.id,
            "Please enter your custom buy tax percentage (0-25):",
            parse_mode='Markdown')
    else:
        tax_value = int(tax_option)
        user_data[user_id]['buy_tax'] = tax_value * 100  # Convert to basis points
        user_data[user_id]['tax_step'] = 'sell'
        
        # Add suggested sell tax buttons
        markup = types.InlineKeyboardMarkup(row_width=3)
        btn1 = types.InlineKeyboardButton('0%', callback_data='sell_tax_0')
        btn2 = types.InlineKeyboardButton('3%', callback_data='sell_tax_3')
        btn3 = types.InlineKeyboardButton('5%', callback_data='sell_tax_5')
        btn4 = types.InlineKeyboardButton('10%', callback_data='sell_tax_10')
        btn5 = types.InlineKeyboardButton('15%', callback_data='sell_tax_15')
        btn6 = types.InlineKeyboardButton('Custom', callback_data='sell_tax_custom')
        markup.add(btn1, btn2, btn3, btn4, btn5, btn6)
        
        bot.send_message(
            call.message.chat.id,
            f"✅ Buy tax: **{tax_value}%**\n\n"
            f"**Step 7/7:** Set Sell Tax\n\n"
            f"Select a sell tax percentage or enter a custom value (0-25%):",
            reply_markup=markup,
            parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('sell_tax_'))
def handle_sell_tax_selection(call):
    user_id = call.from_user.id
    tax_option = call.data.split('_')[2]
    
    if tax_option == 'custom':
        bot.send_message(
            call.message.chat.id,
            "Please enter your custom sell tax percentage (0-25):",
            parse_mode='Markdown')
    else:
        tax_value = int(tax_option)
        user_data[user_id]['sell_tax'] = tax_value * 100  # Convert to basis points
        
        # Ask for tax wallet address
        markup = types.InlineKeyboardMarkup(row_width=1)
        btn1 = types.InlineKeyboardButton('Use my wallet address (default)', callback_data='tax_wallet_default')
        markup.add(btn1)
        
        bot.send_message(
            call.message.chat.id,
            "**Step 8/8:** Enter the wallet address where taxes should be sent.\n\n"
            "You can enter a custom address or use your wallet address (default).",
            reply_markup=markup,
            parse_mode='Markdown'
        )
        
        # Update user state
        user_states[user_id] = UserState.ENTERING_TAX_WALLET

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == UserState.SETTING_TAXES)
def handle_tax_setting(message):
    user_id = message.from_user.id

    if user_id not in user_data:
        return

    tax_step = user_data[user_id].get('tax_step', 'buy')

    try:
        tax_value = float(message.text)
        if tax_value < 0 or tax_value > 25:
            bot.send_message(message.chat.id,
                             "❌ Tax must be between 0 and 25%")
            return

        if tax_step == 'buy':
            user_data[user_id]['buy_tax'] = int(tax_value * 100)  # Convert to basis points
            user_data[user_id]['tax_step'] = 'sell'
            
            # Add suggested sell tax buttons
            markup = types.InlineKeyboardMarkup(row_width=3)
            btn1 = types.InlineKeyboardButton('0%', callback_data='sell_tax_0')
            btn2 = types.InlineKeyboardButton('3%', callback_data='sell_tax_3')
            btn3 = types.InlineKeyboardButton('5%', callback_data='sell_tax_5')
            btn4 = types.InlineKeyboardButton('10%', callback_data='sell_tax_10')
            btn5 = types.InlineKeyboardButton('15%', callback_data='sell_tax_15')
            btn6 = types.InlineKeyboardButton('Custom', callback_data='sell_tax_custom')
            markup.add(btn1, btn2, btn3, btn4, btn5, btn6)
            
            bot.send_message(message.chat.id,
                             f"✅ Buy tax: **{tax_value}%**\n\n"
                             f"**Step 7/8:** Set Sell Tax\n\n"
                             f"Select a sell tax percentage or enter a custom value (0-25%):",
                             reply_markup=markup,
                             parse_mode='Markdown')

        elif tax_step == 'sell':
            user_data[user_id]['sell_tax'] = int(tax_value * 100)  # Convert to basis points
            
            # Ask for tax wallet address
            markup = types.InlineKeyboardMarkup(row_width=1)
            btn1 = types.InlineKeyboardButton('Use my wallet address (default)', callback_data='tax_wallet_default')
            markup.add(btn1)
            
            bot.send_message(
                message.chat.id,
                "**Step 8/8:** Enter the wallet address where taxes should be sent.\n\n"
                "You can enter a custom address or use your wallet address (default).",
                reply_markup=markup,
                parse_mode='Markdown')
            
            # Update user state
            user_states[user_id] = UserState.ENTERING_TAX_WALLET

    except ValueError:
        bot.send_message(message.chat.id,
                         "❌ Please enter a valid number for tax percentage.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('deploy_'))
def deploy_token_network(call):
    user_id = call.from_user.id
    network = call.data.split('_')[1]

    bot.edit_message_text(
        f"🚀 Preparing Token Deployment on {network.title()}...\n\n"
        f"⏳ Calculating gas fees and preparing transaction...",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown')

    # Prepare token data
    features = user_data[user_id]['features']
    
    # Convert boolean array to OpenZeppelin feature names
    oz_features = []
    feature_mapping = [
        "Burnable", "Mintable", "Pausable", "Access Control", "Flash Minting"
    ]
    
    for i, enabled in enumerate(features):
        if enabled:
            oz_features.append(feature_mapping[i])
    
    token_data = {
        'name': user_data[user_id]['token_name'],
        'symbol': user_data[user_id]['token_symbol'],
        'total_supply': user_data[user_id]['total_supply'],
        'decimals': user_data[user_id]['decimals'],
        'buy_tax': user_data[user_id]['buy_tax'],
        'sell_tax': user_data[user_id]['sell_tax'],
        'features': oz_features,
        'tax_wallet': user_data[user_id].get('tax_wallet', '')  # Add tax wallet address
    }

    # Calculate deployment details but don't deploy yet
    try:
        web3 = get_web3(network)
        user_wallet = get_user_wallet(user_id)

        if not user_wallet:
            bot.edit_message_text(
                f"❌ No wallet found!\n\nPlease set up your wallet first.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown')
            return

        # Get token parameters
        token_name = token_data['name']
        token_symbol = token_data['symbol']
        total_supply = token_data['total_supply']
        decimals = token_data['decimals']
        buy_tax = token_data['buy_tax']
        sell_tax = token_data['sell_tax']

        # Calculate estimated gas for the transaction
        gas_price = web3.eth.gas_price
        gas_limit = 3000000  # Estimated gas limit for token deployment

        # Calculate the total transaction cost in ETH/MATIC
        transaction_cost_wei = gas_price * gas_limit
        transaction_cost_eth = web3.from_wei(transaction_cost_wei, 'ether')

        # Get current balance
        current_balance_wei = web3.eth.get_balance(user_wallet['address'])
        current_balance_eth = web3.from_wei(current_balance_wei, 'ether')

        # Check if user has enough balance
        if current_balance_wei < transaction_cost_wei:
            bot.edit_message_text(
                f"❌ Insufficient balance!\n\n"
                f"You need at least {transaction_cost_eth:.6f} {network.upper()} for gas fees.\n"
                f"Current balance: {current_balance_eth:.6f} {network.upper()}",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown')
            return

        # Show transaction details for approval
        feature_names = [
            "Burnable", "Mintable", "Pausable", "Access Control", "Flash Minting"
        ]
        enabled_features = [
            name for name, enabled in zip(feature_names, token_data['features'])
            if enabled
        ]

        # Get tax wallet display text
        tax_wallet_display = token_data.get('tax_wallet', '')
        if not tax_wallet_display:
            tax_wallet_display = "Deployer's address"

        tx_details = f"""
🔍 Transaction Details

Token Information:
• Name: {token_data['name']}
• Symbol: {token_data['symbol']}
• Supply: {token_data['total_supply']:,}
• Decimals: {token_data['decimals']}
• Buy Tax: {buy_tax / 100}%
• Sell Tax: {sell_tax / 100}%
• Tax Wallet: {tax_wallet_display}
• Features: {', '.join(enabled_features) if enabled_features else 'None'}

Network: {network.title()}

Transaction Cost:
• Gas Price: {web3.from_wei(gas_price, 'gwei')} Gwei
• Gas Limit: {gas_limit:,}
• Est. Cost: {transaction_cost_eth:.6f} {network.upper()}
• Your Balance: {current_balance_eth:.6f} {network.upper()}

Do you want to proceed with deployment?
        """

        # Generate confirmation callback ID
        confirm_id = f"c_{user_id}_{int(time.time())}"
        callback_data_store[confirm_id] = {
            'type': 'confirm_deploy',
            'token_data': token_data,
            'network': network
        }

        # Create confirmation buttons
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn1 = types.InlineKeyboardButton('✅ Approve', callback_data=confirm_id)
        btn2 = types.InlineKeyboardButton('❌ Cancel', callback_data='cancel_deploy')
        markup.add(btn1, btn2)

        bot.edit_message_text(
            tx_details,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown')

    except Exception as e:
        print(f"Error calculating deployment details: {e}")
        bot.edit_message_text(
            f"❌ Deployment Preparation Failed\n\n"
            f"Error: {str(e)}\n\n"
            f"Please check your wallet and try again.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('c_'))
def confirm_deploy_token(call):
    user_id = call.from_user.id
    callback_id = call.data

    # Retrieve stored data
    if callback_id not in callback_data_store:
        bot.answer_callback_query(call.id, "Session expired. Please try again.", show_alert=True)
        return

    data = callback_data_store[callback_id]

    if data['type'] == 'confirm_deploy':
        token_data = data['token_data']
        network = data['network']

        # Show deploying message
        bot.edit_message_text(
            f"🚀 Deploying Token on {network.title()}...\n\n"
            f"⏳ Transaction submitted. Waiting for confirmation...\n\n"
            f"This process can take 30-60 seconds depending on network congestion.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown')

        # Actually deploy the token
        contract_address, details = deploy_token(user_id, token_data, network)

        if isinstance(details, dict):  # Successful deployment
            # Generate pool callback ID
            pool_id = f"p_{user_id}_{int(time.time())}"
            callback_data_store[pool_id] = {
                'type': 'pool',
                'contract_address': contract_address,
                'network': network
            }

            # Show success message
            markup = types.InlineKeyboardMarkup(row_width=1)
            btn1 = types.InlineKeyboardButton('💧 Create Pool', callback_data=pool_id)
            btn2 = types.InlineKeyboardButton('📊 View on Explorer',
                                            url=get_explorer_url(
                                                contract_address, network))
            markup.add(btn1, btn2)

            bot.edit_message_text(
                f"🎉 Token Deployed Successfully!\n\n"
                f"📍 Contract Address:\n`{contract_address}`\n\n"
                f"🌐 Network: {network.title()}\n"
                f"🪙 Token: {token_data['name']} ({token_data['symbol']})\n\n"
                f"Transaction Hash: `{details.get('tx_hash', 'N/A')}`\n\n"
                f"Next Steps:\n"
                f"• Create a liquidity pool\n"
                f"• Add initial liquidity\n"
                f"• Start trading!",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode='Markdown')
        else:  # Error occurred
            bot.edit_message_text(
                f"❌ Deployment Failed\n\n"
                f"Error: {details}\n\n"
                f"Please check your wallet balance and try again.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown')

    # Clean up callback data
    del callback_data_store[callback_id]

@bot.callback_query_handler(func=lambda call: call.data == 'cancel_deploy')
def cancel_token_deployment(call):
    user_id = call.from_user.id

    bot.edit_message_text(
        "❌ **Deployment Cancelled**\n\n"
        "Your token deployment has been cancelled. No fees were charged.\n\n"
        "Use /start to return to the main menu.",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown')

    # Clean up user data
    user_states[user_id] = UserState.MAIN_MENU
    if user_id in user_data:
        del user_data[user_id]

@bot.callback_query_handler(func=lambda call: call.data.startswith('p_'))
def handle_pool_callback(call):
    user_id = call.from_user.id
    callback_id = call.data

    # Retrieve stored data
    if callback_id not in callback_data_store:
        bot.answer_callback_query(call.id, "Session expired. Please try again.", show_alert=True)
        return

    data = callback_data_store[callback_id]
    print(f"Pool callback data: {data}")

    if data['type'] == 'pool':
        # Start pool creation with the token from callback data
        create_pool_start(call, data['contract_address'], data['network'])

        # Remove the callback data after use
        del callback_data_store[callback_id]

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == UserState.POOL_CREATION)
def handle_pool_creation(message):
    user_id = message.from_user.id

    if user_id not in user_data:
        return

    step = user_data[user_id].get('step', 'token_amount')

    if step == 'token_amount':
        try:
            token_amount = float(message.text)
            user_data[user_id]['token_amount'] = token_amount
            user_data[user_id]['step'] = 'eth_amount'

            currency = "MATIC" if user_data[user_id]['network'] == 'polygon' else "ETH"

            # Suggest ETH/MATIC amounts based on token amount
            eth_suggestions = [0.1, 0.5, 1, 5, 10]
            
            markup = types.InlineKeyboardMarkup(row_width=3)
            for amount in eth_suggestions:
                btn = types.InlineKeyboardButton(f'{amount} {currency}', callback_data=f'eth_amount_{amount}')
                markup.add(btn)
            markup.add(types.InlineKeyboardButton('Custom Amount', callback_data='eth_amount_custom'))

            bot.send_message(
                message.chat.id, f"✅ Token amount: **{token_amount:,}**\n\n"
                f"**Step 2/2:** Select {currency} amount for initial liquidity or enter a custom amount:",
                reply_markup=markup,
                parse_mode='Markdown')
        except ValueError:
            bot.send_message(
                message.chat.id,
                "❌ Please enter a valid number for token amount.")

    elif step == 'eth_amount':
        try:
            eth_amount = float(message.text)
            user_data[user_id]['eth_amount'] = eth_amount

            # Show confirmation
            markup = types.InlineKeyboardMarkup(row_width=2)
            btn1 = types.InlineKeyboardButton(
                '✅ Create Pool', callback_data='confirm_pool_creation')
            btn2 = types.InlineKeyboardButton(
                '❌ Cancel', callback_data='cancel_pool_creation')
            markup.add(btn1, btn2)

            currency = "MATIC" if user_data[user_id]['network'] == 'polygon' else "ETH"
            
            # Include token info if available
            token_info = user_data[user_id].get('token_info', None)
            token_display = ""
            if token_info:
                token_display = f"\n**Token:** {token_info['name']} ({token_info['symbol']})"
            
            bot.send_message(
                message.chat.id, f"💧 **Pool Creation Summary**\n\n"
                f"🪙 **Token Amount:** {user_data[user_id]['token_amount']:,}\n"
                f"💰 **{currency} Amount:** {eth_amount}\n"
                f"🌐 **Network:** {user_data[user_id]['network'].title()}{token_display}\n"
                f"📍 **Token Address:** `{user_data[user_id]['token_address']}`\n\n"
                f"⚠️ **Important:** Make sure you have enough {currency} for gas fees!\n\n"
                f"Proceed with pool creation?",
                reply_markup=markup,
                parse_mode='Markdown')
        except ValueError:
            currency = "MATIC" if user_data[user_id]['network'] == 'polygon' else "ETH"
            bot.send_message(
                message.chat.id,
                f"❌ Please enter a valid number for {currency} amount.")

@bot.callback_query_handler(func=lambda call: call.data == 'confirm_pool_creation')
def confirm_pool_creation(call):
    user_id = call.from_user.id

    # Get pool parameters from user data
    token_address = user_data[user_id]['token_address']
    network = user_data[user_id]['network']
    liquidity_data = {
        'token_amount': user_data[user_id]['token_amount'],
        'eth_amount': user_data[user_id]['eth_amount']
    }

    # Check pool details first (but don't execute yet)
    pool_address, details = create_uniswap_pool(user_id, token_address, liquidity_data, network)

    if isinstance(details, dict):  # Successful preparation with pool details
        # Show transaction details for approval
        currency = "MATIC" if network == 'polygon' else "ETH"

        # Prepare message based on whether pool exists or not
        pool_status = "Existing pool will be used" if details.get('pool_exists') else "New pool will be created"
        
        tx_details = f"""
🔍 Pool Creation Details

Liquidity Information:
• Token Address: `{token_address}`
• Token Amount: {liquidity_data['token_amount']:,} tokens
• {currency} Amount: {liquidity_data['eth_amount']} {currency}

Network: {network.title()}
Pool Status: {pool_status}

Transaction Cost:
• Gas Price: {details['gas_price']} Gwei
• Gas Limit: {details['gas_limit']:,}
• Gas Cost: {details['transaction_cost']:.6f} {currency}
• Total Cost: {details['total_cost']:.6f} {currency} (including liquidity)
• Your Balance: {details['current_balance']:.6f} {currency}

Do you want to proceed with pool creation?
        """

        # Generate short callback ID for the pool execution
        exec_id = f"e_{user_id}_{int(time.time())}"
        callback_data_store[exec_id] = {
            'type': 'execute_pool',
            'pool_address': pool_address,
            'network': network
        }

        markup = types.InlineKeyboardMarkup(row_width=2)
        btn1 = types.InlineKeyboardButton('✅ Approve', callback_data=exec_id)
        btn2 = types.InlineKeyboardButton('❌ Cancel', callback_data='cancel_pool_creation')
        markup.add(btn1, btn2)

        bot.edit_message_text(
            tx_details,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown')
    else:  # Error occurred
        bot.edit_message_text(
            f"❌ Pool Creation Failed\n\n"
            f"Error: {details}\n\n"
            f"Please check your wallet balance and try again.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown')

        # Clean up user data
        user_states[user_id] = UserState.MAIN_MENU
        if user_id in user_data:
            del user_data[user_id]

@bot.callback_query_handler(func=lambda call: call.data == 'cancel_pool_creation')
def cancel_pool_creation(call):
    user_id = call.from_user.id
    user_states[user_id] = UserState.MAIN_MENU
    if user_id in user_data:
        del user_data[user_id]

    bot.edit_message_text(
        "❌ Pool creation cancelled.\n\nUse /start to return to main menu.",
        call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_main')
def back_to_main_menu(call):
    user_id = call.from_user.id
    user_states[user_id] = UserState.MAIN_MENU

    bot.edit_message_text(
        "✅ Returning to main menu.\n\nUse /start to show all options.",
        call.message.chat.id, call.message.message_id)

@bot.message_handler(func=lambda message: message.text == '💧 Create Pool')
def create_pool_options(message):
    user_id = message.from_user.id
    
    # Check if user has wallet
    wallet = get_user_wallet(user_id)
    if not wallet:
        bot.send_message(
            message.chat.id,
            "❌ **No wallet found!**\n\nPlease setup your wallet first using the '🔐 Setup Wallet' button.",
            parse_mode='Markdown')
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn1 = types.InlineKeyboardButton('🔍 Select from my tokens', callback_data='select_my_tokens')
    btn2 = types.InlineKeyboardButton('📝 Enter custom token address', callback_data='enter_custom_token')
    markup.add(btn1, btn2)
    
    bot.send_message(
        message.chat.id,
        "💧 **Create Liquidity Pool**\n\n"
        "Choose an option:\n"
        "• Select from tokens you've created\n"
        "• Enter a custom token address",
        reply_markup=markup,
        parse_mode='Markdown'
    )

@bot.callback_query_handler(func=lambda call: call.data == 'select_my_tokens')
def select_from_my_tokens(call):
    user_id = call.from_user.id
    user_id_str = str(user_id)
    
    try:
        with open(TOKENS_FILE, 'r') as f:
            tokens = json.load(f)
        
        if user_id_str not in tokens or not tokens[user_id_str]:
            bot.edit_message_text(
                "❌ You haven't created any tokens yet!\n\n"
                "Use '🪙 Create Token' to deploy your first token or select 'Enter custom token address'.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown')
            return
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        # Add each token as a button
        for i, token in enumerate(tokens[user_id_str]):
            token_info = f"{token['token_name']} ({token['token_symbol']}) - {token['network'].title()}"
            callback_data = f"token_{token['contract_address']}_{token['network']}"
            btn = types.InlineKeyboardButton(token_info, callback_data=callback_data)
            markup.add(btn)
        
        # Add back button
        back_btn = types.InlineKeyboardButton('⬅️ Back', callback_data='back_to_pool_options')
        markup.add(back_btn)
        
        bot.edit_message_text(
            "🔍 **Select a token:**\n\n"
            "Choose one of your tokens to create a pool for:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown')
    except Exception as e:
        print(f"Error loading tokens: {e}")
        bot.edit_message_text(
            f"❌ Error loading tokens: {str(e)}",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_pool_options')
def back_to_pool_options(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn1 = types.InlineKeyboardButton('🔍 Select from my tokens', callback_data='select_my_tokens')
    btn2 = types.InlineKeyboardButton('📝 Enter custom token address', callback_data='enter_custom_token')
    markup.add(btn1, btn2)
    
    bot.edit_message_text(
        "💧 **Create Liquidity Pool**\n\n"
        "Choose an option:\n"
        "• Select from tokens you've created\n"
        "• Enter a custom token address",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('token_'))
def token_selected(call):
    user_id = call.from_user.id
    
    # Extract token address and network from callback data
    # Format: token_ADDRESS_NETWORK
    parts = call.data.split('_')
    if len(parts) >= 3:
        token_address = parts[1]
        network = parts[2]
        
        # Start pool creation process with selected token
        create_pool_start(call, token_address, network)
    else:
        bot.answer_callback_query(call.id, "Invalid token selection", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == 'enter_custom_token')
def enter_custom_token(call):
    user_id = call.from_user.id
    user_states[user_id] = UserState.ENTERING_TOKEN_ADDRESS
    
    bot.edit_message_text(
        "📝 **Enter Custom Token Address**\n\n"
        "Please send the contract address of the token you want to create a pool for.\n\n"
        "Make sure it's a valid ERC20 token address.",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown')
    
    # Send a follow-up message to clarify what to do next
    bot.send_message(
        call.message.chat.id,
        "Reply to this message with the token contract address.",
        parse_mode='Markdown')

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == UserState.ENTERING_TOKEN_ADDRESS)
def handle_token_address(message):
    user_id = message.from_user.id
    token_address = message.text.strip()
    
    print(f"Received token address: {token_address} from user {user_id}")
    
    # Basic validation for Ethereum address format
    if not (token_address.startswith('0x') and len(token_address) == 42):
        bot.send_message(
            message.chat.id,
            "❌ Invalid Ethereum address format.\n\n"
            "Please enter a valid ERC20 token address starting with '0x' and 42 characters in length.",
            parse_mode='Markdown')
        return
    
    # Ask user to select network
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton('🟣 Polygon', callback_data=f'custom_network_polygon_{token_address}')
    btn2 = types.InlineKeyboardButton('🔷 Ethereum', callback_data=f'custom_network_ethereum_{token_address}')
    markup.add(btn1, btn2)
    
    bot.send_message(
        message.chat.id,
        f"✅ Token address received: `{token_address}`\n\n"
        f"Please select the network for this token:",
        reply_markup=markup,
        parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('custom_network_'))
def custom_token_network_selected(call):
    user_id = call.from_user.id
    
    # Extract network and token address from callback data
    # Format: custom_network_NETWORK_ADDRESS
    parts = call.data.split('_')
    if len(parts) >= 4:
        network = parts[2]
        token_address = parts[3]
        
        print(f"Selected network {network} for token {token_address}")
        
        # Validate the token on the selected network
        try:
            web3 = get_web3(network)
            
            # Show validating message
            bot.edit_message_text(
                f"⏳ Validating token `{token_address}` on {network.title()}...",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown'
            )
            
            # Try to create a contract instance and get basic info
            token_contract = web3.eth.contract(address=token_address, abi=ERC20_ABI)
            
            try:
                token_name = token_contract.functions.name().call()
                token_symbol = token_contract.functions.symbol().call()
                token_decimals = token_contract.functions.decimals().call()
                
                print(f"Successfully validated token: {token_name} ({token_symbol})")
                
                # Start pool creation process with validated token
                create_pool_start(call, token_address, network, token_info={
                    'name': token_name,
                    'symbol': token_symbol,
                    'decimals': token_decimals
                })
            except Exception as e:
                print(f"Error getting token info: {e}")
                bot.edit_message_text(
                    f"❌ Error validating token: Could not read token information.\n\n"
                    f"Make sure this is a valid ERC20 token on {network.title()} network.",
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode='Markdown')
        except Exception as e:
            print(f"Error validating token: {e}")
            bot.edit_message_text(
                f"❌ Error validating token: {str(e)}\n\n"
                f"Please check the address and try again.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown')
    else:
        bot.answer_callback_query(call.id, "Invalid selection", show_alert=True)

# Update the create_pool_start function to handle token_info parameter
def create_pool_start(call, token_address, network, token_info=None):
    user_id = call.from_user.id
    print(f"Creating pool for token: {token_address} on network: {network}")

    user_states[user_id] = UserState.POOL_CREATION
    user_data[user_id] = {
        'token_address': token_address,
        'network': network,
        'step': 'token_amount'
    }
    
    # If token_info is provided, store it
    if token_info:
        user_data[user_id]['token_info'] = token_info
    
    # Get token info if not provided
    token_display = ""
    if token_info:
        token_display = f"\n\nToken: **{token_info['name']} ({token_info['symbol']})**"
    
    # Try to get token supply from database or contract
    token_supply = None
    try:
        # First check if we have this token in our database
        with open(TOKENS_FILE, 'r') as f:
            tokens = json.load(f)
            user_id_str = str(user_id)
            if user_id_str in tokens:
                for token in tokens[user_id_str]:
                    if token['contract_address'].lower() == token_address.lower():
                        token_supply = token['total_supply']
                        break
        
        # If not found in database, try to get from contract
        if token_supply is None and token_info and 'decimals' in token_info:
            web3 = get_web3(network)
            token_contract = web3.eth.contract(address=token_address, abi=ERC20_ABI)
            total_supply_raw = token_contract.functions.totalSupply().call()
            token_supply = total_supply_raw / (10 ** token_info['decimals'])
    except Exception as e:
        print(f"Error getting token supply: {e}")
    
    # Create markup with suggested percentages if we have token supply
    markup = None
    if token_supply:
        user_data[user_id]['token_supply'] = token_supply
        
        # Calculate suggested amounts
        amount_25_percent = int(token_supply * 0.25)
        amount_50_percent = int(token_supply * 0.5)
        amount_75_percent = int(token_supply * 0.75)
        amount_100_percent = int(token_supply)
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn1 = types.InlineKeyboardButton(f'25% ({amount_25_percent:,})', callback_data=f'pool_amount_{amount_25_percent}')
        btn2 = types.InlineKeyboardButton(f'50% ({amount_50_percent:,})', callback_data=f'pool_amount_{amount_50_percent}')
        btn3 = types.InlineKeyboardButton(f'75% ({amount_75_percent:,})', callback_data=f'pool_amount_{amount_75_percent}')
        btn4 = types.InlineKeyboardButton(f'100% ({amount_100_percent:,})', callback_data=f'pool_amount_{amount_100_percent}')
        btn5 = types.InlineKeyboardButton('Custom Amount', callback_data='pool_amount_custom')
        markup.add(btn1, btn2, btn3, btn4, btn5)
    
    message_text = f"💧 Create Liquidity Pool{token_display}\n\n" \
                  f"We'll create a Uniswap V3 pool for your token.\n\n" \
                  f"**Step 1/2:** "
    
    if token_supply:
        message_text += f"Select token amount for initial liquidity or enter a custom amount:"
    else:
        message_text += f"Enter token amount for initial liquidity:\n(e.g., '10000' tokens)"
    
    bot.edit_message_text(
        message_text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode='Markdown')

    # Also send a new message to make it clearer to the user what to do next
    if not markup:
        bot.send_message(
            call.message.chat.id,
            "Please reply with the amount of tokens you want to add to the pool.",
            parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('pool_amount_'))
def handle_pool_amount_selection(call):
    user_id = call.from_user.id
    amount_option = call.data.split('_')[2]
    
    if amount_option == 'custom':
        bot.send_message(
            call.message.chat.id,
            "Please enter your custom token amount for the pool:",
            parse_mode='Markdown')
    else:
        token_amount = int(amount_option)
        user_data[user_id]['token_amount'] = token_amount
        user_data[user_id]['step'] = 'eth_amount'

        currency = "MATIC" if user_data[user_id]['network'] == 'polygon' else "ETH"
        
        # Suggest ETH/MATIC amounts based on token amount
        # These are just examples, you might want to calculate based on token value
        eth_suggestions = [0.1, 0.5, 1, 5, 10]
        
        markup = types.InlineKeyboardMarkup(row_width=3)
        for amount in eth_suggestions:
            btn = types.InlineKeyboardButton(f'{amount} {currency}', callback_data=f'eth_amount_{amount}')
            markup.add(btn)
        markup.add(types.InlineKeyboardButton('Custom Amount', callback_data='eth_amount_custom'))

        bot.send_message(
            call.message.chat.id, 
            f"✅ Token amount: **{token_amount:,}**\n\n"
            f"**Step 2/2:** Select {currency} amount for initial liquidity or enter a custom amount:",
            reply_markup=markup,
            parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('eth_amount_'))
def handle_eth_amount_selection(call):
    user_id = call.from_user.id
    amount_option = call.data.split('_')[2]
    
    if amount_option == 'custom':
        bot.send_message(
            call.message.chat.id,
            f"Please enter your custom {user_data[user_id]['network'].title()} amount:",
            parse_mode='Markdown')
    else:
        eth_amount = float(amount_option)
        user_data[user_id]['eth_amount'] = eth_amount

        # Show confirmation
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn1 = types.InlineKeyboardButton(
            '✅ Create Pool', callback_data='confirm_pool_creation')
        btn2 = types.InlineKeyboardButton(
            '❌ Cancel', callback_data='cancel_pool_creation')
        markup.add(btn1, btn2)

        currency = "MATIC" if user_data[user_id]['network'] == 'polygon' else "ETH"
        
        # Include token info if available
        token_info = user_data[user_id].get('token_info', None)
        token_display = ""
        if token_info:
            token_display = f"\n**Token:** {token_info['name']} ({token_info['symbol']})"
        
        bot.send_message(
            call.message.chat.id, f"💧 **Pool Creation Summary**\n\n"
            f"🪙 **Token Amount:** {user_data[user_id]['token_amount']:,}\n"
            f"💰 **{currency} Amount:** {eth_amount}\n"
            f"🌐 **Network:** {user_data[user_id]['network'].title()}{token_display}\n"
            f"📍 **Token Address:** `{user_data[user_id]['token_address']}`\n\n"
            f"⚠️ **Important:** Make sure you have enough {currency} for gas fees!\n\n"
            f"Proceed with pool creation?",
            reply_markup=markup,
            parse_mode='Markdown')

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == UserState.POOL_CREATION)
def handle_pool_creation(message):
    user_id = message.from_user.id

    if user_id not in user_data:
        return

    step = user_data[user_id].get('step', 'token_amount')

    if step == 'token_amount':
        try:
            token_amount = float(message.text)
            user_data[user_id]['token_amount'] = token_amount
            user_data[user_id]['step'] = 'eth_amount'

            currency = "MATIC" if user_data[user_id]['network'] == 'polygon' else "ETH"

            # Suggest ETH/MATIC amounts based on token amount
            eth_suggestions = [0.1, 0.5, 1, 5, 10]
            
            markup = types.InlineKeyboardMarkup(row_width=3)
            for amount in eth_suggestions:
                btn = types.InlineKeyboardButton(f'{amount} {currency}', callback_data=f'eth_amount_{amount}')
                markup.add(btn)
            markup.add(types.InlineKeyboardButton('Custom Amount', callback_data='eth_amount_custom'))

            bot.send_message(
                message.chat.id, f"✅ Token amount: **{token_amount:,}**\n\n"
                f"**Step 2/2:** Select {currency} amount for initial liquidity or enter a custom amount:",
                reply_markup=markup,
                parse_mode='Markdown')
        except ValueError:
            bot.send_message(
                message.chat.id,
                "❌ Please enter a valid number for token amount.")

    elif step == 'eth_amount':
        try:
            eth_amount = float(message.text)
            user_data[user_id]['eth_amount'] = eth_amount

            # Show confirmation
            markup = types.InlineKeyboardMarkup(row_width=2)
            btn1 = types.InlineKeyboardButton(
                '✅ Create Pool', callback_data='confirm_pool_creation')
            btn2 = types.InlineKeyboardButton(
                '❌ Cancel', callback_data='cancel_pool_creation')
            markup.add(btn1, btn2)

            currency = "MATIC" if user_data[user_id]['network'] == 'polygon' else "ETH"
            
            # Include token info if available
            token_info = user_data[user_id].get('token_info', None)
            token_display = ""
            if token_info:
                token_display = f"\n**Token:** {token_info['name']} ({token_info['symbol']})"
            
            bot.send_message(
                message.chat.id, f"💧 **Pool Creation Summary**\n\n"
                f"🪙 **Token Amount:** {user_data[user_id]['token_amount']:,}\n"
                f"💰 **{currency} Amount:** {eth_amount}\n"
                f"🌐 **Network:** {user_data[user_id]['network'].title()}{token_display}\n"
                f"📍 **Token Address:** `{user_data[user_id]['token_address']}`\n\n"
                f"⚠️ **Important:** Make sure you have enough {currency} for gas fees!\n\n"
                f"Proceed with pool creation?",
                reply_markup=markup,
                parse_mode='Markdown')
        except ValueError:
            currency = "MATIC" if user_data[user_id]['network'] == 'polygon' else "ETH"
            bot.send_message(
                message.chat.id,
                f"❌ Please enter a valid number for {currency} amount.")

@bot.message_handler(func=lambda message: message.text == '📊 My Tokens')
def show_my_tokens(message):
    user_id = message.from_user.id
    user_id_str = str(user_id)

    with open(TOKENS_FILE, 'r') as f:
        tokens = json.load(f)

    if user_id_str not in tokens or not tokens[user_id_str]:
        bot.send_message(message.chat.id, "📊 **My Tokens**\n\n"
                         "You haven't created any tokens yet!\n\n"
                         "Use '🪙 Create Token' to deploy your first token.",
                         parse_mode='Markdown')
        return

    token_list = "📊 **Your Tokens:**\n\n"

    for i, token in enumerate(tokens[user_id_str], 1):
        token_list += f"**{i}. {token['token_name']} ({token['token_symbol']})**\n"
        token_list += f"📍 `{token['contract_address']}`\n"
        token_list += f"🌐 {token['network'].title()}\n"
        token_list += f"📅 {token['created_at']}\n\n"

    bot.send_message(message.chat.id, token_list, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == 'ℹ️ Help')
def show_help(message):
    help_text = """
ℹ️ **Help & Instructions**

**Getting Started:**
1. 🔐 Setup your wallet (create new or import existing)
2. 💰 Add MATIC/ETH to your wallet for gas fees
3. 🪙 Create your custom token
4. 💧 Create liquidity pool
5. 🎯 Start trading!

**Token Features:**
• **🔥 Burnable:** Allow tokens to be burned (reduced from supply)
• **➕ Mintable:** Create new tokens to increase supply
• **⏸️ Pausable:** Ability to pause all token transfers
• **🔒 Access Control:** Role-based permissions system
• **⚡ Flash Minting:** Allow flash loans of your token

**Tax System:**
• Buy Tax: Applied when users purchase your token
• Sell Tax: Applied when users sell your token
• Range: 0-25% for both buy and sell

**Supported Networks:**
• 🟣 Polygon (Lower fees, faster transactions)
• 🔷 Ethereum (Higher fees, more established)

**Security Tips:**
• Never share your private key
• Keep your seed phrase safe
• Test with small amounts first
• Verify contract addresses

**Need more help?** Contact @YourSupportHandle
    """

    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == '⚙️ Settings')
def show_settings(message):
    user_id = message.from_user.id
    wallet = get_user_wallet(user_id)

    if not wallet:
        wallet_status = "❌ No wallet configured"
        wallet_address = "N/A"
    else:
        wallet_status = "✅ Wallet configured"
        wallet_address = f"`{wallet['address'][:10]}...{wallet['address'][-10:]}`"

    markup = types.InlineKeyboardMarkup(row_width=1)
    btn1 = types.InlineKeyboardButton('🔄 Change Wallet',
                                      callback_data='change_wallet')
    btn2 = types.InlineKeyboardButton('📋 Export Wallet',
                                      callback_data='export_wallet')
    btn3 = types.InlineKeyboardButton('🗑️ Delete Data',
                                      callback_data='delete_data')
    markup.add(btn1, btn2, btn3)

    settings_text = f"""
⚙️ **Settings**

**Wallet Status:** {wallet_status}
**Address:** {wallet_address}

**Options:**
    """

    bot.send_message(message.chat.id,
                     settings_text,
                     reply_markup=markup,
                     parse_mode='Markdown')


@bot.callback_query_handler(func=lambda call: call.data == 'change_wallet')
def change_wallet_callback(call):
    user_id = call.from_user.id
    user_states[user_id] = UserState.WALLET_SETUP

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton('🆕 Create New Wallet',
                                      callback_data='create_wallet')
    btn2 = types.InlineKeyboardButton('📥 Import Existing',
                                      callback_data='import_wallet')
    markup.add(btn1, btn2)

    bot.edit_message_text(
        "🔐 **Change Wallet**\n\n"
        "Choose an option to change your wallet:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode='Markdown')


@bot.callback_query_handler(func=lambda call: call.data == 'export_wallet_key')
def export_wallet_key(call):
    user_id = call.from_user.id
    wallet = get_user_wallet(user_id)

    if wallet:
        # Send private key in a private message
        key_message = f"""
🔐 **Your Private Key**

`{wallet['private_key']}`

⚠️ **IMPORTANT:** Never share this key with anyone! Keep it secure!
This message will be deleted in 60 seconds for security.
        """

        # Send and setup message to delete after 60 seconds
        sent_msg = bot.send_message(call.message.chat.id,
                                    key_message,
                                    parse_mode='Markdown')

        # Delete the callback message to avoid confusion
        bot.edit_message_text(
            "🔒 Private key has been sent in a separate message.\nPlease save it securely and delete the message after you've saved it.",
            call.message.chat.id, call.message.message_id)

        # Schedule message deletion after 60 seconds
        # Since we can't use threading in this simplified version, we'll just advise the user
        bot.send_message(
            call.message.chat.id,
            "⏱ For security, please delete the message with your private key after saving it."
        )
    else:
        bot.answer_callback_query(
            call.id,
            "No wallet found. Please set up a wallet first.",
            show_alert=True)



@bot.message_handler(commands=['debug'])
def debug_info(message):
    user_id = message.from_user.id

    debug_text = "🔍 **Debug Information**\n\n"

    # Check data directory
    debug_text += f"**Data Directory:** `{os.path.abspath(DATA_DIR)}`\n"
    debug_text += f"**Data Directory Exists:** {'✅' if os.path.exists(DATA_DIR) else '❌'}\n\n"

    # Check files
    debug_text += f"**Users File Exists:** {'✅' if os.path.exists(USERS_FILE) else '❌'}\n"
    debug_text += f"**Tokens File Exists:** {'✅' if os.path.exists(TOKENS_FILE) else '❌'}\n"
    debug_text += f"**Pools File Exists:** {'✅' if os.path.exists(POOLS_FILE) else '❌'}\n\n"

    # Check user state
    debug_text += f"**Current User State:** `{user_states.get(user_id, 'Not set')}`\n\n"

    # Check wallet
    wallet = get_user_wallet(user_id)
    if wallet:
        debug_text += f"**Wallet Found:** ✅\n"
        debug_text += f"**Wallet Address:** `{wallet['address']}`\n"
        debug_text += f"**Private Key (first 5 chars):** `{wallet['private_key'][:5]}...`\n"
    else:
        debug_text += f"**Wallet Found:** ❌\n"

    # Let's try to read the users file directly
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                content = f.read()
                if content.strip():
                    users = json.loads(content)
                    debug_text += f"\n**User IDs in file:** {', '.join(users.keys())}\n"
                    debug_text += f"**Your User ID:** `{user_id}`\n"
                else:
                    debug_text += "\n**Users file is empty**\n"
    except Exception as e:
        debug_text += f"\n**Error reading users file:** `{str(e)}`\n"

    bot.send_message(message.chat.id, debug_text, parse_mode='Markdown')

@bot.message_handler(commands=['wallet'])
def wallet_command(message):
    user_id = message.from_user.id
    wallet = get_user_wallet(user_id)

    if not wallet:
        markup = types.InlineKeyboardMarkup(row_width=1)
        btn = types.InlineKeyboardButton('🔐 Setup Wallet', callback_data='setup_wallet')
        markup.add(btn)

        bot.send_message(
            message.chat.id,
            "🔑 **Wallet Management**\n\n"
            "You don't have a wallet set up yet. Would you like to create one?",
            reply_markup=markup,
            parse_mode='Markdown')
    else:
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn1 = types.InlineKeyboardButton('🔄 Change Wallet', callback_data='change_wallet')
        btn2 = types.InlineKeyboardButton('📋 Export Key', callback_data='export_wallet_key')
        markup.add(btn1, btn2)

        wallet_text = f"""
🔑 **Your Wallet**

**Address:** `{wallet['address']}`

**Balance:** (use `/balance` to check)

Use the buttons below to manage your wallet.
        """

        bot.send_message(
            message.chat.id,
            wallet_text,
            reply_markup=markup,
            parse_mode='Markdown')

@bot.message_handler(commands=['balance'])
def check_balance(message):
    user_id = message.from_user.id
    wallet = get_user_wallet(user_id)

    if not wallet:
        bot.send_message(
            message.chat.id,
            "❌ **No wallet found!**\n\n"
            "Please setup your wallet first using the '🔐 Setup Wallet' button or /wallet command.",
            parse_mode='Markdown')
        return

    # Show balance checking message
    sent_msg = bot.send_message(
        message.chat.id,
        "⏳ **Checking wallet balance...**",
        parse_mode='Markdown')

    try:
        # Check Polygon balance
        polygon_web3 = get_web3('polygon')
        polygon_balance_wei = polygon_web3.eth.get_balance(wallet['address'])
        polygon_balance = polygon_web3.from_wei(polygon_balance_wei, 'ether')

        # Check Ethereum balance 
        eth_web3 = get_web3('ethereum')
        eth_balance_wei = eth_web3.eth.get_balance(wallet['address'])
        eth_balance = eth_web3.from_wei(eth_balance_wei, 'ether')

        # Format the balances
        balance_text = f"""
💰 **Wallet Balance**

**Address:** `{wallet['address']}`

**Polygon:** {polygon_balance:.6f} MATIC
**Ethereum:** {eth_balance:.6f} ETH

_To add funds to your wallet, send MATIC/ETH to the address above._
        """

        # Update message with balance info
        bot.edit_message_text(
            balance_text,
            sent_msg.chat.id,
            sent_msg.message_id,
            parse_mode='Markdown')

    except Exception as e:
        bot.edit_message_text(
            f"❌ **Error checking balance:**\n\n{str(e)}",
            sent_msg.chat.id,
            sent_msg.message_id,
            parse_mode='Markdown')

# Handle private key import
@bot.message_handler(
    func=lambda message: user_states.get(message.from_user.id) == UserState.WALLET_SETUP and len(message.text) >= 64)
def import_wallet_handler(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    try:
        # Try to clean up the private key format
        private_key = message.text.strip()
        if not private_key.startswith('0x'):
            private_key = '0x' + private_key

        # Attempt to create account from private key
        account = Account.from_key(private_key)
        wallet_data = {'address': account.address, 'private_key': private_key}

        # Save wallet
        save_user_wallet(user_id, username, wallet_data)
        user_states[user_id] = UserState.MAIN_MENU

        # Send confirmation
        confirmation_text = f"""
✅ **Wallet Imported Successfully!**

🏦 **Address:** `{wallet_data['address']}`

🔒 Your private key has been securely stored.

Use /start to return to main menu.
"""
        bot.send_message(message.chat.id, confirmation_text, parse_mode='Markdown')

        # Delete message with private key if possible
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except Exception:
            # If deletion fails, advise user to delete it themselves
            bot.send_message(message.chat.id, "⚠️ Please delete your previous message containing the private key for security.")

    except Exception as e:
        print(f"Wallet import error: {str(e)}")
        bot.send_message(
            message.chat.id,
            f"❌ **Invalid private key!**\n\nPlease make sure you entered a valid private key (64 characters, with or without '0x' prefix)."
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith('e_'))
def handle_execute_pool_callback(call):
    user_id = call.from_user.id
    callback_id = call.data

    # Retrieve stored data
    if callback_id not in callback_data_store:
        bot.answer_callback_query(call.id, "Session expired. Please try again.", show_alert=True)
        return

    data = callback_data_store[callback_id]

    if data['type'] == 'execute_pool':
        # Show processing message
        bot.edit_message_text(
            f"🚀 Creating Pool and Adding Liquidity...\n\n"
            f"⏳ This may take a minute or two. Please wait patiently.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown')

        # Get token address and liquidity data from user_data
        token_address = user_data[user_id]['token_address']
        network = user_data[user_id]['network']
        liquidity_data = {
            'token_amount': user_data[user_id]['token_amount'],
            'eth_amount': user_data[user_id]['eth_amount']
        }

        # Execute pool creation with the new implementation
        result = execute_pool_creation(user_id, token_address, liquidity_data, network)

        if result['status'] == 'success':
            # Success! Show completion message
            currency = "MATIC" if network == 'polygon' else "ETH"
            tx_hash = result['tx_hash']
            pool_address = result['pool_address']
            position_id = result.get('position_id', 'N/A')
            
            # Create explorer URLs
            pool_explorer_url = get_explorer_url(pool_address, network)
            
            # Ensure tx_hash has 0x prefix for explorer URLs
            tx_hash_for_url = f"0x{tx_hash}" if tx_hash and not tx_hash.startswith('0x') else tx_hash
            
            tx_explorer_url = f"https://polygonscan.com/tx/{tx_hash_for_url}" if network == 'polygon' else f"https://etherscan.io/tx/{tx_hash_for_url}"

            markup = types.InlineKeyboardMarkup(row_width=1)
            btn1 = types.InlineKeyboardButton('📊 View Pool on Explorer', url=pool_explorer_url)
            btn2 = types.InlineKeyboardButton('🔍 View Transaction', url=tx_explorer_url)
            btn3 = types.InlineKeyboardButton('🔄 Back to Main Menu', callback_data='back_to_main')
            markup.add(btn1, btn2, btn3)

            # Add retry info if applicable
            retry_info = "\n⚠️ Initial attempt failed, but retry was successful." if result.get('retry') else ""
            
            # Format position ID properly
            position_id_display = f"`{position_id}`" if position_id and position_id != 'N/A' else "None"
            
            # Format transaction hash with 0x prefix
            tx_hash_display = f"0x{tx_hash[:8]}...{tx_hash[-8:]}" if not tx_hash.startswith('0x') else f"{tx_hash[:10]}...{tx_hash[-8:]}"

            bot.edit_message_text(
                f"🎉 Success! Pool created and liquidity added!\n\n"
                f"📍 Pool Address:\n`{pool_address}`\n\n"
                f"🔢 Position ID: {position_id_display}\n\n"
                f"💧 Liquidity Added:\n"
                f"• {liquidity_data['token_amount']:,} tokens\n"
                f"• {liquidity_data['eth_amount']} {currency}\n\n"
                f"📝 Transaction: `{tx_hash_display}`{retry_info}\n\n"
                f"🎯 Your token is now tradeable on Uniswap V3!",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode='Markdown')
        else:
            # Error occurred
            error_message = result.get('error', 'Unknown error')
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            btn = types.InlineKeyboardButton('🔄 Back to Main Menu', callback_data='back_to_main')
            markup.add(btn)
            
            bot.edit_message_text(
                f"❌ Pool Creation Failed\n\n"
                f"Error: {error_message}\n\n"
                f"Please check your wallet balance and try again.",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode='Markdown')

        # Clean up user data
        user_states[user_id] = UserState.MAIN_MENU
        if user_id in user_data:
            del user_data[user_id]

    # Clean up callback data
    del callback_data_store[callback_id] 



@bot.message_handler(func=lambda message: message.text == '🔒 Manage Liquidity')
def manage_liquidity(message):
    user_id = message.from_user.id

    # Check if user has wallet
    wallet = get_user_wallet(user_id)
    if not wallet:
        bot.send_message(
            message.chat.id,
            "❌ No wallet found!\n\nPlease setup your wallet first using the '🔐 Setup Wallet' button.",
            parse_mode='Markdown')
        return

    user_states[user_id] = UserState.LIQUIDITY_MANAGEMENT

    # Create markup for liquidity management options
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn1 = types.InlineKeyboardButton('🔍 View My Positions',
                                      callback_data='view_positions')
    btn2 = types.InlineKeyboardButton('🔒 View Locked Positions',
                                      callback_data='view_locked')
    btn3 = types.InlineKeyboardButton('🔄 Back to Main Menu',
                                      callback_data='back_to_main')
    markup.add(btn1, btn2, btn3)

    bot.send_message(
        message.chat.id, "🔒 **Liquidity Management**\n\n"
        "Manage your Uniswap V3 liquidity positions and lock them using UNCX Locker.\n\n"
        "What would you like to do?",
        reply_markup=markup,
        parse_mode='Markdown')


@bot.callback_query_handler(func=lambda call: call.data == 'view_positions')
def view_positions(call):
    user_id = call.from_user.id
    wallet = get_user_wallet(user_id)

    if not wallet:
        bot.edit_message_text(
            "❌ No wallet found!\n\nPlease setup your wallet first.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown')
        return

    # Show loading message
    bot.edit_message_text("🔍 Fetching your liquidity positions...",
                          call.message.chat.id,
                          call.message.message_id,
                          parse_mode='Markdown')

    try:
        # Initialize web3 and locker
        web3 = get_web3('polygon')  # Default to polygon
        locker = LiquidityLocker(web3)

        # Get positions
        positions = locker.get_positions(wallet['address'])

        if not positions:
            markup = types.InlineKeyboardMarkup(row_width=1)
            btn = types.InlineKeyboardButton('🔄 Back',
                                             callback_data='manage_liquidity')
            markup.add(btn)

            bot.edit_message_text(
                "❌ No liquidity positions found!\n\n"
                "You don't have any Uniswap V3 positions in your wallet.",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode='Markdown')
            return

        # Store positions in user data
        user_data[user_id] = {'positions': positions}

        # Create position list message
        position_text = "🔍 **Your Liquidity Positions**\n\n"

        markup = types.InlineKeyboardMarkup(row_width=1)

        for i, position in enumerate(positions):
            # Add position to message
            position_text += f"{i+1}. **{position.token0_symbol}/{position.token1_symbol}** (Fee: {position.fee/10000}%)\n"
            position_text += f"   ID: `{position.token_id}`\n"
            position_text += f"   Liquidity: {position.liquidity}\n\n"

            # Add button to lock this position
            lock_btn = types.InlineKeyboardButton(
                f'🔒 Lock Position #{i+1}', callback_data=f'lock_position_{i}')
            markup.add(lock_btn)

        # Add back button
        back_btn = types.InlineKeyboardButton('🔄 Back',
                                              callback_data='manage_liquidity')
        markup.add(back_btn)

        bot.edit_message_text(position_text,
                              call.message.chat.id,
                              call.message.message_id,
                              reply_markup=markup,
                              parse_mode='Markdown')

    except Exception as e:
        print(f"Error fetching positions: {e}")

        markup = types.InlineKeyboardMarkup(row_width=1)
        btn = types.InlineKeyboardButton('🔄 Back',
                                         callback_data='manage_liquidity')
        markup.add(btn)

        bot.edit_message_text(
            f"❌ Error fetching positions: {str(e)}\n\n"
            f"Please try again later.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown')


@bot.callback_query_handler(func=lambda call: call.data == 'view_locked')
def view_locked_positions(call):
    user_id = call.from_user.id
    wallet = get_user_wallet(user_id)

    if not wallet:
        bot.edit_message_text(
            "❌ No wallet found!\n\nPlease setup your wallet first.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown')
        return

    # Show loading message
    bot.edit_message_text("🔍 Fetching your locked positions...",
                          call.message.chat.id,
                          call.message.message_id,
                          parse_mode='Markdown')

    try:
        # Initialize web3 and locker
        web3 = get_web3('polygon')  # Default to polygon
        locker = LiquidityLocker(web3)

        # Get locked positions
        locked_positions = locker.get_locked_positions(wallet['address'])

        if not locked_positions:
            markup = types.InlineKeyboardMarkup(row_width=1)
            btn = types.InlineKeyboardButton('🔄 Back',
                                             callback_data='manage_liquidity')
            markup.add(btn)

            bot.edit_message_text(
                "❌ No locked positions found!\n\n"
                "You don't have any locked Uniswap V3 positions.",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode='Markdown')
            return

        # Create position list message
        position_text = "🔒 **Your Locked Positions**\n\n"

        for i, position in enumerate(locked_positions):
            status = "🟢 Unlocked" if position.is_expired else "🔒 Locked"
            position_text += f"{i+1}. **{position.token0_symbol}/{position.token1_symbol}**\n"
            position_text += f"   Lock ID: `{position.lock_id}`\n"
            position_text += f"   NFT ID: `{position.nft_id}`\n"
            position_text += f"   Unlock Date: {position.unlock_date_formatted}\n"
            position_text += f"   Status: {status}\n\n"

        markup = types.InlineKeyboardMarkup(row_width=1)
        btn = types.InlineKeyboardButton('🔄 Back',
                                         callback_data='manage_liquidity')
        markup.add(btn)

        bot.edit_message_text(position_text,
                              call.message.chat.id,
                              call.message.message_id,
                              reply_markup=markup,
                              parse_mode='Markdown')

    except Exception as e:
        print(f"Error fetching locked positions: {e}")

        markup = types.InlineKeyboardMarkup(row_width=1)
        btn = types.InlineKeyboardButton('🔄 Back',
                                         callback_data='manage_liquidity')
        markup.add(btn)

        bot.edit_message_text(
            f"❌ Error fetching locked positions: {str(e)}\n\n"
            f"Please try again later.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown')


@bot.callback_query_handler(func=lambda call: call.data == 'manage_liquidity')
def manage_liquidity_callback(call):
    # Re-display the liquidity management options
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn1 = types.InlineKeyboardButton('🔍 View My Positions',
                                      callback_data='view_positions')
    btn2 = types.InlineKeyboardButton('🔒 View Locked Positions',
                                      callback_data='view_locked')
    btn3 = types.InlineKeyboardButton('🔄 Back to Main Menu',
                                      callback_data='back_to_main')
    markup.add(btn1, btn2, btn3)

    bot.edit_message_text(
        "🔒 **Liquidity Management**\n\n"
        "Manage your Uniswap V3 liquidity positions and lock them using UNCX Locker.\n\n"
        "What would you like to do?",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode='Markdown')


@bot.callback_query_handler(
    func=lambda call: call.data.startswith('lock_position_'))
def lock_position_start(call):
    user_id = call.from_user.id
    user_states[user_id] = UserState.LOCK_POSITION

    # Get position index from callback data
    position_idx = int(call.data.split('_')[-1])

    # Get position from user data
    if user_id not in user_data or 'positions' not in user_data[user_id]:
        bot.edit_message_text("❌ Session expired. Please try again.",
                              call.message.chat.id,
                              call.message.message_id,
                              parse_mode='Markdown')
        return

    positions = user_data[user_id]['positions']
    if position_idx >= len(positions):
        bot.edit_message_text("❌ Invalid position selected. Please try again.",
                              call.message.chat.id,
                              call.message.message_id,
                              parse_mode='Markdown')
        return

    position = positions[position_idx]

    # Store position in user data for locking
    user_data[user_id]['lock_position'] = position
    user_data[user_id]['lock_step'] = 'duration'

    # Show lock duration options
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton('30 Days', callback_data='lock_days_30')
    btn2 = types.InlineKeyboardButton('90 Days', callback_data='lock_days_90')
    btn3 = types.InlineKeyboardButton('180 Days',
                                      callback_data='lock_days_180')
    btn4 = types.InlineKeyboardButton('365 Days',
                                      callback_data='lock_days_365')
    btn5 = types.InlineKeyboardButton('Custom',
                                      callback_data='lock_days_custom')
    btn6 = types.InlineKeyboardButton('🔄 Back', callback_data='view_positions')
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6)

    bot.edit_message_text(
        f"🔒 **Lock Position**\n\n"
        f"You're about to lock your **{position.token0_symbol}/{position.token1_symbol}** position.\n\n"
        f"Position ID: `{position.token_id}`\n"
        f"Fee: {position.fee/10000}%\n\n"
        f"Select lock duration:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode='Markdown')


@bot.callback_query_handler(
    func=lambda call: call.data.startswith('lock_days_'))
def lock_position_duration(call):
    user_id = call.from_user.id

    if call.data == 'lock_days_custom':
        # Ask user for custom duration
        bot.edit_message_text(
            "🔒 **Lock Position - Custom Duration**\n\n"
            "Please reply with the number of days you want to lock your position (1-3650):",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown')

        # Set state for handling the custom duration input
        user_data[user_id]['lock_step'] = 'custom_duration'
        return

    # Get duration from callback data
    days = int(call.data.split('_')[-1])

    # Store duration in user data
    user_data[user_id]['lock_duration'] = days

    # Check if UNCX is approved
    wallet = get_user_wallet(user_id)
    web3 = get_web3('polygon')  # Default to polygon
    locker = LiquidityLocker(web3)

    # First check if already approved to avoid showing approval message unnecessarily
    try:
        is_approved = locker.is_approved(wallet['address'])

        if not is_approved:
            # Show approval request
            markup = types.InlineKeyboardMarkup(row_width=1)
            btn1 = types.InlineKeyboardButton('✅ Approve UNCX',
                                              callback_data='approve_uncx')
            btn2 = types.InlineKeyboardButton('❌ Cancel',
                                              callback_data='cancel_lock')
            markup.add(btn1, btn2)

            bot.edit_message_text(
                "🔒 **Lock Position - Approval Required**\n\n"
                "Before locking your position, you need to approve UNCX to access your positions.\n\n"
                "This is a one-time approval that allows the UNCX contract to transfer your position NFT.",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode='Markdown')
        else:
            # Already approved, show lock confirmation
            show_lock_confirmation(call.message, user_id)
    except Exception as e:
        print(f"Error checking approval status: {e}")
        # In case of error, proceed to approval screen to be safe
        markup = types.InlineKeyboardMarkup(row_width=1)
        btn1 = types.InlineKeyboardButton('✅ Approve UNCX',
                                          callback_data='approve_uncx')
        btn2 = types.InlineKeyboardButton('❌ Cancel',
                                          callback_data='cancel_lock')
        markup.add(btn1, btn2)

        bot.edit_message_text(
            "🔒 **Lock Position - Approval Required**\n\n"
            "Before locking your position, you need to approve UNCX to access your positions.\n\n"
            "This is a one-time approval that allows the UNCX contract to transfer your position NFT.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown')


@bot.message_handler(func=lambda message: user_states.get(message.from_user.id)
                     == UserState.LOCK_POSITION)
def handle_lock_position_input(message):
    user_id = message.from_user.id

    if user_id not in user_data or 'lock_step' not in user_data[user_id]:
        bot.send_message(message.chat.id,
                         "❌ Session expired. Please try again.",
                         parse_mode='Markdown')
        return

    step = user_data[user_id]['lock_step']

    if step == 'custom_duration':
        try:
            days = int(message.text)
            if days < 1 or days > 3650:
                bot.send_message(
                    message.chat.id,
                    "❌ Invalid duration. Please enter a number between 1 and 3650 days.",
                    parse_mode='Markdown')
                return

            # Store duration in user data
            user_data[user_id]['lock_duration'] = days

            # Check if UNCX is approved
            wallet = get_user_wallet(user_id)
            web3 = get_web3('polygon')  # Default to polygon
            locker = LiquidityLocker(web3)

            try:
                is_approved = locker.is_approved(wallet['address'])

                if not is_approved:
                    # Show approval request
                    markup = types.InlineKeyboardMarkup(row_width=1)
                    btn1 = types.InlineKeyboardButton(
                        '✅ Approve UNCX', callback_data='approve_uncx')
                    btn2 = types.InlineKeyboardButton(
                        '❌ Cancel', callback_data='cancel_lock')
                    markup.add(btn1, btn2)

                    bot.send_message(
                        message.chat.id,
                        "🔒 **Lock Position - Approval Required**\n\n"
                        "Before locking your position, you need to approve UNCX to access your positions.\n\n"
                        "This is a one-time approval that allows the UNCX contract to transfer your position NFT.",
                        reply_markup=markup,
                        parse_mode='Markdown')
                else:
                    # Already approved, show lock confirmation
                    show_lock_confirmation(message, user_id)
            except Exception as e:
                print(f"Error checking approval status: {e}")
                # In case of error, proceed to approval screen to be safe
                markup = types.InlineKeyboardMarkup(row_width=1)
                btn1 = types.InlineKeyboardButton('✅ Approve UNCX',
                                                  callback_data='approve_uncx')
                btn2 = types.InlineKeyboardButton('❌ Cancel',
                                                  callback_data='cancel_lock')
                markup.add(btn1, btn2)

                bot.send_message(
                    message.chat.id,
                    "🔒 **Lock Position - Approval Required**\n\n"
                    "Before locking your position, you need to approve UNCX to access your positions.\n\n"
                    "This is a one-time approval that allows the UNCX contract to transfer your position NFT.",
                    reply_markup=markup,
                    parse_mode='Markdown')

        except ValueError:
            bot.send_message(
                message.chat.id,
                "❌ Invalid input. Please enter a number for the lock duration in days.",
                parse_mode='Markdown')


def show_lock_confirmation(message, user_id):
    # Get position and duration from user data
    position = user_data[user_id]['lock_position']
    days = user_data[user_id]['lock_duration']

    # Calculate unlock date
    unlock_date = datetime.fromtimestamp(
        int(time.time()) + days * 24 * 60 * 60)
    unlock_date_str = unlock_date.strftime("%Y-%m-%d %H:%M:%S")

    # Get lock fee
    web3 = get_web3('polygon')  # Default to polygon
    locker = LiquidityLocker(web3)
    fee_str, _ = locker.get_lock_fee()

    # Create confirmation markup
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn1 = types.InlineKeyboardButton('✅ Confirm Lock',
                                      callback_data='confirm_lock')
    btn2 = types.InlineKeyboardButton('❌ Cancel', callback_data='cancel_lock')
    markup.add(btn1, btn2)

    # Send confirmation message
    if isinstance(message, types.Message):
        # If called from a message handler
        bot.send_message(
            message.chat.id, f"🔒 **Lock Position - Confirmation**\n\n"
            f"You're about to lock your **{position.token0_symbol}/{position.token1_symbol}** position.\n\n"
            f"Position ID: `{position.token_id}`\n"
            f"Lock Duration: {days} days\n"
            f"Unlock Date: {unlock_date_str}\n"
            f"Lock Fee: {fee_str} MATIC\n\n"
            f"Please confirm to proceed with locking:",
            reply_markup=markup,
            parse_mode='Markdown')
    else:
        # If called from a callback handler
        bot.edit_message_text(
            f"🔒 **Lock Position - Confirmation**\n\n"
            f"You're about to lock your **{position.token0_symbol}/{position.token1_symbol}** position.\n\n"
            f"Position ID: `{position.token_id}`\n"
            f"Lock Duration: {days} days\n"
            f"Unlock Date: {unlock_date_str}\n"
            f"Lock Fee: {fee_str} MATIC\n\n"
            f"Please confirm to proceed with locking:",
            message.chat.id,
            message.message_id,
            reply_markup=markup,
            parse_mode='Markdown')


@bot.callback_query_handler(func=lambda call: call.data == 'approve_uncx')
def approve_uncx(call):
    user_id = call.from_user.id
    wallet = get_user_wallet(user_id)

    if not wallet:
        bot.edit_message_text(
            "❌ No wallet found!\n\nPlease setup your wallet first.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown')
        return

    try:
        # First, update the message to show processing status
        markup = types.InlineKeyboardMarkup(row_width=1)
        btn = types.InlineKeyboardButton('⏳ Approving...',
                                         callback_data='processing')
        markup.add(btn)

        bot.edit_message_text(
            "⏳ **Preparing Approval Transaction**\n\n"
            "Please wait while we prepare your approval transaction...",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown')

        # Initialize web3 and locker
        web3 = get_web3('polygon')  # Default to polygon
        locker = LiquidityLocker(web3)

        # Double-check if already approved to avoid unnecessary transactions
        is_approved = locker.is_approved(wallet['address'])
        if is_approved:
            # If already approved, skip to lock confirmation
            bot.edit_message_text(
                "✅ **Already Approved**\n\n"
                "UNCX is already approved to access your positions.\n\n"
                "Proceeding to lock confirmation...",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown')

            # Short delay to show the message before proceeding
            time.sleep(1)

            # Show lock confirmation
            show_lock_confirmation(call.message, user_id)
            return

        # Get approval transaction
        tx = locker.approve_uncx(wallet['address'])

        if tx == "Already approved":
            # If already approved, show lock confirmation
            show_lock_confirmation(call.message, user_id)
            return

        # Sign and send the transaction
        signed_tx = web3.eth.account.sign_transaction(tx,
                                                      wallet['private_key'])
        tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)

        # Update message with transaction hash
        markup = types.InlineKeyboardMarkup(row_width=1)
        btn = types.InlineKeyboardButton('⏳ Confirming...',
                                         callback_data='processing')
        markup.add(btn)

        # Show transaction sent message
        bot.edit_message_text(
            f"✅ **Approval Transaction Sent**\n\n"
            f"Transaction Hash: `{tx_hash.hex()}`\n\n"
            f"⏳ Waiting for confirmation...",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown')

        try:
            # Wait for transaction receipt with a timeout
            receipt = web3.eth.wait_for_transaction_receipt(tx_hash,
                                                            timeout=60)

            if receipt.status == 1:
                # Transaction successful, show lock confirmation
                bot.edit_message_text(
                    "✅ **Approval Successful**\n\n"
                    "UNCX has been approved to access your positions.\n\n"
                    "Proceeding to lock confirmation...",
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode='Markdown')

                # Short delay to show the message before proceeding
                time.sleep(1)

                # Show lock confirmation
                show_lock_confirmation(call.message, user_id)
            else:
                # Transaction failed
                markup = types.InlineKeyboardMarkup(row_width=1)
                btn = types.InlineKeyboardButton('🔄 Try Again',
                                                 callback_data='approve_uncx')
                markup.add(btn)

                bot.edit_message_text(
                    "❌ **Approval Failed**\n\n"
                    "The approval transaction failed. Please try again.",
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup,
                    parse_mode='Markdown')
        except Exception as timeout_error:
            # Transaction might still be pending
            print(f"Timeout waiting for receipt: {timeout_error}")

            # Create markup with options
            markup = types.InlineKeyboardMarkup(row_width=1)
            btn1 = types.InlineKeyboardButton('🔍 Check Status',
                                              callback_data='check_approval')
            btn2 = types.InlineKeyboardButton('🔄 Try Again',
                                              callback_data='approve_uncx')
            btn3 = types.InlineKeyboardButton('⏩ Continue Anyway',
                                              callback_data='force_continue')
            markup.add(btn1, btn2, btn3)

            # Store transaction hash for later checking
            user_data[user_id]['pending_tx_hash'] = tx_hash.hex()

            bot.edit_message_text(
                f"⚠️ **Transaction Taking Longer Than Expected**\n\n"
                f"Your approval transaction has been submitted but is taking longer than expected to confirm.\n\n"
                f"Transaction Hash: `{tx_hash.hex()}`\n\n"
                f"You can check the status, try again, or continue to the next step if you believe the transaction will succeed.",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode='Markdown')

    except Exception as e:
        print(f"Error approving UNCX: {e}")

        markup = types.InlineKeyboardMarkup(row_width=1)
        btn = types.InlineKeyboardButton('🔄 Try Again',
                                         callback_data='approve_uncx')
        markup.add(btn)

        bot.edit_message_text(
            f"❌ **Error Approving UNCX**\n\n"
            f"Error: {str(e)}\n\n"
            f"Please try again.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown')


# Add a handler for the check_approval callback
@bot.callback_query_handler(func=lambda call: call.data == 'check_approval')
def check_approval_status(call):
    user_id = call.from_user.id

    if user_id not in user_data or 'pending_tx_hash' not in user_data[user_id]:
        bot.edit_message_text(
            "❌ Transaction information not found. Please try approving again.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown')
        return

    tx_hash = user_data[user_id]['pending_tx_hash']

    try:
        # Initialize web3
        web3 = get_web3('polygon')  # Default to polygon

        # Show checking message
        bot.edit_message_text(
            f"🔍 **Checking Transaction Status**\n\n"
            f"Transaction Hash: `{tx_hash}`\n\n"
            f"Please wait...",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown')

        # Try to get the receipt
        receipt = web3.eth.get_transaction_receipt(tx_hash)

        if receipt:
            if receipt.status == 1:
                # Transaction successful
                bot.edit_message_text(
                    "✅ **Approval Successful**\n\n"
                    "UNCX has been approved to access your positions.\n\n"
                    "Proceeding to lock confirmation...",
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode='Markdown')

                # Short delay to show the message before proceeding
                time.sleep(1)

                # Show lock confirmation
                show_lock_confirmation(call.message, user_id)
            else:
                # Transaction failed
                markup = types.InlineKeyboardMarkup(row_width=1)
                btn = types.InlineKeyboardButton('🔄 Try Again',
                                                 callback_data='approve_uncx')
                markup.add(btn)

                bot.edit_message_text(
                    "❌ **Approval Failed**\n\n"
                    "The approval transaction failed. Please try again.",
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup,
                    parse_mode='Markdown')
        else:
            # Transaction still pending
            markup = types.InlineKeyboardMarkup(row_width=1)
            btn1 = types.InlineKeyboardButton('🔍 Check Again',
                                              callback_data='check_approval')
            btn2 = types.InlineKeyboardButton('🔄 Try Again',
                                              callback_data='approve_uncx')
            btn3 = types.InlineKeyboardButton('⏩ Continue Anyway',
                                              callback_data='force_continue')
            markup.add(btn1, btn2, btn3)

            bot.edit_message_text(
                f"⏳ **Transaction Still Pending**\n\n"
                f"Your approval transaction is still being processed by the network.\n\n"
                f"Transaction Hash: `{tx_hash}`\n\n"
                f"You can check again later, try a new transaction, or continue if you believe it will succeed.",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode='Markdown')

    except Exception as e:
        print(f"Error checking transaction status: {e}")

        markup = types.InlineKeyboardMarkup(row_width=1)
        btn1 = types.InlineKeyboardButton('🔍 Check Again',
                                          callback_data='check_approval')
        btn2 = types.InlineKeyboardButton('🔄 Try Again',
                                          callback_data='approve_uncx')
        markup.add(btn1, btn2)

        bot.edit_message_text(
            f"❌ **Error Checking Status**\n\n"
            f"Error: {str(e)}\n\n"
            f"You can try checking again or start a new approval transaction.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown')


# Add a handler for the force_continue callback
@bot.callback_query_handler(func=lambda call: call.data == 'force_continue')
def force_continue_to_lock(call):
    user_id = call.from_user.id

    # Show warning and proceed to lock confirmation
    bot.edit_message_text(
        "⚠️ **Proceeding Without Confirmation**\n\n"
        "You're proceeding without confirmation of the approval transaction.\n"
        "If the approval wasn't successful, the lock transaction will fail.\n\n"
        "Proceeding to lock confirmation...",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown')

    # Short delay to show the message before proceeding
    time.sleep(1)

    # Show lock confirmation
    show_lock_confirmation(call.message, user_id)


@bot.callback_query_handler(func=lambda call: call.data == 'confirm_lock')
def confirm_lock(call):
    user_id = call.from_user.id
    wallet = get_user_wallet(user_id)

    if not wallet:
        bot.edit_message_text(
            "❌ No wallet found!\n\nPlease setup your wallet first.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown')
        return

    if user_id not in user_data or 'lock_position' not in user_data[
            user_id] or 'lock_duration' not in user_data[user_id]:
        bot.edit_message_text("❌ Session expired. Please try again.",
                              call.message.chat.id,
                              call.message.message_id,
                              parse_mode='Markdown')
        return

    position = user_data[user_id]['lock_position']
    days = user_data[user_id]['lock_duration']

    try:
        # First, update the message to show processing status
        markup = types.InlineKeyboardMarkup(row_width=1)
        btn = types.InlineKeyboardButton('⏳ Locking Position...',
                                         callback_data='processing')
        markup.add(btn)

        bot.edit_message_text(
            f"🔒 **Locking Position**\n\n"
            f"Preparing to lock your **{position.token0_symbol}/{position.token1_symbol}** position for {days} days.\n\n"
            f"Position ID: `{position.token_id}`\n\n"
            f"⏳ Please wait while we prepare your transaction...",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown')

        # Initialize web3 and locker
        web3 = get_web3('polygon')  # Default to polygon
        locker = LiquidityLocker(web3)

        # Get lock transaction
        lock_result = locker.lock_position(wallet['address'],
                                           position.token_id, days)

        if not lock_result['success']:
            markup = types.InlineKeyboardMarkup(row_width=1)
            btn = types.InlineKeyboardButton('🔄 Try Again',
                                             callback_data='confirm_lock')
            markup.add(btn)

            bot.edit_message_text(
                f"❌ **Lock Failed**\n\n"
                f"Error: {lock_result['error']}\n\n"
                f"Please try again.",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode='Markdown')
            return

        tx = lock_result['transaction']

        # Sign and send the transaction
        signed_tx = web3.eth.account.sign_transaction(tx,
                                                      wallet['private_key'])
        tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)

        # Update message with transaction hash
        markup = types.InlineKeyboardMarkup(row_width=1)
        btn = types.InlineKeyboardButton('⏳ Confirming...',
                                         callback_data='processing')
        markup.add(btn)

        # Show transaction sent message
        bot.edit_message_text(
            f"✅ **Lock Transaction Sent**\n\n"
            f"Transaction Hash: `{tx_hash.hex()}`\n\n"
            f"⏳ Waiting for confirmation...",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown')

        # Wait for transaction receipt
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt.status == 1:
            # Transaction successful
            markup = types.InlineKeyboardMarkup(row_width=1)
            btn1 = types.InlineKeyboardButton('🔍 View Locked Positions',
                                              callback_data='view_locked')
            btn2 = types.InlineKeyboardButton('🔄 Back to Main Menu',
                                              callback_data='back_to_main')
            markup.add(btn1, btn2)

            # Format unlock date
            unlock_date = datetime.fromtimestamp(lock_result['unlock_date'])
            unlock_date_str = unlock_date.strftime("%Y-%m-%d %H:%M:%S")

            bot.edit_message_text(
                f"🎉 **Position Locked Successfully!**\n\n"
                f"Your **{position.token0_symbol}/{position.token1_symbol}** position has been locked.\n\n"
                f"Position ID: `{position.token_id}`\n"
                f"Lock Duration: {days} days\n"
                f"Unlock Date: {unlock_date_str}\n\n"
                f"Transaction Hash: `{tx_hash.hex()}`",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode='Markdown')
        else:
            # Transaction failed
            markup = types.InlineKeyboardMarkup(row_width=1)
            btn = types.InlineKeyboardButton('🔄 Try Again',
                                             callback_data='confirm_lock')
            markup.add(btn)

            bot.edit_message_text(
                "❌ **Lock Failed**\n\n"
                "The lock transaction failed. Please try again.",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode='Markdown')

    except Exception as e:
        print(f"Error locking position: {e}")

        # Check if it's a known UNCX error
        error_str = str(e)
        if "execution reverted" in error_str and ":" in error_str:
            error_code = error_str.split(":")[-1].strip()
            error_message = locker.interpret_uncx_error(error_code)
        else:
            error_message = str(e)

        markup = types.InlineKeyboardMarkup(row_width=1)
        btn = types.InlineKeyboardButton('🔄 Try Again',
                                         callback_data='confirm_lock')
        markup.add(btn)

        bot.edit_message_text(
            f"❌ **Error Locking Position**\n\n"
            f"Error: {error_message}\n\n"
            f"Please try again.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown')


@bot.callback_query_handler(func=lambda call: call.data == 'cancel_lock')
def cancel_lock(call):
    user_id = call.from_user.id
    user_states[user_id] = UserState.LIQUIDITY_MANAGEMENT

    # Clean up lock data
    if user_id in user_data:
        if 'lock_position' in user_data[user_id]:
            del user_data[user_id]['lock_position']
        if 'lock_duration' in user_data[user_id]:
            del user_data[user_id]['lock_duration']
        if 'lock_step' in user_data[user_id]:
            del user_data[user_id]['lock_step']

    # Return to liquidity management
    manage_liquidity_callback(call)


@bot.callback_query_handler(func=lambda call: call.data == 'change_wallet')
def change_wallet_callback(call):
    user_id = call.from_user.id
    user_states[user_id] = UserState.WALLET_SETUP

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton('🆕 Create New Wallet',
                                      callback_data='create_wallet')
    btn2 = types.InlineKeyboardButton('📥 Import Existing',
                                      callback_data='import_wallet')
    markup.add(btn1, btn2)

    bot.edit_message_text(
        "🔐 **Change Wallet**\n\n"
        "Choose an option to change your wallet:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode='Markdown')


@bot.callback_query_handler(func=lambda call: call.data == 'export_wallet')
def export_wallet_callback(call):
    user_id = call.from_user.id
    wallet = get_user_wallet(user_id)

    if not wallet:
        bot.edit_message_text(
            "❌ **No wallet found!**\n\n"
            "You don't have a wallet configured yet.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown')
        return

    # Create a temporary message with the private key
    private_key_message = bot.send_message(
        call.message.chat.id,
        f"🔑 **Your Private Key:**\n\n"
        f"`{wallet['private_key']}`\n\n"
        f"⚠️ **IMPORTANT:** Save this key securely and delete this message afterward!\n"
        f"Anyone with this key has full control of your wallet.",
        parse_mode='Markdown')
    
    # Create a button to return to settings
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn = types.InlineKeyboardButton('⬅️ Back to Settings', callback_data='back_to_settings')
    markup.add(btn)
    
    bot.edit_message_text(
        "📋 **Wallet Exported**\n\n"
        "Your private key has been sent in a separate message.\n"
        "⚠️ Please save it securely and delete the message afterward.",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode='Markdown')


@bot.callback_query_handler(func=lambda call: call.data == 'back_to_settings')
def back_to_settings_callback(call):
    user_id = call.from_user.id
    wallet = get_user_wallet(user_id)

    if not wallet:
        wallet_status = "❌ No wallet configured"
        wallet_address = "N/A"
    else:
        wallet_status = "✅ Wallet configured"
        wallet_address = f"`{wallet['address'][:10]}...{wallet['address'][-10:]}`"

    markup = types.InlineKeyboardMarkup(row_width=1)
    btn1 = types.InlineKeyboardButton('🔄 Change Wallet',
                                      callback_data='change_wallet')
    btn2 = types.InlineKeyboardButton('📋 Export Wallet',
                                      callback_data='export_wallet')
    btn3 = types.InlineKeyboardButton('🗑️ Delete Data',
                                      callback_data='delete_data')
    markup.add(btn1, btn2, btn3)

    settings_text = f"""
⚙️ **Settings**

**Wallet Status:** {wallet_status}
**Address:** {wallet_address}

**Options:**
    """

    bot.edit_message_text(
        settings_text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode='Markdown')


@bot.callback_query_handler(func=lambda call: call.data == 'delete_data')
def delete_data_callback(call):
    user_id = call.from_user.id
    
    # Create confirmation buttons
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton('✅ Yes, Delete', callback_data='confirm_delete_data')
    btn2 = types.InlineKeyboardButton('❌ No, Cancel', callback_data='back_to_settings')
    markup.add(btn1, btn2)
    
    bot.edit_message_text(
        "🗑️ **Delete Data**\n\n"
        "⚠️ **Warning:** This will delete your wallet configuration and all associated data.\n\n"
        "Are you sure you want to proceed?",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode='Markdown')


@bot.callback_query_handler(func=lambda call: call.data == 'confirm_delete_data')
def confirm_delete_data_callback(call):
    user_id = call.from_user.id
    user_id_str = str(user_id)
    
    try:
        # Delete wallet data
        with open(USERS_FILE, 'r') as f:
            users = json.load(f)
        
        if user_id_str in users:
            del users[user_id_str]
            
            with open(USERS_FILE, 'w') as f:
                json.dump(users, f, indent=4)
        
        # Delete token data
        with open(TOKENS_FILE, 'r') as f:
            tokens = json.load(f)
        
        if user_id_str in tokens:
            del tokens[user_id_str]
            
            with open(TOKENS_FILE, 'w') as f:
                json.dump(tokens, f, indent=4)
        
        # Clear user state
        if user_id in user_states:
            del user_states[user_id]
        
        # Clear user data
        if user_id in user_data:
            del user_data[user_id]
        
        bot.edit_message_text(
            "✅ **Data Deleted**\n\n"
            "Your wallet configuration and associated data have been deleted.\n\n"
            "Use /start to set up a new wallet.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown')
    
    except Exception as e:
        print(f"Error deleting data: {e}")
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        btn = types.InlineKeyboardButton('⬅️ Back to Settings', callback_data='back_to_settings')
        markup.add(btn)
        
        bot.edit_message_text(
            f"❌ **Error Deleting Data**\n\n"
            f"Error: {str(e)}\n\n"
            f"Please try again later.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == '⚓ Renounce Contract')
def renounce_contract_start(message):
    user_id = message.from_user.id

    # Check if user has wallet
    wallet = get_user_wallet(user_id)
    if not wallet:
        bot.send_message(
            message.chat.id,
            "❌ **No wallet found!**\n\nPlease setup your wallet first using the '🔐 Setup Wallet' button.",
            parse_mode='Markdown')
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton('🪙 My Tokens', callback_data='renounce_my_tokens')
    btn2 = types.InlineKeyboardButton('📝 Custom Address', callback_data='renounce_custom_address')
    markup.add(btn1, btn2)

    bot.send_message(
        message.chat.id,
        "⚓ **Contract Renouncement**\n\n"
        "This will permanently renounce your ownership of the contract. "
        "This action CANNOT be undone!\n\n"
        "Choose an option:",
        reply_markup=markup,
        parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == 'renounce_my_tokens')
def select_token_for_renouncement(call):
    user_id = call.from_user.id
    user_id_str = str(user_id)
    
    # Load user's tokens
    user_tokens = []
    try:
        if os.path.exists(TOKENS_FILE):
            with open(TOKENS_FILE, 'r') as f:
                tokens_data = json.load(f)
                if user_id_str in tokens_data:
                    user_tokens = tokens_data[user_id_str]
    except Exception as e:
        print(f"Error loading tokens: {e}")
        
    if not user_tokens:
        bot.edit_message_text(
            "❌ You don't have any deployed tokens.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown')
        return

    # Create inline buttons for each token
    markup = types.InlineKeyboardMarkup(row_width=1)
    for i, token in enumerate(user_tokens):
        network = token.get('network', 'polygon')
        # Use index instead of full address to keep callback data short
        btn = types.InlineKeyboardButton(
            f"{token['token_name']} ({token['token_symbol']}) on {network.capitalize()}",
            callback_data=f"renounce_idx_{i}")
        markup.add(btn)
        
    markup.add(types.InlineKeyboardButton('◀️ Back', callback_data='back_to_renounce_options'))
    
    # Store tokens in user data for later reference by index
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]['tokens_for_renounce'] = user_tokens
    
    bot.edit_message_text(
        "Select a token to renounce ownership:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'renounce_custom_address')
def enter_custom_address(call):
    user_id = call.from_user.id
    user_states[user_id] = UserState.ENTERING_CONTRACT_ADDRESS
    
    bot.edit_message_text(
        "📝 **Enter Contract Address**\n\n"
        "Please enter the contract address you want to renounce ownership of:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown')

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == UserState.ENTERING_CONTRACT_ADDRESS)
def handle_contract_address(message):
    user_id = message.from_user.id
    address = message.text.strip()
    
    # Basic address validation
    if not Web3.is_address(address):
        bot.send_message(
            message.chat.id,
            "❌ Invalid address format. Please enter a valid Ethereum/Polygon contract address.",
            parse_mode='Markdown')
        return
    
    # Store the address in user data
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]['custom_contract_address'] = address
    
    # Select network with shorter callback data
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton('Polygon (MATIC)', callback_data='renounce_net_polygon')
    btn2 = types.InlineKeyboardButton('Ethereum (ETH)', callback_data='renounce_net_ethereum')
    markup.add(btn1, btn2)
    
    bot.send_message(
        message.chat.id,
        "Select the network for this contract:",
        reply_markup=markup)

# Add new handler for token index selection
@bot.callback_query_handler(func=lambda call: call.data.startswith('renounce_idx_'))
def token_index_selected_for_renounce(call):
    user_id = call.from_user.id
    
    # Extract token index from callback data
    token_idx = int(call.data.split('_')[2])
    
    # Get token from user data
    if user_id not in user_data or 'tokens_for_renounce' not in user_data[user_id]:
        bot.edit_message_text(
            "❌ Session expired. Please try again.",
            call.message.chat.id,
            call.message.message_id)
        return
    
    tokens = user_data[user_id]['tokens_for_renounce']
    if token_idx >= len(tokens):
        bot.edit_message_text(
            "❌ Invalid token selection. Please try again.",
            call.message.chat.id,
            call.message.message_id)
        return
    
    token = tokens[token_idx]
    contract_address = token['contract_address']
    network = token.get('network', 'polygon')
    
    # Store in user data for later use
    user_data[user_id]['renounce_contract'] = contract_address
    user_data[user_id]['renounce_network'] = network
    
    # Continue with contract validation and confirmation
    confirm_renouncement_with_data(call, user_id, contract_address, network)

# Add new handler for network selection
@bot.callback_query_handler(func=lambda call: call.data.startswith('renounce_net_'))
def network_selected_for_renounce(call):
    user_id = call.from_user.id
    
    # Extract network from callback data
    network = call.data.split('_')[2]
    
    # Get address from user data
    if user_id not in user_data or 'custom_contract_address' not in user_data[user_id]:
        bot.edit_message_text(
            "❌ Session expired. Please try again.",
            call.message.chat.id,
            call.message.message_id)
        return
    
    contract_address = user_data[user_id]['custom_contract_address']
    
    # Store in user data for later use
    user_data[user_id]['renounce_contract'] = contract_address
    user_data[user_id]['renounce_network'] = network
    
    # Continue with contract validation and confirmation
    confirm_renouncement_with_data(call, user_id, contract_address, network)

# Extract the common confirmation logic to a separate function
def confirm_renouncement_with_data(call, user_id, contract_address, network):
    wallet = get_user_wallet(user_id)
    
    if not wallet:
        bot.edit_message_text(
            "❌ **No wallet found!**\n\nPlease setup your wallet first.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown')
        return
    
    # Get web3 instance
    web3 = get_web3(network)
    
    # Display confirmation with token info
    try:
        # Basic contract validation by checking for token info
        bot.edit_message_text(
            "🔍 Fetching contract details...",
            call.message.chat.id,
            call.message.message_id)
        
        # Create a simple contract instance to check if we can interact with it
        contract = web3.eth.contract(address=contract_address, abi=[
            {"constant": True, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}], "type": "function"},
            {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
            {"constant": True, "inputs": [], "name": "owner", "outputs": [{"name": "", "type": "address"}], "type": "function"}
        ])
        
        # Try to get token name and symbol
        try:
            token_name = contract.functions.name().call()
            token_symbol = contract.functions.symbol().call()
        except Exception as e:
            bot.edit_message_text(
                f"❌ Error: Could not read token information from contract. This may not be a valid token contract.\n\nError: {str(e)}",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown')
            return
        
        # Try to get owner
        try:
            owner = contract.functions.owner().call()
            is_owner = owner.lower() == wallet['address'].lower()
        except Exception as e:
            bot.edit_message_text(
                f"❌ Error: Could not read ownership information from contract. This contract may not have an owner function.\n\nError: {str(e)}",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown')
            return
            
        if not is_owner:
            bot.edit_message_text(
                f"❌ You are not the owner of this contract.\n\n"
                f"Contract Owner: `{owner}`\n"
                f"Your address: `{wallet['address']}`",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown')
            return
        
        # Show confirmation dialog
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_confirm = types.InlineKeyboardButton('✅ Yes, Renounce Ownership', callback_data='confirm_renounce')
        btn_cancel = types.InlineKeyboardButton('❌ No, Cancel', callback_data='cancel_renounce')
        markup.add(btn_confirm, btn_cancel)
        
        bot.edit_message_text(
            f"⚠️ **FINAL WARNING** ⚠️\n\n"
            f"You are about to renounce ownership of:\n"
            f"**Token:** {token_name} ({token_symbol})\n"
            f"**Address:** `{contract_address}`\n"
            f"**Network:** {network.capitalize()}\n\n"
            f"**This action CANNOT be undone!**\n"
            f"Once you renounce ownership, you will no longer be able to:\n"
            f"• Mint new tokens\n"
            f"• Change token settings\n"
            f"• Set up special rules\n"
            f"• Recover tokens or ETH sent to the contract\n\n"
            f"Are you absolutely sure you want to continue?",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown')
    except Exception as e:
        bot.edit_message_text(
            f"❌ Error checking contract: {str(e)}",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_renounce_options')
def back_to_renounce_options(call):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton('🪙 My Tokens', callback_data='renounce_my_tokens')
    btn2 = types.InlineKeyboardButton('📝 Custom Address', callback_data='renounce_custom_address')
    markup.add(btn1, btn2)

    bot.edit_message_text(
        "⚓ **Contract Renouncement**\n\n"
        "This will permanently renounce your ownership of the contract. "
        "This action CANNOT be undone!\n\n"
        "Choose an option:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == 'confirm_renounce')
def execute_renouncement(call):
    user_id = call.from_user.id
    
    if user_id not in user_data or 'renounce_contract' not in user_data[user_id]:
        bot.edit_message_text(
            "❌ Error: Contract information not found. Please start over.",
            call.message.chat.id,
            call.message.message_id)
        return
        
    contract_address = user_data[user_id]['renounce_contract']
    network = user_data[user_id]['renounce_network']
    
    # Show processing message
    bot.edit_message_text(
        "⏳ Processing renouncement transaction...",
        call.message.chat.id,
        call.message.message_id)
    
    # Call the renouncement function in a separate thread
    def execute_renouncement_thread():
        try:
            success, result = renounce_contract_ownership(user_id, contract_address, network)
            
            if success:
                # Transaction was successful
                explorer_url = result['explorer_url']
                tx_hash = result['tx_hash']
                
                bot.edit_message_text(
                    f"✅ **Ownership Renounced Successfully!**\n\n"
                    f"Contract: `{contract_address}`\n"
                    f"Transaction Hash: `{tx_hash}`\n\n"
                    f"[View on Blockchain Explorer]({explorer_url})",
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode='Markdown',
                    disable_web_page_preview=True)
            else:
                # Error occurred
                bot.edit_message_text(
                    f"❌ **Renouncement Failed**\n\n"
                    f"Error: {result}",
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode='Markdown')
        except Exception as e:
            bot.edit_message_text(
                f"❌ **Renouncement Failed**\n\n"
                f"Error: {str(e)}",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown')
    
    # Execute in a separate thread
    import threading
    thread = threading.Thread(target=execute_renouncement_thread)
    thread.start()

@bot.callback_query_handler(func=lambda call: call.data == 'cancel_renounce')
def cancel_renouncement(call):
    user_id = call.from_user.id
    
    # Clear renouncement data
    if user_id in user_data:
        if 'renounce_contract' in user_data[user_id]:
            del user_data[user_id]['renounce_contract']
        if 'renounce_network' in user_data[user_id]:
            del user_data[user_id]['renounce_network']
    
    # Return to main menu
    bot.edit_message_text(
        "✅ Contract renouncement cancelled.",
        call.message.chat.id,
        call.message.message_id)

@bot.message_handler(commands=['renounce'])
def renounce_command(message):
    # Simply call the existing renounce_contract_start function
    renounce_contract_start(message)

@bot.callback_query_handler(func=lambda call: call.data == 'tax_wallet_default')
def handle_default_tax_wallet(call):
    user_id = call.from_user.id
    
    # Use the user's wallet address as the tax wallet
    user_wallet = get_user_wallet(user_id)
    if user_wallet:
        user_data[user_id]['tax_wallet'] = user_wallet['address']
    else:
        # If no wallet is set up, we'll use the deployer address (handled in contract)
        user_data[user_id]['tax_wallet'] = ''
    
    # Show network selection
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton('🟣 Polygon', callback_data='deploy_polygon')
    btn2 = types.InlineKeyboardButton('🔷 Ethereum', callback_data='deploy_ethereum')
    markup.add(btn1, btn2)
    
    # Create summary
    features = user_data[user_id]['features']
    feature_names = [
        "Burnable", "Mintable", "Pausable", "Access Control", "Flash Minting"
    ]
    enabled_features = [
        name for name, enabled in zip(feature_names, features)
        if enabled
    ]
    
    tax_wallet_display = user_data[user_id]['tax_wallet'] if user_data[user_id]['tax_wallet'] else "Deployer's address"
    
    summary = f"""
✅ **Token Configuration Complete!**

**Token Details:**
• Name: {user_data[user_id]['token_name']}
• Symbol: {user_data[user_id]['token_symbol']}
• Supply: {user_data[user_id]['total_supply']:,}
• Decimals: {user_data[user_id]['decimals']}
• Buy Tax: {user_data[user_id]['buy_tax']/100}%
• Sell Tax: {user_data[user_id]['sell_tax']/100}%
• Tax Wallet: {tax_wallet_display}

**Features:** {', '.join(enabled_features) if enabled_features else 'None'}

**Select deployment network:**
    """
    
    bot.edit_message_text(
        summary,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == UserState.ENTERING_TAX_WALLET)
def handle_tax_wallet_input(message):
    user_id = message.from_user.id
    
    # Check if the input is a valid Ethereum address
    address = message.text.strip()
    if not address.startswith('0x') or len(address) != 42:
        bot.send_message(
            message.chat.id,
            "❌ Invalid Ethereum address. Please enter a valid address or click 'Use my wallet address'.",
            parse_mode='Markdown')
        return
    
    # Store the tax wallet address
    user_data[user_id]['tax_wallet'] = address
    
    # Show network selection
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton('🟣 Polygon', callback_data='deploy_polygon')
    btn2 = types.InlineKeyboardButton('🔷 Ethereum', callback_data='deploy_ethereum')
    markup.add(btn1, btn2)
    
    # Create summary
    features = user_data[user_id]['features']
    feature_names = [
        "Burnable", "Mintable", "Pausable", "Access Control", "Flash Minting"
    ]
    enabled_features = [
        name for name, enabled in zip(feature_names, features)
        if enabled
    ]
    
    summary = f"""
✅ **Token Configuration Complete!**

**Token Details:**
• Name: {user_data[user_id]['token_name']}
• Symbol: {user_data[user_id]['token_symbol']}
• Supply: {user_data[user_id]['total_supply']:,}
• Decimals: {user_data[user_id]['decimals']}
• Buy Tax: {user_data[user_id]['buy_tax']/100}%
• Sell Tax: {user_data[user_id]['sell_tax']/100}%
• Tax Wallet: {address}

**Features:** {', '.join(enabled_features) if enabled_features else 'None'}

**Select deployment network:**
    """
    
    bot.send_message(
        message.chat.id,
        summary,
        reply_markup=markup,
        parse_mode='Markdown'
    )

