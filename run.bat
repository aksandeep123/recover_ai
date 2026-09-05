@echo off
echo =======================================================================
echo               RecoverAI Autonomous Revenue Recovery Platform
echo =======================================================================
echo.
echo Starting FastAPI Backend Services...
start "RecoverAI Backend" cmd /k "python -m uvicorn backend.main:app --port 8000"
echo Backend API server launching on http://127.0.0.1:8000
echo.
echo Launching React Frontend Server...
start "RecoverAI Frontend" cmd /k "cd frontend && npm install && npm run dev"
echo.
echo Startup commands successfully dispatched.
echo Backend is loading database and seeding synthetic data.
echo Frontend will install packages (if needed) and run on http://localhost:3000
echo.
echo Press any key to close this installer launcher shell...
pause > nul
