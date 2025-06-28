import math
import time
from web3 import Web3

from wallet import get_web3, sign_and_send_transaction, wait_for_transaction_receipt
from storage import get_user_wallet, save_pool_to_db
from config import POLYGON_ADDRESSES, UNISWAP_V3_FACTORY_ABI, ERC20_ABI, POSITION_MANAGER_WITH_POOL_CREATE_ABI

# Constants for tick math (same as in TypeScript code)
TICK_MATH = {
    'MIN_TICK': -887272,
    'MAX_TICK': 887272
}

# Get tick spacing for a fee tier
def get_tick_spacing(fee):
    if fee == 100:  # 0.01%
        return 1
    elif fee == 500:  # 0.05%
        return 10
    elif fee == 3000:  # 0.3%
        return 60
    elif fee == 10000:  # 1%
        return 200
    else:
        return 60  # Default to 0.3% fee tier

# Calculate ticks based on fee tier
def calculate_ticks(fee):
    tick_spacing = get_tick_spacing(fee)
    # Min tick rounded to the nearest multiple of tickSpacing for the lower end
    min_tick = math.ceil(TICK_MATH['MIN_TICK'] / tick_spacing) * tick_spacing
    # Max tick rounded to the nearest multiple of tickSpacing for the upper end
    max_tick = math.floor(TICK_MATH['MAX_TICK'] / tick_spacing) * tick_spacing
    return min_tick, max_tick

# Calculate sqrt price for Uniswap V3 pool initialization
def calculate_sqrt_price_x96(price):
    # price = token1/token0
    sqrt_price = math.sqrt(price)
    # Multiply by 2^96
    return int(sqrt_price * (2 ** 96))

# Uniswap V3 pool creation with transaction details - checks if pool exists and calculates costs
def create_uniswap_pool(user_id, token_address, initial_liquidity, network='polygon'):
    try:
        web3 = get_web3(network)
        user_wallet = get_user_wallet(user_id)

        if not user_wallet:
            return None, "No wallet found for user"

        # Get network-specific addresses
        if network == 'polygon':
            factory_address = POLYGON_ADDRESSES['UNISWAP_V3_FACTORY']
            weth_address = POLYGON_ADDRESSES['WMATIC']
            position_manager_address = POLYGON_ADDRESSES['UNISWAP_V3_POSITION_MANAGER']
        else:  # ethereum
            # Would use Ethereum addresses in a full implementation
            factory_address = POLYGON_ADDRESSES['UNISWAP_V3_FACTORY']
            weth_address = POLYGON_ADDRESSES['WMATIC']
            position_manager_address = POLYGON_ADDRESSES['UNISWAP_V3_POSITION_MANAGER']

        # Get contract instances
        factory_contract = web3.eth.contract(address=factory_address, abi=UNISWAP_V3_FACTORY_ABI)
        token_contract = web3.eth.contract(address=token_address, abi=ERC20_ABI)
        position_manager_contract = web3.eth.contract(address=position_manager_address, abi=POSITION_MANAGER_WITH_POOL_CREATE_ABI)

        # Calculate estimated gas for pool creation
        gas_price = web3.eth.gas_price
        gas_limit = 5000000  # Estimated gas limit for pool creation and liquidity addition

        # Calculate the total transaction cost in ETH/MATIC
        transaction_cost_wei = gas_price * gas_limit
        transaction_cost_eth = float(web3.from_wei(transaction_cost_wei, 'ether'))

        # Get current balance
        current_balance_wei = web3.eth.get_balance(user_wallet['address'])
        current_balance_eth = float(web3.from_wei(current_balance_wei, 'ether'))

        # Convert liquidity amounts to float to ensure consistent types
        token_amount = float(initial_liquidity['token_amount'])
        eth_amount = float(initial_liquidity['eth_amount'])

        # Check if user has enough balance for gas
        if current_balance_wei < transaction_cost_wei:
            return None, f"Insufficient balance. You need at least {transaction_cost_eth} {network.upper()} for gas fees. Current balance: {current_balance_eth} {network.upper()}"

        # Calculate total needed (gas + liquidity)
        total_needed_eth = transaction_cost_eth + eth_amount

        # Check if user has enough balance for gas + liquidity
        if current_balance_eth < total_needed_eth:
            return None, f"Insufficient balance. You need {eth_amount} {network.upper()} for liquidity plus {transaction_cost_eth} {network.upper()} for gas. Current balance: {current_balance_eth} {network.upper()}"

        # Convert amounts to wei
        token_amount_wei = web3.to_wei(token_amount, 'ether')
        eth_amount_wei = web3.to_wei(eth_amount, 'ether')

        # Determine token0 and token1 (tokens must be sorted by address)
        # Sort token addresses
        if token_address.lower() < weth_address.lower():
            token0 = token_address
            token1 = weth_address
            amount0_desired = token_amount_wei
            amount1_desired = eth_amount_wei
        else:
            token0 = weth_address
            token1 = token_address
            amount0_desired = eth_amount_wei
            amount1_desired = token_amount_wei

        # Use 0.3% fee tier (3000)
        fee = 3000

        # Check if pool already exists
        existing_pool = factory_contract.functions.getPool(token0, token1, fee).call()
        pool_exists = existing_pool != '0x0000000000000000000000000000000000000000'
        
        print(f"Pool exists: {pool_exists}, address: {existing_pool}")

        # Prepare transaction details for review
        pool_details = {
            'token_address': token_address,
            'pool_address': existing_pool if pool_exists else None,
            'token_amount': token_amount,
            'eth_amount': eth_amount,
            'gas_price': float(web3.from_wei(gas_price, 'gwei')),
            'gas_limit': gas_limit,
            'transaction_cost': transaction_cost_eth,
            'total_cost': total_needed_eth,
            'current_balance': current_balance_eth,
            'network': network,
            'from_address': user_wallet['address'],
            'pool_exists': pool_exists
        }

        # Save pool to database (preliminary record)
        save_pool_to_db(user_id, token_address, existing_pool if pool_exists else None, 
                      {'token_amount': token_amount, 'eth_amount': eth_amount}, network)

        return existing_pool if pool_exists else None, pool_details
    except Exception as e:
        print(f"Pool creation error: {e}")
        return None, str(e)

# Execute pool creation and add liquidity - actually creates the pool and adds liquidity
def execute_pool_creation(user_id, token_address, liquidity_data, network='polygon'):
    try:
        web3 = get_web3(network)
        user_wallet = get_user_wallet(user_id)
        currency = "MATIC" if network == 'polygon' else "ETH"

        if not user_wallet:
            return {'status': 'failed', 'error': "No wallet found for user"}

        print(f"Token address: {token_address}")
        print(f"Adding: {liquidity_data['token_amount']} tokens and {liquidity_data['eth_amount']} {currency}")

        # Get network-specific addresses
        if network == 'polygon':
            position_manager_address = POLYGON_ADDRESSES['UNISWAP_V3_POSITION_MANAGER']
            weth_address = POLYGON_ADDRESSES['WMATIC']
            factory_address = POLYGON_ADDRESSES['UNISWAP_V3_FACTORY']
        else:
            position_manager_address = POLYGON_ADDRESSES['UNISWAP_V3_POSITION_MANAGER']
            weth_address = POLYGON_ADDRESSES['WMATIC']
            factory_address = POLYGON_ADDRESSES['UNISWAP_V3_FACTORY']

        # Create contract instances
        factory_contract = web3.eth.contract(address=factory_address, abi=UNISWAP_V3_FACTORY_ABI)
        token_contract = web3.eth.contract(address=token_address, abi=ERC20_ABI)
        position_manager_contract = web3.eth.contract(address=position_manager_address, abi=POSITION_MANAGER_WITH_POOL_CREATE_ABI)

        # Use 0.3% fee tier
        fee = 3000

        # Convert liquidity amounts to wei
        token_amount = float(liquidity_data['token_amount'])
        eth_amount = float(liquidity_data['eth_amount'])
        token_amount_wei = web3.to_wei(token_amount, 'ether')
        eth_amount_wei = web3.to_wei(eth_amount, 'ether')

        # Determine token0 and token1 (tokens must be sorted by address)
        if token_address.lower() < weth_address.lower():
            token0 = token_address
            token1 = weth_address
            amount0_desired = token_amount_wei
            amount1_desired = eth_amount_wei
            is_token0 = True
        else:
            token0 = weth_address
            token1 = token_address
            amount0_desired = eth_amount_wei
            amount1_desired = token_amount_wei
            is_token0 = False

        print(f"Token0: {token0}")
        print(f"Token1: {token1}")
        print(f"Is token0: {is_token0}")

        # STEP 1: Token Approval (similar to TypeScript code)
        # Get fresh nonce
        nonce = web3.eth.get_transaction_count(user_wallet['address'])
        print(f"Starting with nonce: {nonce}")

        # Check current allowance
        allowance = token_contract.functions.allowance(
            user_wallet['address'], 
            position_manager_address
        ).call()

        print(f"Current allowance: {allowance}, needed: {token_amount_wei}")

        # Only approve if needed
        if allowance < token_amount_wei:
            print('Approving token for position manager...')
            approve_tx = token_contract.functions.approve(
                position_manager_address,
                2 * token_amount_wei  # Double for safety
            ).build_transaction({
                'chainId': web3.eth.chain_id,
                'gas': 200000,
                'gasPrice': web3.eth.gas_price,
                'nonce': nonce,
                'from': user_wallet['address']
            })

            approve_tx_hash = sign_and_send_transaction(web3, approve_tx, user_wallet['private_key'])
            approve_receipt = wait_for_transaction_receipt(web3, approve_tx_hash)
            print(f"Token approval tx hash: {approve_tx_hash.hex()}, status: {approve_receipt.status}")
            nonce += 1
        else:
            print("Token already approved for position manager, skipping approval")

        # STEP 2: Check if pool exists
        pool_address = factory_contract.functions.getPool(token0, token1, fee).call()
        pool_exists = pool_address != '0x0000000000000000000000000000000000000000'
        print(f"Pool exists: {pool_exists}, address: {pool_address}")

        # STEP 3: Prepare multicall data (similar to TypeScript code)
        # Get latest nonce
        nonce = web3.eth.get_transaction_count(user_wallet['address'])

        # Calculate ticks for full range position
        min_tick, max_tick = calculate_ticks(fee)
        print(f"Using tick range: {min_tick} to {max_tick}")

        # Set up multicall data - this needs to be a list of bytes objects
        calldata = []

        # If pool doesn't exist, add createAndInitializePoolIfNecessary to calldata
        if not pool_exists:
            # Calculate price based on the amounts
            if amount1_desired > 0 and amount0_desired > 0:
                price = float(amount1_desired) / float(amount0_desired)
            else:
                price = 1.0  # Default price (1:1)
            
            sqrt_price_x96 = calculate_sqrt_price_x96(price)
            print(f"Creating pool with sqrtPriceX96: {sqrt_price_x96}")

            # Encode createAndInitializePoolIfNecessary function call
            create_pool_tx = position_manager_contract.functions.createAndInitializePoolIfNecessary(
                token0, token1, fee, sqrt_price_x96
            ).build_transaction({
                'chainId': web3.eth.chain_id,
                'gas': 300000,
                'gasPrice': web3.eth.gas_price,
                'nonce': 0,  # Dummy nonce, not used in multicall
                'from': user_wallet['address']
            })
            create_pool_data = create_pool_tx['data']
            calldata.append(create_pool_data)

        # Set deadline 20 minutes from now
        deadline = int(time.time()) + 1200

        # Encode mint function call
        mint_params = {
            'token0': token0,
            'token1': token1,
            'fee': fee,
            'tickLower': min_tick,
            'tickUpper': max_tick,
            'amount0Desired': amount0_desired,
            'amount1Desired': amount1_desired,
            'amount0Min': 0,  # Following the TypeScript example
            'amount1Min': 0,  # Following the TypeScript example
            'recipient': user_wallet['address'],
            'deadline': deadline
        }

        print(f"Mint params: {mint_params}")

        # Encode mint function call
        mint_tx = position_manager_contract.functions.mint(
            mint_params
        ).build_transaction({
            'chainId': web3.eth.chain_id,
            'gas': 300000,
            'gasPrice': web3.eth.gas_price,
            'nonce': 0,  # Dummy nonce, not used in multicall
            'from': user_wallet['address']
        })
        mint_data = mint_tx['data']
        calldata.append(mint_data)

        # STEP 4: Execute multicall
        print(f"Executing multicall with {len(calldata)} functions")
        
        # The multicall function expects a list of bytes objects (encoded function calls)
        # Each item in the calldata array is the encoded function call (data field from build_transaction)
        multicall_tx = position_manager_contract.functions.multicall(
            calldata
        ).build_transaction({
            'chainId': web3.eth.chain_id,
            'gas': 15000000,  # Increased gas limit to match successful transaction
            'maxFeePerGas': web3.eth.gas_price,  # Use EIP-1559 transaction type
            'maxPriorityFeePerGas': web3.eth.gas_price,
            'nonce': nonce,
            'from': user_wallet['address'],
            'value': eth_amount_wei if not is_token0 else 0,  # Send ETH if it's token1
            'type': 2  # EIP-1559 transaction type
        })

        # Sign and send transaction
        tx_hash = sign_and_send_transaction(web3, multicall_tx, user_wallet['private_key'])
        receipt = wait_for_transaction_receipt(web3, tx_hash)
        print(f"Multicall tx hash: {tx_hash.hex()}, status: {receipt.status}")

        # Check if transaction was successful
        if receipt.status == 0:
            return {
                'status': 'failed',
                'error': 'Transaction failed',
                'tx_hash': tx_hash.hex()
            }

        # STEP 5: Extract position ID from logs
        position_id = None
        if receipt.logs:
            for log in receipt.logs:
                try:
                    # Try to find the Transfer event from NonfungiblePositionManager for the newly minted position
                    if log['address'].lower() == position_manager_address.lower():
                        # Transfer event topic
                        transfer_event_topic = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
                        if len(log['topics']) >= 4 and log['topics'][0].hex().lower() == transfer_event_topic and log['topics'][1].hex().lower() == '0x0000000000000000000000000000000000000000000000000000000000000000':
                            # Found a Transfer from address 0, which is a mint event
                            # topic[3] contains the tokenId
                            position_id = int(log['topics'][3].hex(), 16)
                            print(f'Created position with ID: {position_id}')
                            break  # Exit loop once we find the position ID
                except Exception as e:
                    print(f'Error parsing log: {e}')
                    continue  # Continue to next log if there's an error

        # Additional check for IncreaseLiquidity event if position_id is still None
        if position_id is None and receipt.logs:
            for log in receipt.logs:
                try:
                    # Try to find the IncreaseLiquidity event
                    if log['address'].lower() == position_manager_address.lower():
                        # IncreaseLiquidity event topic
                        increase_liquidity_topic = '0x3067048beee31b25b2f1681f88dac838c8bba36af25bfb2b7cf7473a5847e35f'
                        if len(log['topics']) >= 2 and log['topics'][0].hex().lower() == increase_liquidity_topic:
                            # topic[1] contains the tokenId in IncreaseLiquidity
                            position_id = int(log['topics'][1].hex(), 16)
                            print(f'Found position ID from IncreaseLiquidity event: {position_id}')
                            break
                except Exception as e:
                    print(f'Error parsing IncreaseLiquidity log: {e}')
                    continue

        # Get the pool address (if it was just created)
        if not pool_exists:
            pool_address = factory_contract.functions.getPool(token0, token1, fee).call()
            print(f"New pool created at: {pool_address}")

        # Update pool in database with final address
        save_pool_to_db(user_id, token_address, pool_address, 
                      {'token_amount': token_amount, 'eth_amount': eth_amount}, network)

        # Return success result
        return {
            'status': 'success',
            'pool_address': pool_address,
            'position_id': position_id,
            'token_amount': token_amount,
            'eth_amount': eth_amount,
            'tx_hash': tx_hash.hex()
        }

    except Exception as e:
        print(f"Error in execute_pool_creation: {e}")
        
        # If there was an error with the ticks, try with a retry approach similar to TypeScript code
        if "tick" in str(e).lower() or "liquidity" in str(e).lower():
            try:
                print("Retrying with adjusted ticks...")
                
                # Get fresh nonce
                nonce = web3.eth.get_transaction_count(user_wallet['address'])
                
                # Use exact full range with retry
                retry_tick_spacing = get_tick_spacing(fee)
                retry_min_tick = math.ceil(-887272 / retry_tick_spacing) * retry_tick_spacing
                retry_max_tick = math.floor(887272 / retry_tick_spacing) * retry_tick_spacing
                
                print(f"Retry with exact full range: {retry_min_tick} to {retry_max_tick}")
                
                # Set up retry multicall data
                retry_calldata = []
                
                # If pool doesn't exist, add createAndInitializePoolIfNecessary to calldata
                if not pool_exists:
                    # Default to 1:1 price for retry
                    sqrt_price_x96 = calculate_sqrt_price_x96(1.0)
                    print(f"Retrying pool creation with sqrtPriceX96: {sqrt_price_x96}")
                    
                    # Encode using build_transaction and extract data
                    create_pool_tx = position_manager_contract.functions.createAndInitializePoolIfNecessary(
                        token0, token1, fee, sqrt_price_x96
                    ).build_transaction({
                        'chainId': web3.eth.chain_id,
                        'gas': 300000,
                        'gasPrice': web3.eth.gas_price,
                        'nonce': 0,  # Dummy nonce, not used in multicall
                        'from': user_wallet['address']
                    })
                    create_pool_data = create_pool_tx['data']
                    retry_calldata.append(create_pool_data)
                
                # Set deadline 20 minutes from now
                deadline = int(time.time()) + 1200
                
                # Encode mint function call with adjusted ticks
                retry_mint_params = {
                    'token0': token0,
                    'token1': token1,
                    'fee': fee,
                    'tickLower': retry_min_tick,
                    'tickUpper': retry_max_tick,
                    'amount0Desired': amount0_desired,
                    'amount1Desired': amount1_desired,
                    'amount0Min': 0,  # Following the TypeScript example
                    'amount1Min': 0,  # Following the TypeScript example
                    'recipient': user_wallet['address'],
                    'deadline': deadline
                }
                
                print(f"Retry mint params: {retry_mint_params}")
                
                # Encode using build_transaction and extract data
                retry_mint_tx = position_manager_contract.functions.mint(
                    retry_mint_params
                ).build_transaction({
                    'chainId': web3.eth.chain_id,
                    'gas': 300000,
                    'gasPrice': web3.eth.gas_price,
                    'nonce': 0,  # Dummy nonce, not used in multicall
                    'from': user_wallet['address']
                })
                retry_mint_data = retry_mint_tx['data']
                retry_calldata.append(retry_mint_data)
                
                # Execute retry multicall
                print(f"Executing retry multicall with {len(retry_calldata)} functions")
                
                # The multicall function expects a list of bytes objects (encoded function calls)
                # Each item in the retry_calldata array is the encoded function call (data field from build_transaction)
                retry_multicall_tx = position_manager_contract.functions.multicall(
                    retry_calldata
                ).build_transaction({
                    'chainId': web3.eth.chain_id,
                    'gas': 15000000,  # Increased gas limit to match successful transaction
                    'maxFeePerGas': web3.eth.gas_price,  # Use EIP-1559 transaction type
                    'maxPriorityFeePerGas': web3.eth.gas_price,
                    'nonce': nonce,
                    'from': user_wallet['address'],
                    'value': eth_amount_wei if not is_token0 else 0,  # Send ETH if it's token1
                    'type': 2  # EIP-1559 transaction type
                })
                
                # Sign and send transaction
                retry_tx_hash = sign_and_send_transaction(web3, retry_multicall_tx, user_wallet['private_key'])
                retry_receipt = wait_for_transaction_receipt(web3, retry_tx_hash)
                print(f"Retry multicall tx hash: {retry_tx_hash.hex()}, status: {retry_receipt.status}")
                
                # Check if transaction was successful
                if retry_receipt.status == 0:
                    return {
                        'status': 'failed',
                        'error': 'Retry transaction failed',
                        'tx_hash': retry_tx_hash.hex()
                    }
                
                # Extract position ID from logs
                retry_position_id = None
                if retry_receipt.logs:
                    for log in retry_receipt.logs:
                        try:
                            # Try to find the Transfer event
                            if log['address'].lower() == position_manager_address.lower():
                                # Transfer event topic
                                transfer_event_topic = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
                                if len(log['topics']) >= 4 and log['topics'][0].hex().lower() == transfer_event_topic and log['topics'][1].hex().lower() == '0x0000000000000000000000000000000000000000000000000000000000000000':
                                    # Found a Transfer from address 0, which is a mint event
                                    retry_position_id = int(log['topics'][3].hex(), 16)
                                    print(f'Created position with ID (retry): {retry_position_id}')
                                    break  # Exit loop once we find the position ID
                        except Exception as e:
                            print(f'Error parsing retry log: {e}')
                            continue  # Continue to next log if there's an error
                
                # Additional check for IncreaseLiquidity event if retry_position_id is still None
                if retry_position_id is None and retry_receipt.logs:
                    for log in retry_receipt.logs:
                        try:
                            # Try to find the IncreaseLiquidity event
                            if log['address'].lower() == position_manager_address.lower():
                                # IncreaseLiquidity event topic
                                increase_liquidity_topic = '0x3067048beee31b25b2f1681f88dac838c8bba36af25bfb2b7cf7473a5847e35f'
                                if len(log['topics']) >= 2 and log['topics'][0].hex().lower() == increase_liquidity_topic:
                                    # topic[1] contains the tokenId in IncreaseLiquidity
                                    retry_position_id = int(log['topics'][1].hex(), 16)
                                    print(f'Found position ID from IncreaseLiquidity event (retry): {retry_position_id}')
                                    break
                        except Exception as e:
                            print(f'Error parsing retry IncreaseLiquidity log: {e}')
                            continue
                
                # Get the pool address (if it was just created)
                retry_pool_address = factory_contract.functions.getPool(token0, token1, fee).call()
                print(f"Retry pool address: {retry_pool_address}")
                
                # Update pool in database with final address
                save_pool_to_db(user_id, token_address, retry_pool_address, 
                              {'token_amount': token_amount, 'eth_amount': eth_amount}, network)
                
                # Return success result for retry
                return {
                    'status': 'success',
                    'pool_address': retry_pool_address,
                    'position_id': retry_position_id,
                    'token_amount': token_amount,
                    'eth_amount': eth_amount,
                    'tx_hash': retry_tx_hash.hex(),
                    'retry': True
                }
                
            except Exception as retry_error:
                print(f"Retry also failed: {retry_error}")
                return {
                    'status': 'failed',
                    'error': f"Both attempts failed. Original: {str(e)}. Retry: {str(retry_error)}"
                }
        
        return {
            'status': 'failed',
            'error': str(e)
        } 