import uvicorn
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.db.session import engine, Base, SessionLocal
from backend.db.models import Customer
from backend.db.seed import seed_db
from backend.api.routes import router as api_router
from backend.config import settings

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="RecoverAI — Autonomous Revenue Recovery Backend API",
    description="Simulated fintech revenue recovery platform mock APIs, simulator, and agent orchestrator.",
    version="1.0.0"
)

# CORS configurations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For demo ease
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(api_router, prefix="/api")

@app.on_event("startup")
def on_startup():
    logger.info("Initializing database...")
    Base.metadata.create_all(bind=engine)
    
    # Auto-seed if database is empty
    db = SessionLocal()
    try:
        cust_count = db.query(Customer).count()
        if cust_count == 0:
            logger.info("Database is empty. Seeding initial synthetic datasets...")
            seed_db()
        else:
            logger.info(f"Database contains {cust_count} customer records. Skipping seeding.")
    except Exception as e:
        logger.error(f"Error checking/seeding database on startup: {e}")
    finally:
        db.close()
    
    logger.info("Backend application startup complete.")

@app.get("/health")
def health_check():
    return {"status": "HEALTHY", "db_engine": str(engine.url)}

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
