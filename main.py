import time
import subprocess
import sys
import os
from storage import init_data_storage
from bot import bot

def check_dependencies():
    """Check if all required dependencies are installed"""
    node_installed = False
    npm_installed = False
    
    try:
        # Check Node.js
        node_process = subprocess.run(
            ["node", "--version"], 
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        node_version = node_process.stdout.strip()
        print(f"✅ Node.js detected: {node_version}")
        node_installed = True
        
        # Get Node.js path
        node_path = None
        try:
            which_process = subprocess.run(
                ["where", "node"] if os.name == "nt" else ["which", "node"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            node_path = os.path.dirname(which_process.stdout.strip().split("\n")[0])
        except:
            # Try PowerShell on Windows
            if os.name == "nt":
                try:
                    ps_process = subprocess.run(
                        ["powershell", "-Command", "Get-Command node | Select-Object -ExpandProperty Source"],
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    node_path = os.path.dirname(ps_process.stdout.strip())
                except:
                    pass
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Node.js is not installed.")
        print("Please install Node.js from https://nodejs.org/")
    
    try:
        # Check npm
        npm_process = subprocess.run(
            ["npm", "--version"], 
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        npm_version = npm_process.stdout.strip()
        print(f"✅ npm detected: {npm_version}")
        npm_installed = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        # If npm command fails but we have Node.js path, try using npm from there
        if node_installed and node_path:
            npm_cmd = os.path.join(node_path, "npm.cmd" if os.name == "nt" else "npm")
            try:
                if os.name == "nt":
                    # On Windows, we need to use the & operator in PowerShell
                    npm_process = subprocess.run(
                        ["powershell", "-Command", f"& '{npm_cmd}' --version"],
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                else:
                    npm_process = subprocess.run(
                        [npm_cmd, "--version"],
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                npm_version = npm_process.stdout.strip()
                print(f"✅ npm detected: {npm_version} (using full path)")
                npm_installed = True
                
                # Store the npm path for later use
                os.environ["NPM_PATH"] = npm_cmd
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                print(f"❌ npm is not installed or not working: {e}")
                print("npm should be included with Node.js installation.")
        else:
            print("❌ npm is not installed or not in PATH.")
            print("npm should be included with Node.js installation.")
        
    if not node_installed or not npm_installed:
        print("These are required for contract compilation and deployment.")
        return False
        
    return True

if __name__ == "__main__":
    print("🚀 Starting Token Deployer Bot...")

    # Check dependencies
    if not check_dependencies():
        print("❌ Missing required dependencies. Please install them and try again.")
        sys.exit(1)

    # Initialize data storage
    init_data_storage()
    print("✅ Data storage initialized")

    # Set bot commands
    bot.set_my_commands([
        ("start", "Start the bot and show main menu"),
        ("help", "Show help and instructions"),
        ("tokens", "View your created tokens"),
        ("wallet", "Wallet management"),
        ("balance", "Check your wallet balance"),
        ("renounce", "Renounce contract ownership"),
        ("debug", "Show debug information")
    ])

    print("✅ Bot commands set")
    print("🤖 Bot is running...")

    # Remove webhook to avoid conflicts
    bot.remove_webhook()
    time.sleep(0.5)

    # Start polling
    try:
        bot.infinity_polling(none_stop=True, timeout=60)
    except Exception as e:
        print(f"Bot error: {str(e)}")
        print("Bot stopped")
