# FlowMind - AI-Powered Requirements Engineering (Phase 2)

FlowMind is an intelligent requirements engineering platform for extracting, reviewing, managing, and exporting software requirements from documents (PDF, DOCX, PPTX, images).

Phase 2 extends the extraction pipeline with manager-client review workflows, analytics, integrations, and role-based collaboration.

## Highlights

- AI-powered requirements extraction with hybrid heuristic + semantic logic
- Two-phase optimized image pipeline for faster uploads
- Client review portal with approve/reject/modify workflow
- Manager feedback dashboard with analytics and bulk actions
- Requirements workspace with search, filters, editing, and CSV export
- Integration endpoints for JSON/CSV export and external tool workflows
- Role-based access: manager, team head, member, client

## Quick Start

### Windows (PowerShell)

```powershell
cd D:\fyp_phase2\FlowMind
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn flowmind:app --host 127.0.0.1 --port 8000
```

Open: http://127.0.0.1:8000

### Ubuntu / WSL

```bash
cd ~/fyp_phase2/FlowMind
chmod +x setup_ubuntu.sh
./setup_ubuntu.sh
source venv/bin/activate
uvicorn flowmind:app --host 0.0.0.0 --port 8000
```

Open: http://localhost:8000

## Configuration

Create a `.env` file (or copy from `.env.example`) and set values:

```bash
SECRET_KEY=<your-random-secret>
TESSERACT_CMD=/usr/bin/tesseract
FLOWMIND_USE_VLM=true
FLOWMIND_VLM_MODELS=qwen2.5-vl,llava:13b
FLOWMIND_OLLAMA_VLM_MODEL=llava:13b
FLOWMIND_ENABLE_SELF_LEARNING=true

# Optional email settings (client invites/reminders)
MAIL_EMAIL=<your-email>
MAIL_PASSWORD=<app-password>
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
```

Optional Windows setting:

- `LIBREOFFICE_PATH=C:\Program Files\LibreOffice\program\soffice.exe`

## Core Modules

- Upload and extraction pipeline: parse docs, OCR images, extract requirements
- Requirements management: list, search, filter, edit, remove, export
- Review workflow:
	- Client portal (`/client-review`) for feedback and submission
	- Manager dashboard (`/manager-feedback`) for tracking and actions
- Integrations:
	- Export JSON/CSV endpoints
	- Integration logs and service hooks
- Auth and access:
	- JWT auth, Google OAuth support, role-scoped visibility

## Roles and Access

- Manager: full project visibility, client assignment, feedback oversight
- Team Head: team-level visibility and monitoring
- Member: own uploads and requirements scope
- Client: assigned document review and feedback submission only

## Performance Notes

- Optimized two-phase image extraction improves upload responsiveness
- Requirements extraction quality includes confidence/quality scoring
- Deduplication logic targets near-zero duplicate requirements

## Collaboration Workflow

### Push latest code

```bash
cd D:/fyp_phase2/FlowMind
git push -u origin main
```

### Add collaborator (write access)

```bash
gh api -X PUT repos/musa106/fyp_phase2/collaborators/zainkhalid10 -f permission=push
```

### Verify collaborator list

```bash
gh api repos/musa106/fyp_phase2/collaborators --jq ".[].login"
```

## Tech Stack

- Backend: FastAPI, Uvicorn, SQLAlchemy, SQLite
- AI/NLP: LangChain, SentenceTransformers, ChromaDB
- OCR/Images: Tesseract OCR, OpenCV
- Optional VLM: Ollama (Qwen2.5-VL, LLaVA)
- Frontend: HTML/CSS/JavaScript dashboards and portals

## Troubleshooting

- If push fails with `not a git repository`, run commands inside `FlowMind` folder.
- If GitHub auth fails, run `gh auth login -h github.com -p https -w`.
- If server does not start, ensure no old python/uvicorn process is running and verify `.env` values.

## License

FYP academic project. Use and modify for project collaboration and educational purposes.

