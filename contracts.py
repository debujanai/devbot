import solcx
from web3 import Web3
import time

from wallet import get_web3, sign_and_send_transaction, wait_for_transaction_receipt
from storage import get_user_wallet, save_token_to_db
from config import ERC20_BYTECODE
from contract_bridge import deploy_contract_with_js

# Token deployment
def deploy_token(user_id, token_data, network='polygon'):
    try:
        web3 = get_web3(network)
        user_wallet = get_user_wallet(user_id)

        if not user_wallet:
            return None, "No wallet found for user"

        # Get token parameters
        token_name = token_data['name']
        token_symbol = token_data['symbol']
        total_supply = token_data['total_supply']
        decimals = token_data['decimals']
        buy_tax = token_data['buy_tax']
        sell_tax = token_data['sell_tax']
        features = token_data['features']

        # Get RPC URL for the network
        rpc_url = web3.provider.endpoint_uri

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
            return None, f"Insufficient balance. You need at least {transaction_cost_eth} {network.upper()} for gas fees. Current balance: {current_balance_eth} {network.upper()}"

        # Create deployment data for review
        deployment_details = {
            'token_name': token_name,
            'token_symbol': token_symbol,
            'total_supply': total_supply,
            'decimals': decimals,
            'buy_tax': buy_tax / 100,  # Convert back to percentage
            'sell_tax': sell_tax / 100,  # Convert back to percentage
            'features': features,
            'gas_price': web3.from_wei(gas_price, 'gwei'),
            'gas_limit': gas_limit,
            'transaction_cost': transaction_cost_eth,
            'current_balance': current_balance_eth,
            'network': network,
            'from_address': user_wallet['address']
        }

        # Use the JavaScript bridge to deploy the contract
        print(f"Deploying token {token_name} using JavaScript bridge...")
        deployment_result = deploy_contract_with_js(
            token_data,
            user_wallet['private_key'],
            rpc_url
        )

        if not deployment_result.get('success', False):
            error_message = deployment_result.get('error', 'Unknown deployment error')
            print(f"Deployment failed: {error_message}")
            return None, error_message

        # Extract contract address and transaction hash
        if 'deployedContract' in deployment_result:
            # Standard successful response
            contract_address = deployment_result['deployedContract']['address']
            tx_hash = deployment_result['deployedContract']['txHash']
        elif 'contractAddress' in deployment_result:
            # Fallback response when JSON parsing failed but deployment succeeded
            contract_address = deployment_result['contractAddress']
            tx_hash = "N/A"  # We don't have the tx hash in this case
        else:
            print("Deployment response doesn't contain contract address")
            return None, "Deployment response doesn't contain contract address"

        print(f"Contract deployed at: {contract_address}")

        # Save token to database
        save_token_to_db(user_id, token_data, contract_address, network)

        # Add transaction details to deployment details
        deployment_details['tx_hash'] = tx_hash
        deployment_details['contract_address'] = contract_address
        
        # Add ABI if available
        if 'abi' in deployment_result:
            deployment_details['abi'] = deployment_result['abi']

        return contract_address, deployment_details

    except Exception as e:
        print(f"Deployment error: {e}")
        return None, str(e) 