import json
import os
from contract_bridge import create_js_deployment_file

def test_js_file_creation():
    """Test that the JavaScript deployment file is created correctly"""
    print("Testing JavaScript file creation...")
    
    # Sample contract data
    contract_data = {
        "name": "Test Token",
        "symbol": "TEST",
        "decimals": 18,
        "totalSupply": 1000000,
        "features": ["Mintable", "Burnable"],
        "optimizationLevel": "standard",
        "buyTax": 2.5,  # 2.5%
        "sellTax": 3.5,  # 3.5%
        "privateKey": "0x0000000000000000000000000000000000000000000000000000000000000000",
        "rpcUrl": "https://polygon-rpc.com"
    }
    
    # Create the JavaScript files
    temp_dir = create_js_deployment_file(contract_data)
    
    # Check if the files were created
    package_json_path = os.path.join(temp_dir, "package.json")
    deploy_js_path = os.path.join(temp_dir, "deploy.js")
    
    if os.path.exists(package_json_path):
        print(f"✅ package.json created at {package_json_path}")
        
        # Check the content of package.json
        with open(package_json_path, "r") as f:
            package_json = json.load(f)
            print(f"  - Dependencies: {', '.join(package_json.get('dependencies', {}).keys())}")
    else:
        print("❌ package.json not created")
    
    if os.path.exists(deploy_js_path):
        print(f"✅ deploy.js created at {deploy_js_path}")
        
        # Check the file size
        file_size = os.path.getsize(deploy_js_path)
        print(f"  - File size: {file_size} bytes")
    else:
        print("❌ deploy.js not created")
    
    print(f"\nTemporary directory: {temp_dir}")
    print("You can manually check the files or run the deployment script with:")
    print(f"cd {temp_dir} && npm install && node deploy.js '{json.dumps(contract_data)}'")
    
    return temp_dir

if __name__ == "__main__":
    temp_dir = test_js_file_creation() 