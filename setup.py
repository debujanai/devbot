import subprocess
import sys
import os
import platform

def check_node_installed():
    """Check if Node.js is installed"""
    try:
        subprocess.run(["node", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def check_npm_installed():
    """Check if npm is installed"""
    try:
        subprocess.run(["npm", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def install_python_dependencies():
    """Install Python dependencies"""
    print("Installing Python dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
    print("✅ Python dependencies installed successfully")

def main():
    """Main setup function"""
    print("🚀 Setting up Token Deployer Bot...")
    
    # Check Python version
    python_version = sys.version_info
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
        print("❌ Python 3.8 or higher is required")
        sys.exit(1)
    
    print("✅ Python version check passed")
    
    # Check Node.js
    if not check_node_installed():
        print("❌ Node.js is not installed. Please install Node.js from https://nodejs.org/")
        sys.exit(1)
    
    print("✅ Node.js is installed")
    
    # Check npm
    if not check_npm_installed():
        print("❌ npm is not installed. Please install npm (usually comes with Node.js)")
        sys.exit(1)
    
    print("✅ npm is installed")
    
    # Install Python dependencies
    try:
        install_python_dependencies()
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install Python dependencies: {e}")
        sys.exit(1)
    
    print("\n✅ Setup completed successfully!")
    print("\nYou can now run the bot with:")
    print("  python main.py")

if __name__ == "__main__":
    main() 