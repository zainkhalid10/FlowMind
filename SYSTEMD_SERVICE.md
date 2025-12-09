# Running FlowMind as a Systemd Service (Ubuntu/WSL)

This guide shows you how to run FlowMind as a system service that starts automatically.

## Create Service File

1. Create a systemd service file:

```bash
sudo nano /etc/systemd/system/flowmind.service
```

2. Add the following content (replace `YOUR_USERNAME` and adjust paths):

```ini
[Unit]
Description=FlowMind - AI-Powered Requirements Extraction
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/FlowMind
Environment="PATH=/home/YOUR_USERNAME/FlowMind/venv/bin"
ExecStart=/home/YOUR_USERNAME/FlowMind/venv/bin/uvicorn flowmind:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

# Optional: Environment variables
# Environment="SECRET_KEY=your-secret-key"
# Environment="FLOWMIND_USE_VLM=true"

[Install]
WantedBy=multi-user.target
```

3. Replace `YOUR_USERNAME` with your actual username:

```bash
# Get your username
whoami

# Or use this command to create the file automatically:
cat > flowmind.service << EOF
[Unit]
Description=FlowMind - AI-Powered Requirements Extraction
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$(pwd)
Environment="PATH=$(pwd)/venv/bin"
ExecStart=$(pwd)/venv/bin/uvicorn flowmind:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo mv flowmind.service /etc/systemd/system/
```

## Enable and Start Service

```bash
# Reload systemd to recognize new service
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable flowmind

# Start the service now
sudo systemctl start flowmind

# Check service status
sudo systemctl status flowmind
```

## Managing the Service

```bash
# Start the service
sudo systemctl start flowmind

# Stop the service
sudo systemctl stop flowmind

# Restart the service
sudo systemctl restart flowmind

# Check status
sudo systemctl status flowmind

# View logs
sudo journalctl -u flowmind -f

# View recent logs
sudo journalctl -u flowmind --since "10 minutes ago"
```

## Alternative: Using Screen or Tmux

If you prefer not to use systemd, you can use screen or tmux:

### Using Screen

```bash
# Install screen
sudo apt install screen

# Start a new screen session
screen -S flowmind

# Activate venv and run
source venv/bin/activate
uvicorn flowmind:app --host 0.0.0.0 --port 8000

# Detach from screen: Press Ctrl+A, then D

# Reattach to screen
screen -r flowmind

# List all screens
screen -ls
```

### Using Tmux

```bash
# Install tmux
sudo apt install tmux

# Start a new tmux session
tmux new -s flowmind

# Activate venv and run
source venv/bin/activate
uvicorn flowmind:app --host 0.0.0.0 --port 8000

# Detach from tmux: Press Ctrl+B, then D

# Reattach to tmux
tmux attach -t flowmind

# List all sessions
tmux ls
```

## WSL-Specific Notes

### Running on WSL Startup

WSL doesn't use systemd by default in older versions. For WSL 2 with systemd support:

1. Enable systemd in WSL:

Create or edit `/etc/wsl.conf`:

```ini
[boot]
systemd=true
```

2. Restart WSL from PowerShell:

```powershell
wsl --shutdown
```

3. Then follow the systemd instructions above.

### Without Systemd

If your WSL doesn't support systemd, use screen/tmux or create a Windows Task:

1. Create a batch file in Windows (`C:\Users\YourName\start_flowmind.bat`):

```batch
@echo off
wsl -d Ubuntu -u your-username -- bash -c "cd ~/FlowMind && source venv/bin/activate && uvicorn flowmind:app --host 0.0.0.0 --port 8000"
```

2. Use Windows Task Scheduler to run this on startup.

## Troubleshooting

### Service Fails to Start

```bash
# Check detailed logs
sudo journalctl -u flowmind -n 50 --no-pager

# Check if port is already in use
sudo lsof -i :8000

# Verify paths in service file
cat /etc/systemd/system/flowmind.service

# Test manually
cd /path/to/FlowMind
source venv/bin/activate
uvicorn flowmind:app --host 0.0.0.0 --port 8000
```

### Permission Issues

```bash
# Fix ownership
sudo chown -R $(whoami):$(whoami) /path/to/FlowMind

# Fix permissions
chmod 755 /path/to/FlowMind
chmod 644 /path/to/FlowMind/*.py
```

### Environment Variables Not Loading

If using `.env` file, ensure the service file includes:

```ini
EnvironmentFile=/home/YOUR_USERNAME/FlowMind/.env
```

Or explicitly set variables in the service file.

