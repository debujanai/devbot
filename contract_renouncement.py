from web3 import Web3
import json
from telebot import types
from wallet import get_web3, sign_and_send_transaction, wait_for_transaction_receipt, get_explorer_url
from storage import get_user_wallet, save_token_to_db

# Ownership Renouncement ABI snippet - for the renounceOwnership function
OWNERSHIP_ABI = [
    {
        "constant": False,
        "inputs": [],
        "name": "renounceOwnership",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "owner",
        "outputs": [{"name": "", "type": "address"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "name",
        "outputs": [{"name": "", "type": "string"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    }
]

def check_contract_ownership(web3, contract_address, wallet_address):
    """Check if the user is the owner of the contract"""
    try:
        contract = web3.eth.contract(address=contract_address, abi=OWNERSHIP_ABI)
        owner = contract.functions.owner().call()
        return owner.lower() == wallet_address.lower()
    except Exception as e:
        print(f"Error checking ownership: {e}")
        # If there's an error, it might be because the contract doesn't have an owner function
        # In that case, we return False
        return False

def get_token_info(web3, contract_address, wallet_address):
    """Get basic token information"""
    try:
        contract = web3.eth.contract(address=contract_address, abi=OWNERSHIP_ABI)
        
        # Get token info
        token_info = {}
        
        try:
            token_info['name'] = contract.functions.name().call()
        except:
            token_info['name'] = "Unknown Token"
            
        try:
            token_info['symbol'] = contract.functions.symbol().call()
        except:
            token_info['symbol'] = "???"
            
        try:
            balance = contract.functions.balanceOf(wallet_address).call()
            token_info['balance'] = balance
        except:
            token_info['balance'] = 0
            
        try:
            token_info['owner'] = contract.functions.owner().call()
            token_info['is_owner'] = (token_info['owner'].lower() == wallet_address.lower())
        except:
            token_info['owner'] = None
            token_info['is_owner'] = False
            
        return token_info
    except Exception as e:
        print(f"Error getting token info: {e}")
        return {'name': 'Unknown', 'symbol': '???', 'balance': 0, 'owner': None, 'is_owner': False}

def renounce_contract_ownership(user_id, contract_address, network='polygon'):
    """Renounce ownership of a contract"""
    try:
        print(f"Starting contract renouncement process for {contract_address} on {network}")
        web3 = get_web3(network)
        user_wallet = get_user_wallet(user_id)
        
        if not user_wallet:
            return False, "No wallet found for user"
        
        # Check if user is the owner of the contract
        print(f"Checking ownership for {user_wallet['address']}")
        is_owner = check_contract_ownership(web3, contract_address, user_wallet['address'])
        if not is_owner:
            return False, "You are not the owner of this contract"
        
        print("Ownership confirmed, preparing transaction")
        # Create contract instance
        contract = web3.eth.contract(address=contract_address, abi=OWNERSHIP_ABI)
        
        # Build the transaction
        nonce = web3.eth.get_transaction_count(user_wallet['address'])
        gas_price = web3.eth.gas_price
        
        print(f"Using nonce: {nonce}, gas price: {gas_price}")
        
        # Get the transaction data
        try:
            tx_data = contract.functions.renounceOwnership().build_transaction({
                'chainId': web3.eth.chain_id,
                'gas': 0, 
                'gasPrice': 0, 
                'nonce': 0
            })['data']
            print(f"Transaction data generated: {tx_data[:10]}...")
        except Exception as e:
            print(f"Error generating transaction data: {e}")
            return False, f"Failed to generate transaction data: {str(e)}"
        
        # Prepare the transaction
        tx = {
            'from': user_wallet['address'],
            'to': contract_address,
            'gas': 200000,  # Gas limit
            'gasPrice': gas_price,
            'nonce': nonce,
            'data': tx_data
        }
        
        print("Signing and sending transaction...")
        # Sign and send the transaction
        try:
            tx_hash = sign_and_send_transaction(web3, tx, user_wallet['private_key'])
            print(f"Transaction sent with hash: {tx_hash.hex()}")
        except Exception as e:
            print(f"Error sending transaction: {e}")
            return False, f"Failed to send transaction: {str(e)}"
        
        print("Waiting for transaction receipt...")
        # Wait for the transaction to be mined
        try:
            receipt = wait_for_transaction_receipt(web3, tx_hash)
            print(f"Receipt received: status={receipt.status}")
        except Exception as e:
            print(f"Error getting receipt: {e}")
            return False, f"Transaction sent but failed to get receipt: {str(e)}"
        
        if receipt.status == 1:  # Transaction successful
            explorer_url = get_explorer_url(contract_address, network)
            print(f"Transaction successful! Explorer URL: {explorer_url}")
            return True, {
                'message': "Ownership successfully renounced!",
                'tx_hash': tx_hash.hex(),
                'explorer_url': explorer_url,
                'contract_address': contract_address
            }
        else:
            print("Transaction failed according to receipt status")
            return False, "Transaction failed"
        
    except Exception as e:
        print(f"Renouncement error: {e}")
        return False, str(e) 