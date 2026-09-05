@echo off
echo Starting RazorOps AI Backend (FastAPI)...
start cmd /k "cd backend && python main.py"

echo Starting RazorOps AI Frontend (Next.js)...
start cmd /k "cd frontend && npm run dev"

echo Both servers are starting!
echo Frontend will be available at http://localhost:3000
echo Backend API available at http://localhost:8000
