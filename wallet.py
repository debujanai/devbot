from eth_account import Account
from web3 import Web3
from config import POLYGON_RPC, ETHEREUM_RPC

# Web3 setup
def get_web3(network='polygon'):
    if network == 'polygon':
        return Web3(Web3.HTTPProvider(POLYGON_RPC))
    else:
        return Web3(Web3.HTTPProvider(ETHEREUM_RPC))

# Wallet creation
def create_wallet():
    account = Account.create()
    return {'address': account.address, 'private_key': account.key.hex()}

# Create a fully-compatible transaction signing function
def sign_and_send_transaction(web3, transaction, private_key):
    """Sign and send a transaction in a way that works with any Web3.py version"""
    print("Using basic transaction signing method")

    # Import libraries directly here to avoid version conflicts
    import eth_account
    import eth_keys
    from eth_utils import to_bytes, keccak, to_hex

    # Create the account directly using the private key
    if not private_key.startswith('0x'):
        private_key = '0x' + private_key

    # Get the private key object
    private_key_bytes = to_bytes(hexstr=private_key)

    # Create an eth_account account
    acct = eth_account.Account.from_key(private_key_bytes)
    print(f"Account created: {acct.address}")

    # Add chainId to the transaction for replay protection (EIP-155)
    if 'chainId' not in transaction:
        # Get chainId from the network
        try:
            chain_id = web3.eth.chain_id
            print(f"Using chain_id: {chain_id}")
            transaction['chainId'] = chain_id
        except Exception as e:
            print(f"Could not get chain_id: {e}")
            # Default chainIds: Ethereum = 1, Polygon = 137
            if web3.provider.endpoint_uri.lower().find('polygon') > -1:
                transaction['chainId'] = 137
                print("Using default chainId for Polygon: 137")
            else:
                transaction['chainId'] = 1
                print("Using default chainId for Ethereum: 1")

    # Sign the transaction manually
    signed = acct.sign_transaction(transaction)
    print("Transaction signed")

    # Extract the raw transaction - try multiple approaches
    raw_tx = None

    # Try all possible ways to get the rawTransaction
    if hasattr(signed, 'rawTransaction'):
        raw_tx = signed.rawTransaction
        print("Got rawTransaction as attribute")
    elif isinstance(signed, dict) and 'rawTransaction' in signed:
        raw_tx = signed['rawTransaction']
        print("Got rawTransaction from dict")
    elif hasattr(signed, 'raw_transaction'):
        raw_tx = signed.raw_transaction
        print("Got raw_transaction as attribute")
    elif isinstance(signed, dict) and 'raw_transaction' in signed:
        raw_tx = signed['raw_transaction']
        print("Got raw_transaction from dict")

    if not raw_tx:
        # As a last resort, print everything we can about the signed transaction
        print(f"Signed transaction: {signed}")
        if isinstance(signed, dict):
            print(f"Dict keys: {signed.keys()}")
        print(f"Attributes: {dir(signed)}")
        raise Exception("Could not extract raw transaction data")

    # Send the raw transaction - try multiple approaches
    try:
        print("Sending transaction using send_raw_transaction")
        tx_hash = web3.eth.send_raw_transaction(raw_tx)
        print(f"Transaction hash: {tx_hash.hex()}")
        return tx_hash
    except Exception as e:
        print(f"Error sending transaction: {e}")
        raise Exception(f"Failed to send transaction: {e}")

# Modified wait_for_receipt function
def wait_for_transaction_receipt(web3, tx_hash, timeout=120):
    """Wait for transaction receipt in a way that works with any Web3.py version"""
    print(f"Waiting for receipt for tx: {tx_hash.hex()}")

    try:
        print("Using wait_for_transaction_receipt")
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
    except Exception as e:
        print(f"First receipt method failed: {e}")
        try:
            print("Trying waitForTransactionReceipt")
            receipt = web3.eth.waitForTransactionReceipt(tx_hash, timeout=timeout)
        except Exception as e2:
            print(f"Second receipt method failed: {e2}")
            # As a last fallback, poll manually
            print("Falling back to manual polling")
            import time
            start_time = time.time()
            while time.time() < start_time + timeout:
                try:
                    receipt = web3.eth.getTransactionReceipt(tx_hash)
                    if receipt:
                        return receipt
                except Exception:
                    pass
                time.sleep(2)
            raise Exception("Timeout waiting for transaction receipt")

    print("Got transaction receipt")
    return receipt

# Utility functions
def get_explorer_url(address, network):
    if network == 'polygon':
        return f"https://polygonscan.com/address/{address}"
    else:
        return f"https://etherscan.io/address/{address}" 