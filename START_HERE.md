# 🚀 FlowMind - Quick Start

## ⚡ TL;DR - Start FlowMind NOW

```bash
# In your WSL Ubuntu terminal:
cd /mnt/c/FlowMind
source venv/bin/activate
uvicorn flowmind:app --host 0.0.0.0 --port 8000
```

Then open: **http://localhost:8000** in your Windows browser

---

## 🔧 The Issue You Had

**Problem**: Running `python3 flowmind.py` just shows "Loaded 0 persisted views" and exits.

**Why**: FlowMind is a FastAPI app that needs to be run with **uvicorn**, not directly with Python.

**Solution**: Use `uvicorn flowmind:app --host 0.0.0.0 --port 8000`

---

## ✅ Correct Commands

### Start the Server

```bash
# Activate virtual environment first
source venv/bin/activate

# Then run with uvicorn
uvicorn flowmind:app --host 0.0.0.0 --port 8000
```

### Or Use the Run Script

```bash
./run.sh
```

### Stop the Server

Press `Ctrl+C` in the terminal

---

## 📍 Your Current Status

Based on your terminal output, you have:
- ✅ Python 3.12.3 installed
- ✅ All system dependencies installed (Tesseract, etc.)
- ✅ Virtual environment created
- ✅ All Python packages installed
- ✅ Database initialized
- ✅ Missing: email-validator (but you installed it)

**You're ready to run!** Just use the correct command above.

---

## 🌐 Accessing FlowMind

Once the server starts, you'll see:
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Then open in your Windows browser:
- **Main App**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Alternative**: http://127.0.0.1:8000

---

## 🎯 First Time Usage

1. **Sign Up**: Create account at http://localhost:8000
2. **Upload**: Upload a document (PDF, DOCX, PPTX)
3. **Train**: Click "Train Agent" to extract requirements
4. **View**: See extracted requirements by category

---

## 🔍 Troubleshooting

### Server won't start?

```bash
# Check if port 8000 is in use
sudo lsof -i :8000

# Or use a different port
uvicorn flowmind:app --host 0.0.0.0 --port 8001
```

### Can't access from browser?

```bash
# Make sure server is running
curl http://localhost:8000

# Check your WSL IP
hostname -I
```

### Module not found errors?

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Reinstall if needed
pip install -r requirements.txt
```

---

## 📚 Documentation

- **QUICK_START_WSL.md** - Quick setup guide
- **UBUNTU_SETUP.md** - Detailed setup with troubleshooting
- **SYSTEMD_SERVICE.md** - Run as background service
- **TECHNOLOGY_STACK.md** - Technical architecture
- **FUNCTION_REFERENCE.md** - API documentation

---

## 💡 Common Commands

```bash
# Activate virtual environment
source venv/bin/activate

# Start server (correct way)
uvicorn flowmind:app --host 0.0.0.0 --port 8000

# Start with auto-reload (for development)
uvicorn flowmind:app --host 0.0.0.0 --port 8000 --reload

# Run in background (detached)
nohup uvicorn flowmind:app --host 0.0.0.0 --port 8000 > flowmind.log 2>&1 &

# Check if running
ps aux | grep uvicorn

# Kill background process
pkill -f uvicorn
```

---

## 🎉 You're All Set!

The message "📚 Loaded 0 persisted views" is **normal** for a fresh installation. It just means you haven't uploaded any documents yet.

Now run the correct command and enjoy FlowMind! 🚀

```bash
uvicorn flowmind:app --host 0.0.0.0 --port 8000
```

