#!/bin/bash

# AI Project Launcher - Unified Mode
# Launch script for the Unified AI Project Launcher application

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Function to print colored output
print_color() {
    echo -e "${1}${2}${NC}"
}

# Print banner
print_color $PURPLE "
🚀 AI Project Launcher - Unified Mode
====================================
"

# Check if we're in the right directory
if [ ! -f "unified_launcher.py" ]; then
    print_color $RED "❌ Error: unified_launcher.py not found!"
    print_color $YELLOW "   Please run this script from the AI Launcher directory."
    exit 1
fi

# Check if config file exists
if [ ! -f "config.json" ]; then
    print_color $RED "❌ Error: config.json not found!"
    print_color $YELLOW "   Please ensure the configuration file exists."
    exit 1
fi

# Check Python availability
if ! command -v python3 &> /dev/null; then
    print_color $RED "❌ Error: python3 is not installed or not in PATH"
    exit 1
fi

# Check if Ollama is running
print_color $BLUE "🔍 Checking Ollama availability..."
if ! command -v ollama &> /dev/null; then
    print_color $YELLOW "⚠️  Warning: Ollama not found in PATH"
    print_color $YELLOW "   AI descriptions may not work without Ollama"
else
    # Test if Ollama is responsive
    if timeout 5s ollama list &> /dev/null; then
        print_color $GREEN "✅ Ollama is running and responsive"
        
        # Check for required models
        if ollama list | grep -q "granite3.1-dense:8b" && ollama list | grep -q "granite-code:8b"; then
            print_color $GREEN "✅ Required Granite models found"
        else
            print_color $YELLOW "⚠️  Warning: Some Granite models may be missing"
            print_color $YELLOW "   Run: ollama pull granite3.1-dense:8b && ollama pull granite-code:8b"
        fi
    else
        print_color $YELLOW "⚠️  Warning: Ollama appears to be installed but not responding"
        print_color $YELLOW "   Try running: ollama serve"
    fi
fi

# Check dependencies
print_color $BLUE "🔍 Checking Python dependencies..."
missing_deps=()

if ! python3 -c "import gradio" &> /dev/null; then
    missing_deps+=("gradio")
fi

if ! python3 -c "import PIL" &> /dev/null; then
    missing_deps+=("Pillow")
fi

if [ ${#missing_deps[@]} -ne 0 ]; then
    print_color $RED "❌ Missing Python dependencies: ${missing_deps[*]}"
    print_color $YELLOW "   Install with: pip install ${missing_deps[*]}"
    
    read -p "Would you like to install missing dependencies now? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_color $BLUE "📦 Installing dependencies..."
        pip install "${missing_deps[@]}"
        print_color $GREEN "✅ Dependencies installed"
    else
        print_color $YELLOW "⚠️  Continuing without installing dependencies (may cause errors)"
    fi
else
    print_color $GREEN "✅ All Python dependencies found"
fi

# Kill any existing instances
print_color $BLUE "🔍 Checking for existing launcher instances..."

# Check for any launcher processes
EXISTING_PROCESSES=$(pgrep -f "unified_launcher.py\|persistent_launcher.py\|enhanced_launcher.py" | wc -l)

if [ "$EXISTING_PROCESSES" -gt 0 ]; then
    print_color $YELLOW "⚠️  Found $EXISTING_PROCESSES existing launcher process(es)"
    
    # Show which ports are in use
    if command -v lsof &> /dev/null; then
        USED_PORTS=$(lsof -i :7870-7880 -t 2>/dev/null | wc -l)
        if [ "$USED_PORTS" -gt 0 ]; then
            print_color $YELLOW "📱 Ports 7870-7880 in use: $USED_PORTS"
            lsof -i :7870-7880 2>/dev/null | grep LISTEN | head -3
        fi
    fi
    
    read -p "Kill existing processes and continue? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        pkill -f "unified_launcher.py" 2>/dev/null
        pkill -f "persistent_launcher.py" 2>/dev/null
        pkill -f "enhanced_launcher.py" 2>/dev/null
        print_color $GREEN "✅ Stopped existing processes"
        sleep 3
    else
        print_color $YELLOW "❌ Exiting to avoid conflicts"
        exit 1
    fi
fi

# Display configuration
print_color $BLUE "📁 Configuration:"
if command -v jq &> /dev/null; then
    echo "   Indexed directories:"
    jq -r '.index_directories[]' config.json | sed 's/^/     - /'
else
    echo "   Config file: config.json"
fi

print_color $GREEN "
🚀 Starting Unified AI Project Launcher...
📱 Web interface will be available at: http://localhost:7870-7880 (first available port)
💡 Features enabled:
   - Tabbed interface (App List + Database Viewer)
   - Automatic project discovery
   - Environment detection (conda, venv, poetry, etc.)
   - AI-powered project descriptions (if Ollama available)
   - One-click project launching
   - Visual project icons
   - Real-time search and filtering
   - Complete database inspection tools
   - Command-line arguments support (--verbose, --port, etc.)

Press Ctrl+C to stop the launcher
"

# Change to script directory
cd "$(dirname "$0")"

# Launch the application
if [ -f "unified_launcher.py" ]; then
    print_color $BLUE "🚀 Launching Unified AI Launcher (with tabs and all features)..."
    exec python3 unified_launcher.py
elif [ -f "persistent_launcher.py" ]; then
    print_color $YELLOW "⚠️  Unified launcher not found, using persistent launcher..."
    exec python3 persistent_launcher.py
else
    print_color $YELLOW "⚠️  No launcher found, using enhanced launcher..."
    exec python3 enhanced_launcher.py
fi 