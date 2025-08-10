# =====================================
# backend/main.py - Entry Point
# =====================================
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

from api.auth import router as auth_router
from api.wallet import router as wallet_router
from database.supabase_client import get_supabase_client

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - verificar conexão com Supabase
    try:
        supabase = get_supabase_client()
        print("✅ Supabase connection successful")
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        raise
    
    yield
    
    # Shutdown
    print("🔄 Shutting down ProductiveCasino API")

app = FastAPI(
    title="Produtividade-Casino API",
    description="Gamified productivity system with betting mechanics",
    version="1.0.0",
    lifespan=lifespan
)

# CORS para desenvolvimento (Flask frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5000"],  # Flask dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers - Desacoplamento
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(wallet_router, prefix="/api/wallet", tags=["Wallet"])

@app.get("/")
def root():
    return {
        "message": "🎰 ProductiveCasino API is running!",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "ProductiveCasino"}