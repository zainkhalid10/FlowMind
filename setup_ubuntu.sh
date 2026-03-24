#!/bin/bash

# FlowMind Ubuntu/WSL Setup Script
# This script automates the setup process for FlowMind on Ubuntu/WSL

set -e  # Exit on error

echo "========================================"
echo "FlowMind Ubuntu/WSL Setup Script"
echo "========================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

# Check if running on Ubuntu/Debian
if [ ! -f /etc/debian_version ]; then
    print_error "This script is designed for Ubuntu/Debian systems"
    exit 1
fi

# Check Python version
echo "Step 1: Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    print_success "Python $PYTHON_VERSION found"
else
    print_error "Python 3 not found. Installing..."
    sudo apt update
    sudo apt install -y python3 python3-pip python3-venv python3-dev
fi

# Update system packages
echo ""
echo "Step 2: Updating system packages..."
sudo apt update
print_success "System packages updated"

# Install system dependencies
echo ""
echo "Step 3: Installing system dependencies..."

# Detect Ubuntu version and use appropriate package names
if apt-cache show libgl1-mesa-glx &>/dev/null; then
    LIBGL_PACKAGE="libgl1-mesa-glx"
else
    LIBGL_PACKAGE="libgl1"
fi

sudo apt install -y \
    tesseract-ocr \
    libtesseract-dev \
    $LIBGL_PACKAGE \
    libglib2.0-0 \
    build-essential \
    libssl-dev \
    libffi-dev \
    curl \
    git

print_success "System dependencies installed"

# Verify Tesseract installation
if command -v tesseract &> /dev/null; then
    TESSERACT_VERSION=$(tesseract --version | head -n1)
    print_success "Tesseract OCR installed: $TESSERACT_VERSION"
else
    print_error "Tesseract installation failed"
    exit 1
fi

# Create virtual environment
echo ""
echo "Step 4: Creating Python virtual environment..."
if [ -d "venv" ]; then
    print_warning "Virtual environment already exists, skipping..."
else
    python3 -m venv venv
    print_success "Virtual environment created"
fi

# Activate virtual environment
source venv/bin/activate
print_success "Virtual environment activated"

# Upgrade pip
echo ""
echo "Step 5: Upgrading pip..."
pip install --upgrade pip > /dev/null
print_success "pip upgraded"

# Install Python dependencies
echo ""
echo "Step 6: Installing Python dependencies..."
print_info "This may take a few minutes..."
pip install -r requirements.txt
print_success "Python dependencies installed"

# Create necessary directories
echo ""
echo "Step 7: Creating directories..."
mkdir -p uploads
mkdir -p chroma_db
print_success "Directories created"

# Initialize database
echo ""
echo "Step 8: Initializing database..."
python3 -c "from database import init_db; init_db()"
print_success "Database initialized"

# Create .env file if it doesn't exist
echo ""
echo "Step 9: Creating environment configuration..."
if [ -f ".env" ]; then
    print_warning ".env file already exists, skipping..."
else
    # Generate a random secret key
    SECRET_KEY=$(openssl rand -hex 32)
    
    cat > .env << EOF
# Secret key for JWT tokens
SECRET_KEY=$SECRET_KEY

# Tesseract OCR path (auto-detected on Linux)
TESSERACT_CMD=/usr/bin/tesseract

# VLM (Visual Language Model) Configuration
FLOWMIND_USE_VLM=true
FLOWMIND_VLM_MODELS=qwen2.5-vl,llava:13b
FLOWMIND_OLLAMA_VLM_MODEL=llava:13b
FLOWMIND_OLLAMA_MODEL=llama3:8b
FLOWMIND_VLM_TIMEOUT_MS=12000

# LLM Finalization
FLOWMIND_USE_LLM_FINALIZE=true

# Self-Learning Feature
FLOWMIND_ENABLE_SELF_LEARNING=true

# Optional: Advanced features (disable if causing issues)
FLOWMIND_USE_SPACY=false
FLOWMIND_USE_RERANKER=false

# File upload limits
MAX_FILE_SIZE=52428800

# Optional: OpenRouter API (not required)
# OPENROUTER_API_KEY=your-api-key-here
EOF
    
    print_success ".env file created with random secret key"
fi

# Check if Ollama is installed
echo ""
echo "Step 10: Checking Ollama installation..."
if command -v ollama &> /dev/null; then
    print_success "Ollama is already installed"
    
    # Check if models are available
    if ollama list | grep -q "llava:13b"; then
        print_success "llava:13b model already available"
    else
        print_warning "llava:13b model not found"
        read -p "Do you want to download llava:13b model? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_info "Downloading llava:13b... This may take 10-20 minutes..."
            ollama pull llava:13b
            print_success "llava:13b model downloaded"
        fi
    fi
    
    if ollama list | grep -q "llama3:8b"; then
        print_success "llama3:8b model already available"
    else
        print_warning "llama3:8b model not found"
        read -p "Do you want to download llama3:8b model? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_info "Downloading llama3:8b... This may take 5-10 minutes..."
            ollama pull llama3:8b
            print_success "llama3:8b model downloaded"
        fi
    fi
else
    print_warning "Ollama is not installed"
    read -p "Do you want to install Ollama? (recommended) (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Installing Ollama..."
        curl -fsSL https://ollama.com/install.sh | sh
        print_success "Ollama installed"
        
        # Start Ollama service
        print_info "Starting Ollama service..."
        systemctl start ollama 2>/dev/null || ollama serve > /dev/null 2>&1 &
        sleep 3
        
        # Download models
        print_info "Downloading llava:13b model... This may take 10-20 minutes..."
        ollama pull llava:13b
        print_success "llava:13b model downloaded"
        
        print_info "Downloading llama3:8b model... This may take 5-10 minutes..."
        ollama pull llama3:8b
        print_success "llama3:8b model downloaded"
    else
        print_warning "Skipping Ollama installation. Advanced image analysis features will be limited."
    fi
fi

# Final summary
echo ""
echo "========================================"
echo "Setup Complete! 🚀"
echo "========================================"
echo ""
print_success "All components installed successfully!"
echo ""
echo "To start FlowMind:"
echo "  1. Activate the virtual environment: source venv/bin/activate"
echo "  2. Run the application: python3 flowmind.py"
echo ""
echo "The application will be available at:"
echo "  - http://localhost:8000"
echo "  - API docs: http://localhost:8000/docs"
echo ""
echo "For WSL users:"
echo "  - Access from Windows browser using http://localhost:8000"
echo "  - Or find your WSL IP with: hostname -I"
echo ""
print_info "Check UBUNTU_SETUP.md for troubleshooting and advanced configuration"
echo ""
echo "Quick start command:"
echo "  source venv/bin/activate && python3 flowmind.py"
echo ""

