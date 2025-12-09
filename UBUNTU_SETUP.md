# FlowMind - Ubuntu/WSL Setup Guide

This guide will help you set up and run FlowMind in your Ubuntu/WSL environment.

## Prerequisites

- WSL with Ubuntu (18.04 or later)
- Internet connection for downloading dependencies
- At least 4GB of free disk space

## Quick Setup

Run the automated setup script:

```bash
chmod +x setup_ubuntu.sh
./setup_ubuntu.sh
```

Or follow the manual steps below.

---

## Manual Setup Steps

### 1. Update System Packages

```bash
sudo apt update && sudo apt upgrade -y
```

### 2. Install Python 3.9+ and Dependencies

```bash
# Install Python and pip
sudo apt install -y python3 python3-pip python3-venv python3-dev

# Verify Python version (should be 3.9+)
python3 --version
```

### 3. Install System Dependencies

```bash
# Install Tesseract OCR
sudo apt install -y tesseract-ocr libtesseract-dev

# Install OpenCV dependencies
# For Ubuntu 22.04+ use libgl1, for older versions use libgl1-mesa-glx
sudo apt install -y libgl1 libglib2.0-0
# OR for Ubuntu 20.04 and older:
# sudo apt install -y libgl1-mesa-glx libglib2.0-0

# Install other build dependencies
sudo apt install -y build-essential libssl-dev libffi-dev curl git
```

### 4. Create Python Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip
```

### 5. Install Python Dependencies

```bash
pip install -r requirements.txt
```

This will install all required packages including:
- FastAPI & Uvicorn (web framework)
- SQLAlchemy (database)
- LangChain & ChromaDB (AI/ML)
- Tesseract, Pillow, OpenCV (image processing)
- PyPDF, python-docx, python-pptx (document processing)
- And more...

### 6. Install Ollama (Optional but Recommended)

Ollama provides local LLM capabilities for enhanced image analysis.

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull recommended models (this may take time)
ollama pull llava:13b    # For image analysis (VLM)
ollama pull llama3:8b    # For text finalization

# Verify Ollama is running
curl http://localhost:11434/api/tags
```

**Note**: If you don't install Ollama, FlowMind will still work but without advanced image analysis features.

### 7. Create Environment Configuration

Create a `.env` file in the project root:

```bash
cat > .env << 'EOF'
# Secret key for JWT tokens (change this to a random string)
SECRET_KEY=your-secret-key-change-this-to-random-string

# Tesseract OCR path (usually auto-detected on Linux)
TESSERACT_CMD=/usr/bin/tesseract

# VLM (Visual Language Model) Configuration
FLOWMIND_USE_VLM=true
FLOWMIND_VLM_MODELS=llava:13b,llava:latest
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

# Generate a secure secret key
echo "SECRET_KEY=$(openssl rand -hex 32)" > .env.tmp
cat .env | grep -v "^SECRET_KEY=" >> .env.tmp
mv .env.tmp .env

echo ".env file created!"
```

### 8. Initialize Database

```bash
# Create necessary directories
mkdir -p uploads chroma_db

# Initialize the database (will be created automatically on first run)
python3 -c "from database import init_db; init_db(); print('Database initialized!')"
```

### 9. Run the Application

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Run the server with uvicorn
uvicorn flowmind:app --host 0.0.0.0 --port 8000
```

The application will be available at:
- **Main app**: http://localhost:8000
- **API docs**: http://localhost:8000/docs

### 10. Access from Windows Browser

Since you're using WSL, you can access the app from your Windows browser:

1. Find your WSL IP address:
   ```bash
   hostname -I
   ```

2. Or simply use:
   - http://localhost:8000 (usually works directly)
   - http://127.0.0.1:8000

---

## Testing the Setup

1. Open your browser to http://localhost:8000
2. You should see the FlowMind landing page
3. Click "Sign Up" to create an account
4. Upload a test document (PDF, DOCX, or PPTX)
5. View the extraction results

---

## Troubleshooting

### Issue: Python version too old
```bash
# Install Python 3.9+ from deadsnakes PPA (Ubuntu 18.04/20.04)
sudo apt install software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.9 python3.9-venv python3.9-dev
```

### Issue: Tesseract not found
```bash
# Verify Tesseract installation
which tesseract
tesseract --version

# If not found, reinstall
sudo apt install -y tesseract-ocr
```

### Issue: Ollama not running
```bash
# Check Ollama status
systemctl status ollama

# Start Ollama manually if needed
ollama serve &
```

### Issue: Port 8000 already in use
```bash
# Find what's using port 8000
sudo lsof -i :8000

# Run on a different port
uvicorn flowmind:app --host 0.0.0.0 --port 8001
```

### Issue: Permission denied errors
```bash
# Fix directory permissions
chmod 755 uploads chroma_db
sudo chown -R $USER:$USER .
```

### Issue: ChromaDB errors
```bash
# Remove and reinitialize ChromaDB
rm -rf chroma_db
mkdir chroma_db
```

---

## Running in Production

For production deployment with auto-restart and multiple workers:

```bash
# Install process manager
pip install supervisor

# Or use systemd service (see SYSTEMD_SERVICE.md)
```

---

## Stopping the Application

Press `Ctrl+C` in the terminal where the server is running.

To deactivate the virtual environment:
```bash
deactivate
```

---

## Updating the Application

```bash
# Activate virtual environment
source venv/bin/activate

# Pull latest changes (if using git)
git pull

# Update dependencies
pip install -r requirements.txt --upgrade

# Restart the application
python3 flowmind.py
```

---

## Directory Structure

```
FlowMind/
├── flowmind.py           # Main application
├── database.py           # Database models
├── auth.py              # Authentication
├── rag_agent.py         # AI agent
├── image_parser.py      # Image processing
├── requirements.txt     # Python dependencies
├── .env                 # Environment configuration
├── routes/              # API routes
├── services/            # Service layer
├── static/              # HTML files
├── utils/               # Utilities
├── uploads/             # Uploaded files (created)
├── chroma_db/          # Vector database (created)
├── flowmind.db         # SQLite database (created)
└── venv/               # Virtual environment (created)
```

---

## Additional Configuration

### Enable CORS for Remote Access

If you want to access from other devices on your network, modify `flowmind.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Be cautious in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Configure Ollama Models

```bash
# List available models
ollama list

# Pull additional models
ollama pull llava:34b     # Larger, more accurate
ollama pull llama3.1:8b   # Latest version
```

---

## Performance Tips

1. **Use SSD storage** for ChromaDB directory for faster embeddings
2. **Increase RAM** allocated to WSL (via .wslconfig in Windows)
3. **Use GPU** if available (requires CUDA setup)
4. **Disable telemetry** (already configured in code)

---

## Security Notes

- Change the `SECRET_KEY` in `.env` to a random string
- Use strong passwords for user accounts
- Don't expose the server to the internet without proper security
- Keep dependencies updated regularly

---

## Getting Help

- Check `ERRORS_AND_ISSUES.md` for known issues
- Check `FIXES_APPLIED.md` for recent fixes
- Review `FUNCTION_REFERENCE.md` for API documentation
- Check application logs for error messages

---

## WSL-Specific Tips

### Accessing WSL Files from Windows
Navigate to: `\\wsl$\Ubuntu\home\<your-username>\FlowMind`

### Setting WSL Memory Limits
Create `C:\Users\<YourUser>\.wslconfig`:

```ini
[wsl2]
memory=4GB
processors=2
```

### Restarting WSL
From Windows PowerShell:
```powershell
wsl --shutdown
```

Then reopen your WSL terminal.

---

## Success!

Once everything is set up, you should be able to:
- Upload documents (PDF, DOCX, PPTX)
- Extract requirements automatically
- Use AI-powered analysis
- Track training progress
- View document summaries

Enjoy using FlowMind! 🚀

