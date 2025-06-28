import subprocess
import json
import os
import tempfile
from pathlib import Path

def create_js_deployment_file(contract_data):
    """
    Creates a temporary JavaScript file that will compile and deploy the contract
    using the provided contract data.
    
    Args:
        contract_data (dict): Dictionary containing contract details
        
    Returns:
        str: Path to the created JavaScript file
    """
    # Create a temporary directory to store our JS files
    temp_dir = tempfile.mkdtemp()
    
    # Create the package.json file
    package_json = {
        "name": "token-deployer-temp",
        "version": "1.0.0",
        "description": "Temporary package for token deployment",
        "main": "deploy.js",
        "dependencies": {
            "ethers": "^6.7.1",
            "solc": "^0.8.20",
            "@openzeppelin/contracts": "^4.9.3"
        }
    }
    
    with open(os.path.join(temp_dir, "package.json"), "w") as f:
        json.dump(package_json, f, indent=2)
    
    # Create the deployment script
    deploy_js = """
const solc = require('solc');
const ethers = require('ethers');
const fs = require('fs');
const path = require('path');

// Function to read imported files for solc compiler
function findImports(importPath) {
  try {
    // Remove @openzeppelin prefix and convert to filesystem path
    const normalizedPath = importPath.replace('@openzeppelin/contracts/', '');
    const fullPath = path.join(process.cwd(), 'node_modules', '@openzeppelin', 'contracts', normalizedPath);
    
    if (fs.existsSync(fullPath)) {
      return {
        contents: fs.readFileSync(fullPath, 'utf8')
      };
    } else {
      return { error: `File not found: ${importPath}` };
    }
  } catch (error) {
    return { error: `Error reading file: ${error}` };
  }
}

// Contract template with gas optimization features
const CONTRACT_TEMPLATE = `// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
{{IMPORTS}}

contract {{TOKEN_NAME}} is ERC20, Ownable{{INHERITANCE}} {
    uint8 private immutable _decimals;
    {{VARIABLES}}
    
    // Tax settings
    uint256 public buyTax;
    uint256 public sellTax;
    address public taxWallet;
    
    // Router addresses for tax detection
    mapping(address => bool) public isRouter;
    
    constructor(
        string memory name_,
        string memory symbol_,
        uint8 decimals_,
        uint256 initialSupply_,
        uint256 buyTax_,
        uint256 sellTax_,
        address taxWallet_
    ) 
        ERC20(name_, symbol_)
        Ownable()
        {{CONSTRUCTOR_INITIALIZERS}}
    {
        _decimals = decimals_;
        {{CONSTRUCTOR_BODY}}
        
        // Initialize taxes to 0 - will be set in separate transactions after deployment
        buyTax = 0;
        sellTax = 0;
        
        // Set tax wallet - use provided address or default to msg.sender
        taxWallet = taxWallet_ == address(0) ? msg.sender : taxWallet_;
        
        // Add known router addresses for tax detection
        isRouter[address(0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2)] = true; // WETH
        isRouter[address(0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D)] = true; // Uniswap V2 Router
        isRouter[address(0xE592427A0AEce92De3Edee1F18E0157C05861564)] = true; // Uniswap V3 Router
        isRouter[address(0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270)] = true; // WMATIC
        isRouter[address(0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff)] = true; // QuickSwap Router
        
        _mint(msg.sender, initialSupply_ * 10 ** decimals_);
    }

    function decimals() public view virtual override returns (uint8) {
        return _decimals;
    }
    
    // Override transfer function to apply taxes
    function _transfer(
        address from,
        address to,
        uint256 amount
    ) internal virtual override {
        // Skip taxes for certain addresses or when taxes are zero
        if (from == taxWallet || to == taxWallet || (buyTax == 0 && sellTax == 0)) {
            super._transfer(from, to, amount);
            return;
        }
        
        uint256 taxAmount = 0;
        
        // Apply buy tax when buying from a router (router -> user)
        if (isRouter[from]) {
            // Tax calculation: 1% = 100 basis points, divided by 10000 to get the actual percentage
            taxAmount = amount * buyTax / 10000;
        }
        // Apply sell tax when selling to a router (user -> router)
        else if (isRouter[to]) {
            // Tax calculation: 1% = 100 basis points, divided by 10000 to get the actual percentage
            taxAmount = amount * sellTax / 10000;
        }
        
        // Transfer tax amount to tax wallet if there's any tax
        if (taxAmount > 0) {
            super._transfer(from, taxWallet, taxAmount);
            super._transfer(from, to, amount - taxAmount);
        } else {
            super._transfer(from, to, amount);
        }
    }
    
    // Function to set buy tax - separate transaction after deployment
    function setBuyTax(uint256 newBuyTax) public onlyOwner {
        require(newBuyTax <= 5000, "Tax cannot exceed 50%");
        buyTax = newBuyTax;
    }
    
    // Function to set sell tax - separate transaction after deployment
    function setSellTax(uint256 newSellTax) public onlyOwner {
        require(newSellTax <= 5000, "Tax cannot exceed 50%");
        sellTax = newSellTax;
    }
    
    // Function to update tax settings - combined function
    function setTaxes(uint256 newBuyTax, uint256 newSellTax) public onlyOwner {
        require(newBuyTax <= 5000 && newSellTax <= 5000, "Tax cannot exceed 50%");
        buyTax = newBuyTax;
        sellTax = newSellTax;
    }
    
    // Function to update tax wallet
    function setTaxWallet(address newTaxWallet) public onlyOwner {
        require(newTaxWallet != address(0), "Cannot set to zero address");
        taxWallet = newTaxWallet;
    }
    
    // Function to add or remove router addresses
    function setRouter(address router, bool isActive) public onlyOwner {
        isRouter[router] = isActive;
    }
    
    {{FUNCTIONS}}
}`;

// Feature imports and implementations
const FEATURE_TEMPLATES = {
  Mintable: {
    imports: [],
    inheritance: '',
    variables: '',
    constructorBody: '',
    functions: `
    function mint(address to, uint256 amount) public onlyOwner {
        _mint(to, amount);
    }`,
  },
  Burnable: {
    imports: ['import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol";'],
    inheritance: ', ERC20Burnable',
    variables: '',
    constructorBody: '',
    functions: '',
  },
  Pausable: {
    imports: ['import "@openzeppelin/contracts/security/Pausable.sol";'],
    inheritance: ', Pausable',
    variables: '',
    constructorBody: '',
    functions: `
    function pause() public onlyOwner {
        _pause();
    }

    function unpause() public onlyOwner {
        _unpause();
    }`,
  },
  'Access Control': {
    imports: ['import "@openzeppelin/contracts/access/AccessControl.sol";'],
    inheritance: ', AccessControl',
    variables: `
    bytes32 public constant MINTER_ROLE = keccak256("MINTER_ROLE");
    bytes32 public constant BURNER_ROLE = keccak256("BURNER_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");`,
    constructorBody: `
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(MINTER_ROLE, msg.sender);
        _grantRole(BURNER_ROLE, msg.sender);
        _grantRole(PAUSER_ROLE, msg.sender);`,
    functions: `
    function mint(address to, uint256 amount) public onlyRole(MINTER_ROLE) {
        _mint(to, amount);
    }

    function burn(address from, uint256 amount) public onlyRole(BURNER_ROLE) {
        _burn(from, amount);
    }
    
    function pause() public onlyRole(PAUSER_ROLE) {
        _pause();
    }
    
    function unpause() public onlyRole(PAUSER_ROLE) {
        _unpause();
    }`,
  },
  'Flash Minting': {
    imports: ['import "@openzeppelin/contracts/token/ERC20/extensions/ERC20FlashMint.sol";'],
    inheritance: ', ERC20FlashMint',
    variables: '',
    constructorBody: '',
    functions: '',
  },
};

// Gas optimization settings
const OPTIMIZATION_SETTINGS = {
  none: {
    enabled: false,
    runs: 200,
  },
  standard: {
    enabled: true,
    runs: 200,
  },
  high: {
    enabled: true,
    runs: 1000,
  },
};

// Helper function to generate contract code
function generateContractCode(contractDetails) {
  const {
    name,
    symbol,
    decimals = '18',
    totalSupply,
    features = [],
    optimizationLevel = 'standard',
    buyTax = 0,
    sellTax = 0,
  } = contractDetails;

  console.log('Generating contract code...');
  let imports = [];
  let inheritance = '';
  let variables = '';
  let constructorBody = '';
  let functions = '';

  // Add selected features
  console.log('Adding selected features:', features);
  
  // Extract feature names for easier processing
  const featureNames = [];
  features.forEach((feature) => {
    // Handle both string features and object features
    let featureName = feature;
    
    // If feature is an object with a type property, use that
    if (typeof feature === 'object' && feature !== null) {
      if (feature.type) {
        featureName = feature.type;
      } else if (feature.name) {
        featureName = feature.name;
      }
      // Only use enabled features if that property exists
      if (feature.enabled === false) {
        return; // Skip disabled features
      }
    }
    
    // Convert to string in case it's not already
    featureName = String(featureName);
    featureNames.push(featureName);
  });
  
  // Process features in a specific order to handle dependencies
  const orderedFeatures = ['Access Control', 'Pausable', 'Burnable', 'Mintable', 'Flash Minting'];
  
  // Sort features based on defined order
  const sortedFeatures = featureNames.sort((a, b) => {
    const indexA = orderedFeatures.indexOf(a);
    const indexB = orderedFeatures.indexOf(b);
    // If feature is not in the orderedFeatures list, push it to the end
    if (indexA === -1) return 1;
    if (indexB === -1) return -1;
    return indexA - indexB;
  });

  // Special case: If both Access Control and Pausable are selected, modify the Pausable implementation
  const hasAccessControl = sortedFeatures.includes('Access Control');
  const hasPausable = sortedFeatures.includes('Pausable');
  const hasBurnable = sortedFeatures.includes('Burnable');
  const hasMintable = sortedFeatures.includes('Mintable');
  
  // Create a custom function map to avoid duplications for multiple features
  const resolvedFunctions = new Map();
  
  // Process each feature
  sortedFeatures.forEach((featureName) => {
    const template = FEATURE_TEMPLATES[featureName];
    if (template) {
      // Deduplicate imports and avoid duplicate Ownable
      template.imports.forEach(importStatement => {
        if (!imports.includes(importStatement)) {
          imports.push(importStatement);
        }
      });
      
      // Avoid duplicate inheritance
      if (template.inheritance && !inheritance.includes(template.inheritance)) {
        inheritance += template.inheritance;
      }
      
      variables += template.variables;
      constructorBody += template.constructorBody;
      
      // Special handling for combinations of features
      if (featureName === 'Pausable' && hasAccessControl) {
        // Skip the pause/unpause functions as they're already included in Access Control
        const pauseFunc = `
    function pause() public onlyRole(PAUSER_ROLE) {
        _pause();
    }`;
        
        const unpauseFunc = `
    function unpause() public onlyRole(PAUSER_ROLE) {
        _unpause();
    }`;
        
        resolvedFunctions.set('pause', pauseFunc);
        resolvedFunctions.set('unpause', unpauseFunc);
      } else if (featureName === 'Access Control') {
        // For Access Control - special handling based on which other features are present
        const accessControlFunctions = template.functions.trim();
        
        // Split into individual functions and process
        const functions = accessControlFunctions.split('function');
        for (let i = 1; i < functions.length; i++) {
          const func = 'function' + functions[i];
          
          // Skip mint function if Mintable isn't selected (to avoid duplication)
          if (func.includes('mint(') && !hasMintable) {
            continue;
          }
          
          // Skip burn function if Burnable isn't selected
          if (func.includes('burn(') && !hasBurnable) {
            continue;
          }
          
          // Skip pause/unpause if Pausable isn't selected
          if ((func.includes('pause()') || func.includes('unpause()')) && !hasPausable) {
            continue;
          }
          
          // Skip _beforeTokenTransfer for now
          if (func.includes('_beforeTokenTransfer')) {
            continue;
          }
          
          const funcName = func.substring(9, func.indexOf('(')).trim();
          resolvedFunctions.set(funcName, func);
        }
      } else {
        // For other features or when there are no special combinations
        const featureFunctions = template.functions.trim();
        if (featureFunctions) {
          const functions = featureFunctions.split('function');
          for (let i = 1; i < functions.length; i++) {
            const func = 'function' + functions[i];
            
            // Skip _beforeTokenTransfer - we'll handle it separately
            if (func.includes('_beforeTokenTransfer')) {
              continue;
            }
            
            const funcName = func.substring(9, func.indexOf('(')).trim();
            resolvedFunctions.set(funcName, func);
          }
        }
      }
    }
  });
  
  // Now add the _beforeTokenTransfer function with correct implementation 
  // based on OpenZeppelin's actual implementation
  if (hasPausable) {
    const beforeTokenTransferFunc = `
    function _beforeTokenTransfer(
        address from,
        address to,
        uint256 amount
    ) internal virtual override whenNotPaused {
        super._beforeTokenTransfer(from, to, amount);
    }`;
    
    resolvedFunctions.set('_beforeTokenTransfer', beforeTokenTransferFunc);
  }
  
  // Combine all the resolved functions
  functions = Array.from(resolvedFunctions.values()).join('\\n\\n    ');
  
  // Replace placeholders
  const tokenName = name.replace(/\\s+/g, '');
  
  // Build proper constructor inheritance as separate initializers
  let constructorInitializers = '';
  if (hasAccessControl) {
    constructorInitializers += 'AccessControl()\\n        ';
  }
  if (hasPausable) {
    constructorInitializers += 'Pausable()\\n        ';
  }
  
  const contractCode = CONTRACT_TEMPLATE
    .replace('{{IMPORTS}}', imports.join('\\n'))
    .replace(/{{TOKEN_NAME}}/g, tokenName)
    .replace('{{TOKEN_SYMBOL}}', symbol)
    .replace('{{INHERITANCE}}', inheritance)
    .replace('{{VARIABLES}}', variables)
    .replace('{{CONSTRUCTOR_BODY}}', constructorBody)
    .replace('{{FUNCTIONS}}', functions)
    .replace('{{CONSTRUCTOR_INITIALIZERS}}', constructorInitializers);

  return contractCode;
}

// Compile the contract
async function compileContract(contractCode, name, optimizationLevel = 'standard') {
  console.log('Compiling contract...');
  
  const tokenName = name.replace(/\\s+/g, '');
  
  // Prepare compiler input
  const input = {
    language: 'Solidity',
    sources: {
      'Token.sol': {
        content: contractCode,
      },
    },
    settings: {
      optimizer: OPTIMIZATION_SETTINGS[optimizationLevel],
      outputSelection: {
        '*': {
          '*': ['*'],
        },
      },
    },
  };

  try {
    // Compile the contract
    const output = JSON.parse(solc.compile(JSON.stringify(input), { import: findImports }));
    
    // Check for compilation errors
    if (output.errors?.length > 0) {
      const errors = output.errors.map((error) => ({
        severity: error.severity,
        message: error.message,
        source: error.sourceLocation?.file,
        line: error.sourceLocation?.start,
      }));

      const hasError = errors.some((error) => error.severity === 'error');
      if (hasError) {
        console.error('Compilation failed with errors');
        return { success: false, errors };
      }
    }

    // Extract compiled contract data
    const contract = output.contracts?.['Token.sol']?.[tokenName];
    if (!contract) {
      console.error('No contract output found');
      return { 
        success: false, 
        error: 'Failed to compile contract - no output found' 
      };
    }

    console.log('Successfully compiled contract');
    return {
      success: true,
      abi: contract.abi,
      bytecode: contract.evm.bytecode.object
    };
  } catch (error) {
    console.error('Compilation error:', error);
    return {
      success: false,
      error: error.message || 'Unknown compilation error'
    };
  }
}

// Deploy the contract
async function deployContract(bytecode, abi, constructorArgs, privateKey, rpcUrl) {
  try {
    console.log('Deploying contract...');
    
    // Create provider and wallet
    const provider = new ethers.JsonRpcProvider(rpcUrl);
    const wallet = new ethers.Wallet(privateKey, provider);
    
    // Create contract factory
    const factory = new ethers.ContractFactory(abi, bytecode, wallet);
    
    // Get current gas prices
    const feeData = await provider.getFeeData();
    const maxFeePerGas = feeData.maxFeePerGas || undefined;
    const maxPriorityFeePerGas = feeData.maxPriorityFeePerGas || undefined;
    
    // Deploy with gas optimization
    console.log('Sending deployment transaction...');
    const contract = await factory.deploy(...constructorArgs, {
      maxFeePerGas,
      maxPriorityFeePerGas
    });
    
    // Wait for deployment
    console.log('Waiting for deployment confirmation...');
    const receipt = await contract.deploymentTransaction().wait();
    
    console.log('Contract deployed successfully:', contract.target);
    return {
      success: true,
      address: contract.target,
      txHash: receipt.hash,
      blockNumber: receipt.blockNumber,
      gasUsed: receipt.gasUsed.toString()
    };
  } catch (error) {
    console.error('Deployment error:', error);
    return {
      success: false,
      error: error.message || 'Unknown deployment error'
    };
  }
}

// Set tax values after deployment
async function setTaxRates(contractAddress, abi, privateKey, rpcUrl, buyTax, sellTax) {
  try {
    if (buyTax === 0 && sellTax === 0) {
      console.log('No taxes to set, skipping');
      return { success: true, message: 'No taxes to set' };
    }
    
    console.log(`Setting tax rates: Buy ${buyTax}%, Sell ${sellTax}%`);
    
    // Convert percentages to basis points (1% = 100 basis points)
    const buyTaxBasisPoints = Math.floor(buyTax * 100);
    const sellTaxBasisPoints = Math.floor(sellTax * 100);
    
    // Create provider and wallet
    const provider = new ethers.JsonRpcProvider(rpcUrl);
    const wallet = new ethers.Wallet(privateKey, provider);
    
    // Create contract instance
    const contract = new ethers.Contract(contractAddress, abi, wallet);
    
    // Set buy tax if needed
    if (buyTaxBasisPoints > 0) {
      console.log(`Setting buy tax to ${buyTaxBasisPoints} basis points`);
      const buyTaxTx = await contract.setBuyTax(buyTaxBasisPoints);
      await buyTaxTx.wait();
      console.log('Buy tax set successfully');
    }
    
    // Set sell tax if needed
    if (sellTaxBasisPoints > 0) {
      console.log(`Setting sell tax to ${sellTaxBasisPoints} basis points`);
      const sellTaxTx = await contract.setSellTax(sellTaxBasisPoints);
      await sellTaxTx.wait();
      console.log('Sell tax set successfully');
    }
    
    return {
      success: true,
      buyTaxSet: buyTaxBasisPoints > 0,
      sellTaxSet: sellTaxBasisPoints > 0
    };
  } catch (error) {
    console.error('Error setting tax rates:', error);
    return {
      success: false,
      error: error.message || 'Unknown error setting tax rates'
    };
  }
}

// Main function
async function main() {
  try {
    // Read contract details from command line arguments
    const contractDetailsJson = process.argv[2];
    const contractDetails = JSON.parse(contractDetailsJson);
    
    const { 
      privateKey,
      rpcUrl,
      name,
      symbol,
      decimals = '18',
      totalSupply,
      features = [],
      optimizationLevel = 'standard',
      buyTax = 0,
      sellTax = 0,
      taxWallet = '', // Get tax wallet address if provided
    } = contractDetails;
    
    // Generate contract code
    const contractCode = generateContractCode(contractDetails);
    
    // Compile the contract
    const compilationResult = await compileContract(contractCode, name, optimizationLevel);
    
    if (!compilationResult.success) {
      console.error('Compilation failed:', compilationResult.errors || compilationResult.error);
      process.exit(1);
    }
    
    // Convert tax wallet address to zero address if empty
    const taxWalletAddress = taxWallet ? taxWallet : '0x0000000000000000000000000000000000000000';
    
    // Prepare constructor arguments
    const tokenDecimals = parseInt(decimals) || 18;
    const constructorArgs = [
      name,
      symbol,
      tokenDecimals,
      totalSupply,
      0, // Initial buyTax is 0, will be set in a separate transaction
      0, // Initial sellTax is 0, will be set in a separate transaction
      taxWalletAddress // Add tax wallet address parameter
    ];
    
    // Deploy the contract
    const deploymentResult = await deployContract(
      compilationResult.bytecode, 
      compilationResult.abi, 
      constructorArgs,
      privateKey,
      rpcUrl
    );
    
    if (!deploymentResult.success) {
      console.error('Deployment failed:', deploymentResult.error);
      process.exit(1);
    }
    
    // Set tax rates if needed
    if (buyTax > 0 || sellTax > 0) {
      const taxResult = await setTaxRates(
        deploymentResult.address,
        compilationResult.abi,
        privateKey,
        rpcUrl,
        buyTax,
        sellTax
      );
      
      if (!taxResult.success) {
        console.warn('Warning: Failed to set tax rates:', taxResult.error);
      }
    }
    
    // Return the result as JSON
    const result = {
      success: true,
      contractCode,
      abi: compilationResult.abi,
      bytecode: compilationResult.bytecode,
      deployedContract: {
        address: deploymentResult.address,
        txHash: deploymentResult.txHash,
        blockNumber: deploymentResult.blockNumber,
        gasUsed: deploymentResult.gasUsed,
      },
      taxSettings: {
        buyTax,
        sellTax,
        buyTaxBasisPoints: Math.floor(buyTax * 100),
        sellTaxBasisPoints: Math.floor(sellTax * 100)
      }
    };
    
    console.log(JSON.stringify(result));
    process.exit(0);
  } catch (error) {
    console.error('Error:', error);
    console.log(JSON.stringify({
      success: false,
      error: error.message || 'Unknown error'
    }));
    process.exit(1);
  }
}

main();
    """
    
    # Write the deployment script to the temporary directory
    with open(os.path.join(temp_dir, "deploy.js"), "w") as f:
        f.write(deploy_js)
    
    return temp_dir

def deploy_contract_with_js(contract_data, private_key, rpc_url):
    """
    Deploys a contract using Node.js and the JavaScript deployment script.
    
    Args:
        contract_data (dict): Contract details
        private_key (str): Private key for deployment
        rpc_url (str): RPC URL for the network
        
    Returns:
        dict: Deployment result
    """
    try:
        # Create deployment data
        deployment_data = {
            "name": contract_data["name"],
            "symbol": contract_data["symbol"],
            "decimals": contract_data.get("decimals", 18),
            "totalSupply": contract_data["total_supply"],
            "features": contract_data.get("features", []),
            "optimizationLevel": "standard",
            "buyTax": contract_data.get("buy_tax", 0) / 100,  # Convert from basis points to percentage
            "sellTax": contract_data.get("sell_tax", 0) / 100,  # Convert from basis points to percentage
            "taxWallet": contract_data.get("tax_wallet", ""),  # Add tax wallet address
            "privateKey": private_key,
            "rpcUrl": rpc_url
        }
        
        # Create temporary directory with JS files
        temp_dir = create_js_deployment_file(deployment_data)
        
        # Install dependencies
        print("Installing Node.js dependencies...")
        
        # Check if we have a custom npm path from environment variable
        npm_cmd = os.environ.get("NPM_PATH", "npm")
        
        if npm_cmd != "npm" and os.name == "nt" and npm_cmd.endswith("npm.cmd"):
            # On Windows with a full path to npm.cmd, we need to use PowerShell
            install_process = subprocess.run(
                ["powershell", "-Command", f"& '{npm_cmd}' install"],
                cwd=temp_dir,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        else:
            # Standard npm command
            install_process = subprocess.run(
                [npm_cmd, "install"], 
                cwd=temp_dir, 
                check=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE
            )
        
        # Run the deployment script
        print("Running deployment script...")
        process = subprocess.run(
            ["node", "deploy.js", json.dumps(deployment_data)],
            cwd=temp_dir,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Parse the output
        try:
            # First, try to find a valid JSON object in the output
            # Sometimes the Node.js script might output logs before the actual JSON result
            stdout = process.stdout.strip()
            # Find the first '{' character (start of JSON)
            json_start = stdout.find('{')
            if json_start >= 0:
                json_str = stdout[json_start:]
                result = json.loads(json_str)
                return result
            else:
                # If no JSON found, check if there's a contract address in the output
                # This is a fallback in case the JSON parsing fails but deployment succeeded
                if "Contract deployed successfully:" in stdout:
                    address_line = [line for line in stdout.split('\n') if "Contract deployed successfully:" in line][0]
                    contract_address = address_line.split(":")[-1].strip()
                    return {
                        "success": True,
                        "contractAddress": contract_address,
                        "message": "Contract deployed but JSON parsing failed",
                        "stdout": stdout,
                        "stderr": process.stderr
                    }
                else:
                    print("Error parsing deployment result:", stdout)
                    return {
                        "success": False,
                        "error": "Failed to parse deployment result",
                        "stdout": stdout,
                        "stderr": process.stderr
                    }
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            print("Output:", process.stdout)
            
            # Check if we can find the contract address in the output
            if "Contract deployed successfully:" in process.stdout:
                try:
                    address_line = [line for line in process.stdout.split('\n') if "Contract deployed successfully:" in line][0]
                    contract_address = address_line.split(":")[-1].strip()
                    return {
                        "success": True,
                        "contractAddress": contract_address,
                        "message": "Contract deployed but JSON parsing failed",
                        "stdout": process.stdout,
                        "stderr": process.stderr
                    }
                except Exception as ex:
                    print(f"Error extracting address: {ex}")
            
            return {
                "success": False,
                "error": f"JSON parsing error: {e}",
                "stdout": process.stdout,
                "stderr": process.stderr
            }
    except subprocess.CalledProcessError as e:
        print(f"Deployment process error: {e}")
        return {
            "success": False,
            "error": f"Deployment process error: {e}",
            "stdout": e.stdout if hasattr(e, 'stdout') else None,
            "stderr": e.stderr if hasattr(e, 'stderr') else None
        }
    except Exception as e:
        print(f"Deployment error: {e}")
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        # Clean up temporary directory (optional - you might want to keep it for debugging)
        # import shutil
        # shutil.rmtree(temp_dir)
        pass 