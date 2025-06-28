import json
import time
from typing import Dict, List, Optional, Tuple, Union, Any
from web3 import Web3
from eth_typing import Address, ChecksumAddress
from web3.contract import Contract
from web3.types import TxParams, Wei

# UNCX Lock Contract ABI - Fixed with correct function signatures
UNCX_LOCK_ABI = [{
    "name":
    "setApprovalForAll",
    "type":
    "function",
    "inputs": [{
        "name": "operator",
        "type": "address"
    }, {
        "name": "approved",
        "type": "bool"
    }],
    "outputs": [],
    "stateMutability":
    "nonpayable"
}, {
    "name":
    "lock",
    "type":
    "function",
    "inputs": [{
        "name":
        "",
        "type":
        "tuple",
        "components": [{
            "name": "nftPositionManager",
            "type": "address"
        }, {
            "name": "nft_id",
            "type": "uint256"
        }, {
            "name": "dustRecipient",
            "type": "address"
        }, {
            "name": "owner",
            "type": "address"
        }, {
            "name": "additionalCollector",
            "type": "address"
        }, {
            "name": "collectAddress",
            "type": "address"
        }, {
            "name": "unlockDate",
            "type": "uint256"
        }, {
            "name": "countryCode",
            "type": "uint16"
        }, {
            "name": "feeName",
            "type": "string"
        }, {
            "name": "r",
            "type": "bytes[]"
        }]
    }],
    "outputs": [{
        "name": "",
        "type": "uint256"
    }],
    "stateMutability":
    "payable"
}, {
    "name":
    "getFee",
    "type":
    "function",
    "inputs": [{
        "name": "_name",
        "type": "string"
    }],
    "outputs": [{
        "name":
        "",
        "type":
        "tuple",
        "components": [{
            "name": "name",
            "type": "string"
        }, {
            "name": "lpFee",
            "type": "uint256"
        }, {
            "name": "collectFee",
            "type": "uint256"
        }, {
            "name": "flatFee",
            "type": "uint256"
        }, {
            "name": "flatFeeToken",
            "type": "address"
        }]
    }],
    "stateMutability":
    "view"
}, {
    "name": "getNumUserLocks",
    "type": "function",
    "inputs": [{
        "name": "_user",
        "type": "address"
    }],
    "outputs": [{
        "name": "",
        "type": "uint256"
    }],
    "stateMutability": "view"
}, {
    "name":
    "getUserLockAtIndex",
    "type":
    "function",
    "inputs": [{
        "name": "_user",
        "type": "address"
    }, {
        "name": "_index",
        "type": "uint256"
    }],
    "outputs": [{
        "name":
        "",
        "type":
        "tuple",
        "components": [{
            "name": "lock_id",
            "type": "uint256"
        }, {
            "name": "nftPositionManager",
            "type": "address"
        }, {
            "name": "nft_id",
            "type": "uint256"
        }, {
            "name": "owner",
            "type": "address"
        }, {
            "name": "pendingOwner",
            "type": "address"
        }, {
            "name": "additionalCollector",
            "type": "address"
        }, {
            "name": "collectAddress",
            "type": "address"
        }, {
            "name": "unlockDate",
            "type": "uint256"
        }, {
            "name": "countryCode",
            "type": "uint16"
        }, {
            "name": "ucf",
            "type": "uint256"
        }]
    }],
    "stateMutability":
    "view"
}, {
    "name":
    "getLock",
    "type":
    "function",
    "inputs": [{
        "name": "_lockId",
        "type": "uint256"
    }],
    "outputs": [{
        "name":
        "",
        "type":
        "tuple",
        "components": [{
            "name": "lock_id",
            "type": "uint256"
        }, {
            "name": "nftPositionManager",
            "type": "address"
        }, {
            "name": "pool",
            "type": "address"
        }, {
            "name": "nft_id",
            "type": "uint256"
        }, {
            "name": "owner",
            "type": "address"
        }, {
            "name": "pendingOwner",
            "type": "address"
        }, {
            "name": "additionalCollector",
            "type": "address"
        }, {
            "name": "collectAddress",
            "type": "address"
        }, {
            "name": "unlockDate",
            "type": "uint256"
        }, {
            "name": "countryCode",
            "type": "uint16"
        }, {
            "name": "ucf",
            "type": "uint256"
        }]
    }],
    "stateMutability":
    "view"
}]

# Uniswap V3 Position Manager ABI (only the functions we need)
UNISWAP_V3_POSITION_ABI = [{
    "name": "balanceOf",
    "type": "function",
    "inputs": [{
        "name": "owner",
        "type": "address"
    }],
    "outputs": [{
        "name": "",
        "type": "uint256"
    }],
    "stateMutability": "view"
}, {
    "name":
    "tokenOfOwnerByIndex",
    "type":
    "function",
    "inputs": [{
        "name": "owner",
        "type": "address"
    }, {
        "name": "index",
        "type": "uint256"
    }],
    "outputs": [{
        "name": "",
        "type": "uint256"
    }],
    "stateMutability":
    "view"
}, {
    "name":
    "positions",
    "type":
    "function",
    "inputs": [{
        "name": "tokenId",
        "type": "uint256"
    }],
    "outputs": [{
        "name": "nonce",
        "type": "uint96"
    }, {
        "name": "operator",
        "type": "address"
    }, {
        "name": "token0",
        "type": "address"
    }, {
        "name": "token1",
        "type": "address"
    }, {
        "name": "fee",
        "type": "uint24"
    }, {
        "name": "tickLower",
        "type": "int24"
    }, {
        "name": "tickUpper",
        "type": "int24"
    }, {
        "name": "liquidity",
        "type": "uint128"
    }, {
        "name": "feeGrowthInside0LastX128",
        "type": "uint256"
    }, {
        "name": "feeGrowthInside1LastX128",
        "type": "uint256"
    }, {
        "name": "tokensOwed0",
        "type": "uint128"
    }, {
        "name": "tokensOwed1",
        "type": "uint128"
    }],
    "stateMutability":
    "view"
}, {
    "name":
    "isApprovedForAll",
    "type":
    "function",
    "inputs": [{
        "name": "owner",
        "type": "address"
    }, {
        "name": "operator",
        "type": "address"
    }],
    "outputs": [{
        "name": "",
        "type": "bool"
    }],
    "stateMutability":
    "view"
}, {
    "name":
    "setApprovalForAll",
    "type":
    "function",
    "inputs": [{
        "name": "operator",
        "type": "address"
    }, {
        "name": "approved",
        "type": "bool"
    }],
    "outputs": [],
    "stateMutability":
    "nonpayable"
}]

# ERC20 ABI for token symbol lookup
ERC20_ABI = [{
    "name": "symbol",
    "type": "function",
    "inputs": [],
    "outputs": [{
        "name": "",
        "type": "string"
    }],
    "stateMutability": "view"
}]

# Contract addresses
UNISWAP_V3_POSITION_NFT = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"

# Define network types
NetworkName = str  # 'ethereum' | 'arbitrum' | 'optimism' | 'polygon' | 'base' | 'bsc' | 'avalanche' | 'celo' | 'sepolia'

# UNCX Lock Contract addresses for different networks
UNCX_LOCK_ADDRESSES: Dict[NetworkName, str] = {
    "ethereum": "0xFD235968e65B0990584585763f837A5b5330e6DE",
    "arbitrum": "0x6b5360B419e0851b4b81644e0F63c1A9778f2506",
    "optimism": "0x1cE6d27F7e5494573684436d99574e8288eBBD2D",
    "polygon": "0x40f6301edb774e8B22ADC874f6cb17242BaEB8c4",
    "base": "0x231278eDd38B00B07fBd52120CEf685B9BaEBCC1",
    "bsc": "0xfe88DAB083964C56429baa01F37eC2265AbF1557",
    "avalanche": "0x625e1b2e78DC5b978237f9c29DE2910062D80a05",
    "celo": "0xb108D212d1aEDf054354E7E707eab5bce6e029C6",
    "sepolia": "0x6a976ECb2377E7CbB5B48913b0faA1D7446D4dC7"
}

# Network currency symbols
NETWORK_CURRENCY_SYMBOLS: Dict[NetworkName, str] = {
    "ethereum": "ETH",
    "arbitrum": "ETH",
    "optimism": "ETH",
    "polygon": "MATIC",
    "base": "ETH",
    "bsc": "BNB",
    "avalanche": "AVAX",
    "celo": "CELO",
    "sepolia": "ETH"
}

# Default fee names for different networks
DEFAULT_FEE_NAMES: Dict[NetworkName, str] = {
    "ethereum": "LVP",  # From the successful Ethereum transaction
    "arbitrum": "DEFAULT",
    "optimism": "DEFAULT",
    "polygon": "DEFAULT",
    "base": "DEFAULT",
    "bsc": "DEFAULT",
    "avalanche": "DEFAULT",
    "celo": "DEFAULT",
    "sepolia": "DEFAULT"
}


class Position:

    def __init__(self, token_id: str, token0: str, token1: str, fee: int,
                 liquidity: str, token0_symbol: str, token1_symbol: str):
        self.token_id = token_id
        self.token0 = token0
        self.token1 = token1
        self.fee = fee
        self.liquidity = liquidity
        self.token0_symbol = token0_symbol
        self.token1_symbol = token1_symbol

    def __repr__(self):
        return f"Position(token_id={self.token_id}, {self.token0_symbol}/{self.token1_symbol}, fee={self.fee/10000}%)"


class LockedPosition:

    def __init__(self, lock_id: str, nft_id: str, token0: str, token1: str,
                 token0_symbol: str, token1_symbol: str, fee: int,
                 unlock_date: int, liquidity: str):
        self.lock_id = lock_id
        self.nft_id = nft_id
        self.token0 = token0
        self.token1 = token1
        self.token0_symbol = token0_symbol
        self.token1_symbol = token1_symbol
        self.fee = fee
        self.unlock_date = unlock_date
        self.unlock_date_formatted = self._format_date(unlock_date)
        self.liquidity = liquidity
        self.is_expired = self._is_expired()

    def _format_date(self, timestamp: int) -> str:
        """Format timestamp to readable date"""
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))

    def _is_expired(self) -> bool:
        """Check if a lock has expired"""
        return self.unlock_date < int(time.time())

    def __repr__(self):
        status = "Unlocked" if self.is_expired else "Locked"
        return f"LockedPosition(lock_id={self.lock_id}, nft_id={self.nft_id}, {self.token0_symbol}/{self.token1_symbol}, unlock_date={self.unlock_date_formatted}, status={status})"


class LiquidityLocker:
    """
    Python implementation of UNCX Liquidity Locker functionality
    """

    def __init__(self, web3_provider: Web3):
        """
        Initialize the LiquidityLocker with a Web3 provider

        Args:
            web3_provider: An initialized Web3 instance
        """
        self.web3 = web3_provider
        # Increase timeout for RPC calls
        if hasattr(self.web3.provider, 'timeout'):
            self.web3.provider.timeout = 60  # Increase timeout to 60 seconds

        self.chain_id = self.web3.eth.chain_id
        self.network_name = self._get_network_name(self.chain_id)
        self.lock_contract_address = UNCX_LOCK_ADDRESSES.get(
            self.network_name, UNCX_LOCK_ADDRESSES["polygon"])
        self.fee_name = DEFAULT_FEE_NAMES.get(self.network_name, "DEFAULT")
        self.native_currency = NETWORK_CURRENCY_SYMBOLS.get(
            self.network_name, "ETH")

        # Initialize contracts
        self.position_contract = self.web3.eth.contract(
            address=Web3.to_checksum_address(UNISWAP_V3_POSITION_NFT),
            abi=UNISWAP_V3_POSITION_ABI)

        self.lock_contract = self.web3.eth.contract(
            address=Web3.to_checksum_address(self.lock_contract_address),
            abi=UNCX_LOCK_ABI)

    def _get_network_name(self, chain_id: int) -> NetworkName:
        """
        Get network name from chain ID

        Args:
            chain_id: The chain ID

        Returns:
            The network name
        """
        network_map = {
            1: "ethereum",
            42161: "arbitrum",
            10: "optimism",
            137: "polygon",
            8453: "base",
            56: "bsc",
            43114: "avalanche",
            42220: "celo",
            11155111: "sepolia"
        }
        return network_map.get(
            chain_id,
            "polygon")  # Default to polygon if network not recognized

    def get_token_symbol(self, token_address: str) -> str:
        """
        Get token symbol from address

        Args:
            token_address: The token contract address

        Returns:
            The token symbol
        """
        try:
            token_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(token_address), abi=ERC20_ABI)
            return token_contract.functions.symbol().call()
        except Exception as e:
            print(f"Error getting token symbol: {e}")
            return token_address[:
                                 6]  # Return truncated address if symbol lookup fails

    def get_positions(self, wallet_address: str) -> List[Position]:
        """
        Get all Uniswap V3 positions for a wallet

        Args:
            wallet_address: The wallet address

        Returns:
            List of Position objects
        """
        wallet_address = Web3.to_checksum_address(wallet_address)
        positions = []

        try:
            # Get number of positions owned by user
            balance = self.position_contract.functions.balanceOf(
                wallet_address).call()

            if balance == 0:
                return positions

            # Fetch all positions
            for i in range(balance):
                position = self._get_position_details(wallet_address, i)
                if position:
                    positions.append(position)

            return positions
        except Exception as e:
            print(f"Error fetching positions: {e}")
            return []

    def _get_position_details(self, wallet_address: str,
                              index: int) -> Optional[Position]:
        """
        Get details for a single position

        Args:
            wallet_address: The wallet address
            index: The position index

        Returns:
            Position object or None if error
        """
        try:
            # Get token ID for the position
            token_id = self.position_contract.functions.tokenOfOwnerByIndex(
                wallet_address, index).call()

            # Get position details
            position = self.position_contract.functions.positions(
                token_id).call()

            # Get token symbols
            token0_symbol = self.get_token_symbol(position[2])  # token0
            token1_symbol = self.get_token_symbol(position[3])  # token1

            return Position(token_id=str(token_id),
                            token0=position[2],
                            token1=position[3],
                            fee=position[4],
                            liquidity=str(position[7]),
                            token0_symbol=token0_symbol,
                            token1_symbol=token1_symbol)
        except Exception as e:
            print(f"Error fetching position details: {e}")
            return None

    def is_approved(self, wallet_address: str) -> bool:
        """
        Check if UNCX is approved to transfer the user's NFT positions

        Args:
            wallet_address: The wallet address

        Returns:
            True if approved, False otherwise
        """
        try:
            wallet_address = Web3.to_checksum_address(wallet_address)
            lock_address = Web3.to_checksum_address(self.lock_contract_address)

            return self.position_contract.functions.isApprovedForAll(
                wallet_address, lock_address).call()
        except Exception as e:
            print(f"Error checking approval: {e}")
            return False

    def approve_uncx(self, wallet_address: str) -> Dict[str, Any]:
        """
        Approve UNCX to transfer the user's NFT positions

        Args:
            wallet_address: The wallet address

        Returns:
            Dictionary with transaction details
        """
        try:
            if self.is_approved(wallet_address):
                return {
                    "success": True,
                    "message": "Already approved",
                    "already_approved": True
                }

            wallet_address = Web3.to_checksum_address(wallet_address)
            lock_address = Web3.to_checksum_address(self.lock_contract_address)

            print(
                f"Approving UNCX locker ({lock_address}) to access positions for {wallet_address}"
            )

            # Get current nonce with retry logic
            max_retries = 3
            retry_count = 0
            nonce = None
            
            while retry_count < max_retries:
                try:
                    nonce = self.web3.eth.get_transaction_count(wallet_address)
                    break
                except Exception as e:
                    print(f"Error getting nonce (attempt {retry_count+1}): {e}")
                    retry_count += 1
                    time.sleep(1)  # Wait before retrying
            
            if nonce is None:
                return {
                    "success": False,
                    "error": "Failed to get transaction nonce after multiple attempts"
                }

            # Build transaction
            tx = self.position_contract.functions.setApprovalForAll(
                lock_address, True).build_transaction({
                    'from': wallet_address,
                    'nonce': nonce,
                    'gas': 200000,
                    'gasPrice': self.web3.eth.gas_price
                })

            return {
                "success": True,
                "transaction": tx
            }
        except Exception as e:
            print(f"Error in approve_uncx: {e}")
            return {
                "success": False,
                "error": f"Error building approval transaction: {str(e)}"
            }

    def get_lock_fee(self) -> Tuple[str, Wei]:
        """
        Get the flat fee required for locking

        Returns:
            Tuple of (fee in ETH as string, fee in Wei)
        """
        try:
            fee_struct = self.lock_contract.functions.getFee(
                self.fee_name).call()
            flat_fee_wei = fee_struct[3]  # flatFee
            flat_fee_eth = self.web3.from_wei(flat_fee_wei, 'ether')
            return str(flat_fee_eth), flat_fee_wei
        except Exception as e:
            print(f"Error getting flat fee: {e}")
            # Default fallback value
            default_fee_wei = self.web3.to_wei(0.01, 'ether')
            return "0.01", default_fee_wei

    def lock_position(self,
                      wallet_address: str,
                      position_id: str,
                      lock_duration_days: int,
                      country_code: int = 0) -> Dict[str, Any]:
        """
        Lock a liquidity position

        Args:
            wallet_address: The wallet address
            position_id: The position token ID
            lock_duration_days: Lock duration in days
            country_code: Country code (default: 0)

        Returns:
            Dictionary with transaction details
        """
        wallet_address = Web3.to_checksum_address(wallet_address)

        # Check if approved
        if not self.is_approved(wallet_address):
            return {
                "success": False,
                "error":
                "Position not approved for UNCX. Call approve_uncx first."
            }

        # Calculate unlock date (current time + lockDuration days)
        unlock_date = int(time.time()) + (lock_duration_days * 24 * 60 * 60)

        # Get the fee from the contract
        _, flat_fee_wei = self.get_lock_fee()

        # Structure the lock parameters
        lock_params = (
            UNISWAP_V3_POSITION_NFT,  # nftPositionManager
            int(position_id),  # nft_id
            wallet_address,  # dustRecipient
            wallet_address,  # owner
            wallet_address,  # additionalCollector
            wallet_address,  # collectAddress
            unlock_date,  # unlockDate
            country_code,  # countryCode
            self.fee_name,  # feeName
            []  # r (empty bytes array)
        )

        try:
            # Get current nonce with retry logic
            max_retries = 3
            retry_count = 0
            nonce = None
            
            while retry_count < max_retries:
                try:
                    nonce = self.web3.eth.get_transaction_count(wallet_address)
                    break
                except Exception as e:
                    print(f"Error getting nonce (attempt {retry_count+1}): {e}")
                    retry_count += 1
                    time.sleep(1)  # Wait before retrying
            
            if nonce is None:
                return {
                    "success": False,
                    "error": "Failed to get transaction nonce after multiple attempts"
                }

            # Build transaction
            tx = self.lock_contract.functions.lock(lock_params).build_transaction({
                'from': wallet_address,
                'value': flat_fee_wei,
                'nonce': nonce,
                'gas': 1000000,
                'gasPrice': self.web3.eth.gas_price
            })

            return {
                "success": True,
                "transaction": tx,
                "unlock_date": unlock_date,
                "fee_wei": flat_fee_wei,
                "fee_eth": self.web3.from_wei(flat_fee_wei, 'ether')
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error building transaction: {str(e)}"
            }

    def get_locked_positions(self,
                             wallet_address: str) -> List[LockedPosition]:
        """
        Get all locked positions for a wallet

        Args:
            wallet_address: The wallet address

        Returns:
            List of LockedPosition objects
        """
        wallet_address = Web3.to_checksum_address(wallet_address)
        locked_positions = []

        try:
            # Get number of locks for the user
            try:
                num_locks = self.lock_contract.functions.getNumUserLocks(
                    wallet_address).call()
            except Exception as e:
                print(f"Error getting number of locks: {e}")
                # Try a direct approach - query some reasonable number of locks
                # This is a fallback if getNumUserLocks fails
                print("Attempting fallback method to retrieve locks...")
                num_locks = 10  # Try to get up to 10 locks

            if num_locks == 0:
                return locked_positions

            # Fetch all locks
            for i in range(num_locks):
                try:
                    lock = self._get_lock_details(wallet_address, i)
                    if lock:
                        locked_positions.append(lock)
                except Exception as e:
                    print(f"Error fetching lock at index {i}: {e}")
                    # Continue to the next lock instead of failing completely

            return locked_positions
        except Exception as e:
            print(f"Error fetching locked positions: {e}")
            return []

    def _get_lock_details(self, wallet_address: str,
                          index: int) -> Optional[LockedPosition]:
        """
        Get details for a single lock

        Args:
            wallet_address: The wallet address
            index: The lock index

        Returns:
            LockedPosition object or None if error
        """
        try:
            # Get lock details from getUserLockAtIndex
            # Handle the contract response structure correctly
            try:
                user_lock = self.lock_contract.functions.getUserLockAtIndex(
                    wallet_address, index).call()
                lock_id = str(user_lock[0])
            except Exception as decode_error:
                print(f"Error decoding getUserLockAtIndex response: {decode_error}")
                # Try to extract the lock_id from the raw response
                try:
                    # Get the lock ID directly using getLock with the index
                    # This is a fallback approach
                    lock_id = str(index)
                    # Continue with this lock_id
                except Exception:
                    print(f"Could not extract lock ID from error: {decode_error}")
                    return None

            try:
                # Get more detailed lock information using getLock function
                lock = self.lock_contract.functions.getLock(lock_id).call()

                # Check if the lock has a valid pool address
                if lock[2] != "0x0000000000000000000000000000000000000000":
                    # Try to get token information from the pool
                    try:
                        # Create a minimal pool interface to get token0 and token1
                        pool_abi = [{
                            "name":
                            "token0",
                            "type":
                            "function",
                            "inputs": [],
                            "outputs": [{
                                "name": "",
                                "type": "address"
                            }],
                            "stateMutability":
                            "view"
                        }, {
                            "name":
                            "token1",
                            "type":
                            "function",
                            "inputs": [],
                            "outputs": [{
                                "name": "",
                                "type": "address"
                            }],
                            "stateMutability":
                            "view"
                        }, {
                            "name": "fee",
                            "type": "function",
                            "inputs": [],
                            "outputs": [{
                                "name": "",
                                "type": "uint24"
                            }],
                            "stateMutability": "view"
                        }]

                        pool_contract = self.web3.eth.contract(
                            address=Web3.to_checksum_address(lock[2]),
                            abi=pool_abi)

                        # Get token addresses and fee from the pool
                        token0 = pool_contract.functions.token0().call()
                        token1 = pool_contract.functions.token1().call()
                        fee = pool_contract.functions.fee().call()

                        # Get token symbols
                        token0_symbol = self.get_token_symbol(token0)
                        token1_symbol = self.get_token_symbol(token1)

                        return LockedPosition(
                            lock_id=lock_id,
                            nft_id=str(lock[3]),  # nft_id
                            token0=token0,
                            token1=token1,
                            token0_symbol=token0_symbol,
                            token1_symbol=token1_symbol,
                            fee=fee,
                            unlock_date=lock[8],  # unlockDate
                            liquidity=
                            "N/A"  # We don't have liquidity information from the pool
                        )
                    except Exception as pool_error:
                        print(f"Error getting pool information: {pool_error}")

                # Fallback: Return lock with basic information
                return LockedPosition(
                    lock_id=lock_id,
                    nft_id=str(lock[3]),  # nft_id
                    token0="0x0000000000000000000000000000000000000000",
                    token1="0x0000000000000000000000000000000000000000",
                    token0_symbol="Unknown",
                    token1_symbol="Unknown",
                    fee=0,
                    unlock_date=lock[8],  # unlockDate
                    liquidity="0")
            except Exception as lock_error:
                print(f"Error fetching detailed lock information: {lock_error}")
                # Create a minimal lock object with just the ID
                return LockedPosition(
                    lock_id=lock_id,
                    nft_id="Unknown",
                    token0="0x0000000000000000000000000000000000000000",
                    token1="0x0000000000000000000000000000000000000000",
                    token0_symbol="Unknown",
                    token1_symbol="Unknown",
                    fee=0,
                    unlock_date=int(time.time()) + 3600,  # Placeholder unlock date
                    liquidity="0")
        except Exception as e:
            print(f"Error fetching lock details: {e}")
            return None

    def interpret_uncx_error(self, error_code: str) -> str:
        """
        Interpret UNCX Locker error codes

        Args:
            error_code: The error code

        Returns:
            Human-readable error message
        """
        error_map = {
            "TF":
            "Transfer Failed: The transaction couldn't transfer the required fee. Make sure you have enough MATIC to cover the fee.",
            "FLAT FEE":
            "Incorrect fee amount. The contract requires the exact fee amount specified.",
            "DATE PASSED":
            "The unlock date has already passed. Please choose a future date.",
            "COUNTRY":
            "Invalid country code. Please set a valid country code.",
            "INVALID NFT POSITION MANAGER":
            "The NFT position manager is not whitelisted by UNCX.",
            "OWNER CANNOT = address(0)":
            "Owner address cannot be the zero address.",
            "COLLECT_ADDR":
            "Collect address cannot be the zero address.",
            "MILLISECONDS":
            "Invalid unlock date format. Please ensure you're using Unix timestamp in seconds.",
            "NOT FOUND":
            "Fee structure not found. The specified fee name is invalid."
        }

        return error_map.get(error_code, f"Error: {error_code}")
