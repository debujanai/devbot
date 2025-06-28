import json
import os
from datetime import datetime
from config import DATA_DIR, USERS_FILE, TOKENS_FILE, POOLS_FILE

# Initialize data storage
def init_data_storage():
    # Create data directory if it doesn't exist
    os.makedirs(DATA_DIR, exist_ok=True)

    # Initialize users data
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w') as f:
            json.dump({}, f, indent=4)
    else:
        # Make sure it's valid JSON
        try:
            with open(USERS_FILE, 'r') as f:
                json.load(f)
        except json.JSONDecodeError:
            # If corrupted, create a new empty file
            with open(USERS_FILE, 'w') as f:
                json.dump({}, f, indent=4)

    # Initialize tokens data
    if not os.path.exists(TOKENS_FILE):
        with open(TOKENS_FILE, 'w') as f:
            json.dump({}, f, indent=4)
    else:
        # Make sure it's valid JSON
        try:
            with open(TOKENS_FILE, 'r') as f:
                json.load(f)
        except json.JSONDecodeError:
            # If corrupted, create a new empty file
            with open(TOKENS_FILE, 'w') as f:
                json.dump({}, f, indent=4)

    # Initialize pools data
    if not os.path.exists(POOLS_FILE):
        with open(POOLS_FILE, 'w') as f:
            json.dump({}, f, indent=4)
    else:
        # Make sure it's valid JSON
        try:
            with open(POOLS_FILE, 'r') as f:
                json.load(f)
        except json.JSONDecodeError:
            # If corrupted, create a new empty file
            with open(POOLS_FILE, 'w') as f:
                json.dump({}, f, indent=4)

def save_user_wallet(user_id, username, wallet_data):
    user_id = str(user_id)  # Convert to string for JSON keys

    try:
        # Ensure file exists
        if not os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'w') as f:
                json.dump({}, f, indent=4)

        # Read current data
        try:
            with open(USERS_FILE, 'r') as f:
                users = json.load(f)
        except json.JSONDecodeError:
            # If file is corrupted, start fresh
            users = {}

        # Update data
        users[user_id] = {
            'username': username,
            'wallet_address': wallet_data['address'],
            'private_key': wallet_data['private_key'],
            'created_at': datetime.now().isoformat()
        }

        # Write data back
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=4)

        return True
    except Exception as e:
        print(f"Error saving wallet: {str(e)}")
        return False

def get_user_wallet(user_id):
    user_id = str(user_id)  # Convert to string for JSON keys

    try:
        with open(USERS_FILE, 'r') as f:
            users = json.load(f)

        if user_id in users:
            return {
                'address': users[user_id]['wallet_address'],
                'private_key': users[user_id]['private_key']
            }
        return None
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        print(f"Error reading wallet data: {str(e)}")
        # Initialize the file if it doesn't exist
        if isinstance(e, FileNotFoundError):
            with open(USERS_FILE, 'w') as f:
                json.dump({}, f, indent=4)
    return None

def save_token_to_db(user_id, token_data, contract_address, network):
    user_id = str(user_id)  # Convert to string for JSON keys

    with open(TOKENS_FILE, 'r') as f:
        tokens = json.load(f)

    if user_id not in tokens:
        tokens[user_id] = []

    tokens[user_id].append({
        'token_name': token_data['name'],
        'token_symbol': token_data['symbol'],
        'contract_address': contract_address,
        'total_supply': token_data['total_supply'],
        'buy_tax': token_data['buy_tax'],
        'sell_tax': token_data['sell_tax'],
        'tax_wallet': token_data.get('tax_wallet', ''),
        'features': token_data['features'],
        'network': network,
        'created_at': datetime.now().isoformat()
    })

    with open(TOKENS_FILE, 'w') as f:
        json.dump(tokens, f, indent=4)

def save_pool_to_db(user_id, token_address, pool_address, liquidity_data, network):
    user_id = str(user_id)  # Convert to string for JSON keys

    with open(POOLS_FILE, 'r') as f:
        pools = json.load(f)

    if user_id not in pools:
        pools[user_id] = []

    pools[user_id].append({
        'token_address': token_address,
        'pool_address': pool_address,
        'liquidity_amount': liquidity_data,
        'network': network,
        'created_at': datetime.now().isoformat()
    })

    with open(POOLS_FILE, 'w') as f:
        json.dump(pools, f, indent=4) 