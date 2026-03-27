# Contributing to FlowMind

This project is maintained collaboratively for FYP Phase 2.

## Collaboration Model

- Main repository: https://github.com/musa106/fyp_phase2
- Owners/collaborators: musa106, zainkhalid10
- Default branch: main

## Basic Workflow

1. Pull latest main before starting work.
2. Create a feature branch.
3. Commit small, focused changes.
4. Push branch and open a pull request.
5. Merge only after review.

## Git Commands

### 1) Sync local main

```bash
git checkout main
git pull origin main
```

### 2) Create a feature branch

```bash
git checkout -b feature/short-description
```

Examples:
- feature/client-review-bulk-actions
- fix/export-csv-button
- docs/readme-phase2

### 3) Commit changes

```bash
git add -A
git commit -m "feat: short clear summary"
```

Commit types:
- feat: new feature
- fix: bug fix
- docs: documentation update
- refactor: internal code improvement
- chore: maintenance task

### 4) Push branch

```bash
git push -u origin feature/short-description
```

### 5) Open PR

Create a pull request into main with:
- What changed
- Why it changed
- How it was tested

## Direct Push to Main

For urgent docs/hotfix changes only:

```bash
git checkout main
git pull origin main
git add -A
git commit -m "docs: update readme"
git push -u origin main
```

## Code Quality Checklist

Before pushing:
- App runs locally
- No obvious console/runtime errors
- UI changes tested on key pages
- README/docs updated if behavior changed
- Sensitive secrets are not committed

## Learning Maintenance Operations

Run this before major demos or weekly checkpoints to keep self-learning current:

```powershell
cd D:\fyp_phase2\FlowMind
.\run_learning_maintenance.ps1 -NFeedback 50 -BackfillLimit 0
```

If using scheduled automation on Windows:

```powershell
cd D:\fyp_phase2\FlowMind
.\setup_learning_maintenance_task.ps1 -TaskName "FlowMind-LearningMaintenance" -RunTime "02:00"
```

Artifacts are stored in `reports/` and should be used as evidence in evaluation (baseline snapshots, self-learning reports, run summaries).

## Security Rules

- Never commit .env with real credentials.
- Keep secrets in local .env only.
- Use .env.example for shared variable names.

## Conflict Resolution

If branch is behind main:

```bash
git checkout main
git pull origin main
git checkout feature/short-description
git rebase main
```

Then push:

```bash
git push --force-with-lease
```

## Contact

If blocked, coordinate in GitHub issue/PR comments before force-changing shared files.
