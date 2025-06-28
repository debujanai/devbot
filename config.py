import os

# Bot configuration

# Data storage paths
DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
TOKENS_FILE = os.path.join(DATA_DIR, "tokens.json")
POOLS_FILE = os.path.join(DATA_DIR, "pools.json")

# User state enum
class UserState:
    MAIN_MENU = "main_menu"
    WALLET_SETUP = "wallet_setup"
    TOKEN_CREATION = "token_creation"
    POOL_CREATION = "pool_creation"
    SELECTING_FEATURES = "selecting_features"
    SETTING_TAXES = "setting_taxes"
    SETTING_TOKEN_DETAILS = "setting_token_details"
    ENTERING_TOKEN_ADDRESS = "entering_token_address" 
    LIQUIDITY_MANAGEMENT = "liquidity_management"
    LOCK_POSITION = "lock_position"
    CONTRACT_RENOUNCEMENT = "contract_renouncement"
    ENTERING_CONTRACT_ADDRESS = "entering_contract_address"
    ENTERING_TAX_WALLET = "entering_tax_wallet"

# Contract addresses (Polygon)
POLYGON_ADDRESSES = {
    'UNISWAP_V3_FACTORY': '0x1F98431c8aD98523631AE4a59f267346ea31F984',
    'UNISWAP_V3_ROUTER': '0xE592427A0AEce92De3Edee1F18E0157C05861564',
    'UNISWAP_V3_POSITION_MANAGER': '0xC36442b4a4522E871399CD717aBDD847Ab11FE88',
    'WMATIC': '0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270'
}

# Contract ABIs
ERC20_ABI = [{
    "inputs": [{
        "internalType": "string",
        "name": "name",
        "type": "string"
    }, {
        "internalType": "string",
        "name": "symbol",
        "type": "string"
    }, {
        "internalType": "uint256",
        "name": "totalSupply",
        "type": "uint256"
    }, {
        "internalType": "uint8",
        "name": "decimals",
        "type": "uint8"
    }, {
        "internalType": "uint256",
        "name": "buyTax",
        "type": "uint256"
    }, {
        "internalType": "uint256",
        "name": "sellTax",
        "type": "uint256"
    }],
    "stateMutability":
    "nonpayable",
    "type":
    "constructor"
}, {
    "anonymous":
    False,
    "inputs": [{
        "indexed": True,
        "internalType": "address",
        "name": "owner",
        "type": "address"
    }, {
        "indexed": True,
        "internalType": "address",
        "name": "spender",
        "type": "address"
    }, {
        "indexed": False,
        "internalType": "uint256",
        "name": "value",
        "type": "uint256"
    }],
    "name":
    "Approval",
    "type":
    "event"
}, {
    "anonymous":
    False,
    "inputs": [{
        "indexed": True,
        "internalType": "address",
        "name": "from",
        "type": "address"
    }, {
        "indexed": True,
        "internalType": "address",
        "name": "to",
        "type": "address"
    }, {
        "indexed": False,
        "internalType": "uint256",
        "name": "value",
        "type": "uint256"
    }],
    "name":
    "Transfer",
    "type":
    "event"
}, {
    "inputs": [{
        "internalType": "address",
        "name": "owner",
        "type": "address"
    }, {
        "internalType": "address",
        "name": "spender",
        "type": "address"
    }],
    "name":
    "allowance",
    "outputs": [{
        "internalType": "uint256",
        "name": "",
        "type": "uint256"
    }],
    "stateMutability":
    "view",
    "type":
    "function"
}, {
    "inputs": [{
        "internalType": "address",
        "name": "spender",
        "type": "address"
    }, {
        "internalType": "uint256",
        "name": "amount",
        "type": "uint256"
    }],
    "name":
    "approve",
    "outputs": [{
        "internalType": "bool",
        "name": "",
        "type": "bool"
    }],
    "stateMutability":
    "nonpayable",
    "type":
    "function"
}, {
    "inputs": [{
        "internalType": "address",
        "name": "account",
        "type": "address"
    }],
    "name":
    "balanceOf",
    "outputs": [{
        "internalType": "uint256",
        "name": "",
        "type": "uint256"
    }],
    "stateMutability":
    "view",
    "type":
    "function"
}, {
    "inputs": [],
    "name":
    "decimals",
    "outputs": [{
        "internalType": "uint8",
        "name": "",
        "type": "uint8"
    }],
    "stateMutability":
    "view",
    "type":
    "function"
}, {
    "inputs": [],
    "name":
    "name",
    "outputs": [{
        "internalType": "string",
        "name": "",
        "type": "string"
    }],
    "stateMutability":
    "view",
    "type":
    "function"
}, {
    "inputs": [],
    "name":
    "symbol",
    "outputs": [{
        "internalType": "string",
        "name": "",
        "type": "string"
    }],
    "stateMutability":
    "view",
    "type":
    "function"
}, {
    "inputs": [],
    "name":
    "totalSupply",
    "outputs": [{
        "internalType": "uint256",
        "name": "",
        "type": "uint256"
    }],
    "stateMutability":
    "view",
    "type":
    "function"
}, {
    "inputs": [{
        "internalType": "address",
        "name": "recipient",
        "type": "address"
    }, {
        "internalType": "uint256",
        "name": "amount",
        "type": "uint256"
    }],
    "name":
    "transfer",
    "outputs": [{
        "internalType": "bool",
        "name": "",
        "type": "bool"
    }],
    "stateMutability":
    "nonpayable",
    "type":
    "function"
}, {
    "inputs": [{
        "internalType": "address",
        "name": "sender",
        "type": "address"
    }, {
        "internalType": "address",
        "name": "recipient",
        "type": "address"
    }, {
        "internalType": "uint256",
        "name": "amount",
        "type": "uint256"
    }],
    "name":
    "transferFrom",
    "outputs": [{
        "internalType": "bool",
        "name": "",
        "type": "bool"
    }],
    "stateMutability":
    "nonpayable",
    "type":
    "function"
}]

UNISWAP_V3_FACTORY_ABI = [{
    "inputs": [{
        "internalType": "address",
        "name": "tokenA",
        "type": "address"
    }, {
        "internalType": "address",
        "name": "tokenB",
        "type": "address"
    }, {
        "internalType": "uint24",
        "name": "fee",
        "type": "uint24"
    }],
    "name":
    "createPool",
    "outputs": [{
        "internalType": "address",
        "name": "pool",
        "type": "address"
    }],
    "stateMutability":
    "nonpayable",
    "type":
    "function"
}, {
    "inputs": [{
        "internalType": "address",
        "name": "tokenA",
        "type": "address"
    }, {
        "internalType": "address",
        "name": "tokenB",
        "type": "address"
    }, {
        "internalType": "uint24",
        "name": "fee",
        "type": "uint24"
    }],
    "name":
    "getPool",
    "outputs": [{
        "internalType": "address",
        "name": "pool",
        "type": "address"
    }],
    "stateMutability":
    "view",
    "type":
    "function"
}]

POSITION_MANAGER_ABI = [{
    "inputs": [{
        "components": [{
            "internalType": "address",
            "name": "token0",
            "type": "address"
        }, {
            "internalType": "address",
            "name": "token1",
            "type": "address"
        }, {
            "internalType": "uint24",
            "name": "fee",
            "type": "uint24"
        }, {
            "internalType": "int24",
            "name": "tickLower",
            "type": "int24"
        }, {
            "internalType": "int24",
            "name": "tickUpper",
            "type": "int24"
        }, {
            "internalType": "uint256",
            "name": "amount0Desired",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amount1Desired",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amount0Min",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amount1Min",
            "type": "uint256"
        }, {
            "internalType": "address",
            "name": "recipient",
            "type": "address"
        }, {
            "internalType": "uint256",
            "name": "deadline",
            "type": "uint256"
        }],
        "internalType":
        "struct INonfungiblePositionManager.MintParams",
        "name":
        "params",
        "type":
        "tuple"
    }],
    "name":
    "mint",
    "outputs": [{
        "internalType": "uint256",
        "name": "tokenId",
        "type": "uint256"
    }, {
        "internalType": "uint128",
        "name": "liquidity",
        "type": "uint128"
    }, {
        "internalType": "uint256",
        "name": "amount0",
        "type": "uint256"
    }, {
        "internalType": "uint256",
        "name": "amount1",
        "type": "uint256"
    }],
    "stateMutability":
    "payable",
    "type":
    "function"
}]

# Position Manager ABI with pool creation function
POSITION_MANAGER_WITH_POOL_CREATE_ABI = POSITION_MANAGER_ABI + [
    {
        "inputs": [
            {
                "internalType": "address",
                "name": "token0",
                "type": "address"
            },
            {
                "internalType": "address",
                "name": "token1",
                "type": "address"
            },
            {
                "internalType": "uint24",
                "name": "fee",
                "type": "uint24"
            },
            {
                "internalType": "uint160",
                "name": "sqrtPriceX96",
                "type": "uint160"
            }
        ],
        "name": "createAndInitializePoolIfNecessary",
        "outputs": [
            {
                "internalType": "address",
                "name": "pool",
                "type": "address"
            }
        ],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [
            {
                "internalType": "bytes[]",
                "name": "data",
                "type": "bytes[]"
            }
        ],
        "name": "multicall",
        "outputs": [
            {
                "internalType": "bytes[]",
                "name": "results",
                "type": "bytes[]"
            }
        ],
        "stateMutability": "payable",
        "type": "function"
    }
]

# ERC20 token contract bytecode
ERC20_BYTECODE = """
pragma solidity ^0.8.0;

contract CustomERC20 {
    string public name;
    string public symbol;
    uint8 public decimals;
    uint256 public totalSupply;
    uint256 public buyTax;
    uint256 public sellTax;

    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    address public owner;
    address public taxWallet;
    bool public tradingEnabled = false;
    bool public maxWalletEnabled = false;
    bool public antiWhaleEnabled = false;
    bool public burnEnabled = false;
    bool public mintEnabled = false;

    uint256 public maxWalletAmount;
    uint256 public maxTransactionAmount;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);

    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }

    constructor(
        string memory _name,
        string memory _symbol,
        uint256 _totalSupply,
        uint8 _decimals,
        uint256 _buyTax,
        uint256 _sellTax,
        bool[5] memory _features // [maxWallet, antiWhale, burn, mint, trading]
    ) {
        name = _name;
        symbol = _symbol;
        decimals = _decimals;
        totalSupply = _totalSupply * 10**_decimals;
        buyTax = _buyTax;
        sellTax = _sellTax;
        owner = msg.sender;
        taxWallet = msg.sender;

        balanceOf[msg.sender] = totalSupply;

        maxWalletEnabled = _features[0];
        antiWhaleEnabled = _features[1];
        burnEnabled = _features[2];
        mintEnabled = _features[3];
        tradingEnabled = _features[4];

        if (maxWalletEnabled) {
            maxWalletAmount = totalSupply / 100; // 1% of total supply
        }

        if (antiWhaleEnabled) {
            maxTransactionAmount = totalSupply / 200; // 0.5% of total supply
        }

        emit Transfer(address(0), msg.sender, totalSupply);
    }

    function transfer(address to, uint256 amount) public returns (bool) {
        return _transfer(msg.sender, to, amount);
    }

    function transferFrom(address from, address to, uint256 amount) public returns (bool) {
        require(allowance[from][msg.sender] >= amount, "Insufficient allowance");
        allowance[from][msg.sender] -= amount;
        return _transfer(from, to, amount);
    }

    function _transfer(address from, address to, uint256 amount) internal returns (bool) {
        require(balanceOf[from] >= amount, "Insufficient balance");

        if (maxWalletEnabled && to != owner) {
            require(balanceOf[to] + amount <= maxWalletAmount, "Max wallet exceeded");
        }

        if (antiWhaleEnabled && from != owner && to != owner) {
            require(amount <= maxTransactionAmount, "Max transaction exceeded");
        }

        uint256 taxAmount = 0;
        if (from != owner && to != owner) {
            // Apply buy tax when buying from DEX
            if (to != address(0) && buyTax > 0) {
                taxAmount = (amount * buyTax) / 10000;
            }
            // Apply sell tax when selling to DEX
            else if (from != address(0) && sellTax > 0) {
                taxAmount = (amount * sellTax) / 10000;
            }
        }

        uint256 transferAmount = amount - taxAmount;

        balanceOf[from] -= amount;
        balanceOf[to] += transferAmount;

        if (taxAmount > 0) {
            balanceOf[taxWallet] += taxAmount;
            emit Transfer(from, taxWallet, taxAmount);
        }

        emit Transfer(from, to, transferAmount);
        return true;
    }

    function approve(address spender, uint256 amount) public returns (bool) {
        allowance[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }

    function burn(uint256 amount) public {
        require(burnEnabled, "Burn not enabled");
        require(balanceOf[msg.sender] >= amount, "Insufficient balance");
        balanceOf[msg.sender] -= amount;
        totalSupply -= amount;
        emit Transfer(msg.sender, address(0), amount);
    }

    function mint(address to, uint256 amount) public onlyOwner {
        require(mintEnabled, "Mint not enabled");
        totalSupply += amount;
        balanceOf[to] += amount;
        emit Transfer(address(0), to, amount);
    }

    function enableTrading() public onlyOwner {
        tradingEnabled = true;
    }

    function setTaxes(uint256 _buyTax, uint256 _sellTax) public onlyOwner {
        buyTax = _buyTax;
        sellTax = _sellTax;
    }
}
"""