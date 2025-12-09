# FlowMind - Quick Start Guide for WSL Ubuntu

This is a super quick guide to get FlowMind running in your WSL Ubuntu environment in just a few minutes.

## Prerequisites

- WSL with Ubuntu installed
- Internet connection

## Quick Start (Automated)

```bash
# 1. Make the setup script executable
chmod +x setup_ubuntu.sh

# 2. Run the automated setup
./setup_ubuntu.sh

# 3. Start FlowMind
source venv/bin/activate
uvicorn flowmind:app --host 0.0.0.0 --port 8000
```

That's it! Open http://localhost:8000 in your Windows browser.

---

## Quick Start (Using the Run Script)

After setup, you can use the quick-start script:

```bash
# Make run script executable
chmod +x run.sh

# Run FlowMind
./run.sh
```

---

## Manual Quick Start (Step by Step)

If you prefer to do it manually:

```bash
# 1. Update and install system dependencies
sudo apt update
sudo apt install -y python3 python3-pip python3-venv tesseract-ocr libgl1-mesa-glx

# 2. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install Python packages
pip install -r requirements.txt

# 4. Create .env file
cp .env.example .env
# Edit .env and change SECRET_KEY to a random string

# 5. Create directories
mkdir -p uploads chroma_db

# 6. Initialize database
python3 -c "from database import init_db; init_db()"

# 7. (Optional) Install Ollama for AI features
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llava:13b
ollama pull llama3:8b

# 8. Run the application with uvicorn
uvicorn flowmind:app --host 0.0.0.0 --port 8000
```

---

## Accessing FlowMind

From your Windows browser, go to:

- **Main App**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

---

## First Time Usage

1. **Sign Up**: Create a new account at http://localhost:8000
2. **Upload**: Upload a document (PDF, DOCX, or PPTX)
3. **Extract**: Click "Train Agent" to extract requirements
4. **View**: See the extracted requirements organized by category

---

## Stopping FlowMind

Press `Ctrl+C` in the terminal where it's running.

---

## Troubleshooting

### Can't access localhost:8000?

```bash
# Check if the server is running
curl http://localhost:8000

# Or find your WSL IP
hostname -I

# Then access using that IP from Windows
```

### Permission errors?

```bash
sudo chown -R $USER:$USER .
chmod 755 uploads chroma_db
```

### Python packages failing?

```bash
# Make sure you're in the virtual environment
source venv/bin/activate

# Upgrade pip and try again
pip install --upgrade pip
pip install -r requirements.txt
```

### Ollama not working?

Ollama is optional. FlowMind will work without it, but you'll have limited image analysis features.

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama manually if needed
ollama serve
```

---

## What Gets Installed?

**System Packages:**
- Python 3.9+
- Tesseract OCR (for text extraction from images)
- OpenCV dependencies (for image processing)

**Python Packages:**
- FastAPI (web framework)
- SQLAlchemy (database)
- LangChain (AI framework)
- ChromaDB (vector database)
- Various document parsers (PDF, DOCX, PPTX)

**Optional:**
- Ollama (local LLM for enhanced AI features)

**Total Installation Size**: ~2-3 GB (including Ollama models)

---

## Running on Startup

See `SYSTEMD_SERVICE.md` for instructions on running FlowMind as a system service.

---

## Next Steps

- Read `UBUNTU_SETUP.md` for detailed configuration
- Check `TECHNOLOGY_STACK.md` to understand the technology
- Review `FUNCTION_REFERENCE.md` for API documentation

---

## Common Commands

```bash
# Activate virtual environment
source venv/bin/activate

# Run FlowMind with uvicorn
uvicorn flowmind:app --host 0.0.0.0 --port 8000

# Or use the convenience script
./run.sh

# Check if server is running
curl http://localhost:8000

# View application logs
# (logs are shown in the terminal)

# Stop the server
# Press Ctrl+C
```

---

## Need Help?

- Check `ERRORS_AND_ISSUES.md` for known issues
- Check `FIXES_APPLIED.md` for solutions
- Check the console output for error messages

---

## Tips

1. **First run takes longer** - Models need to download and initialize
2. **Use Chrome/Edge** - Best compatibility
3. **Keep WSL updated** - `sudo apt update && sudo apt upgrade`
4. **Allocate enough RAM to WSL** - At least 4GB recommended

---

Enjoy using FlowMind! 🚀

