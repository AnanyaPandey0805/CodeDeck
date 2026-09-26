# CodeDeck – AI‑Assisted Software Development & DevOps Platform

## Overview
CodeDeck is a lightweight, AI‑augmented platform that automates the end‑to‑end software delivery workflow:

1. **Repository analysis** – the backend clones a GitHub repo, runs static analysis and extracts a high‑level description.
2. **AI‑driven Q&A** – developers can ask natural‑language questions about the codebase.
3. **AI‑generated tests** – the system generates a pytest suite that is executed automatically.
4. **Docker build** – a container image is built from the repository.
5. **Kind/Kubernetes deployment** – the image is loaded into a local Kind cluster, deployed and a smoke‑test validates the service.

The UI (React) presents a clean dashboard showing the pipeline status and lets the user trigger each step manually.

## Quick start (local demo)
```bash
# prerequisites
# - Docker Desktop (Windows) running
# - Python 3.11, Node.js, npm

# backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload &

# frontend
cd ../frontend
npm install
npm run dev   # http://localhost:5173
```
Enter a public GitHub repository URL in the UI and follow the steps displayed.

## License
MIT.
