# =====================================
# backend/main.py - VERSÃO SINGLE FILE PARA TESTE RÁPIDO
# =====================================
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, validator
from supabase import create_client, Client
from contextlib import asynccontextmanager
from typing import Optional, Dict
from datetime import datetime, timedelta
from enum import Enum
import jwt
import bcrypt
import os
from dotenv import load_dotenv

load_dotenv()

# =====================================
# CONFIGURAÇÕES
# =====================================
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-super-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# Supabase client (singleton)
_supabase_client: Optional[Client] = None

def get_supabase_client() -> Client:
    global _supabase_client
    if _supabase_client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_ANON_KEY")
        
        if not url or not key:
            raise ValueError("❌ SUPABASE_URL e SUPABASE_ANON_KEY são obrigatórios no .env")
        
        _supabase_client = create_client(url, key)
    return _supabase_client

# =====================================
# PYDANTIC MODELS
# =====================================
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must have at least 6 characters')
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    created_at: datetime

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class WalletResponse(BaseModel):
    balance: int
    user_id: str
    updated_at: datetime

class ActivityType(str, Enum):
    POMODORO = "pomodoro_25min"
    EXERCISE = "exercise_30min" 
    STUDY = "study_1h"
    DEEP_WORK = "deep_work_2h"

class ActivityCreate(BaseModel):
    activity_type: ActivityType
    duration_minutes: Optional[int] = None
    notes: Optional[str] = None

# =====================================
# UTILITY FUNCTIONS
# =====================================
def hash_password(password: str) -> str:
    """Hash seguro da senha com bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verifica senha contra hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_access_token(user_id: str) -> str:
    """Cria JWT token"""
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.utcnow()
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> Dict:
    """Verifica e decodifica JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise Exception("Token expired")
    except jwt.JWTError:
        raise Exception("Invalid token")

# =====================================
# WALLET CONFIGURATIONS
# =====================================
ACTIVITY_COINS: Dict[ActivityType, int] = {
    ActivityType.POMODORO: 50,
    ActivityType.EXERCISE: 75,
    ActivityType.STUDY: 100,
    ActivityType.DEEP_WORK: 200,
}

STREAK_MULTIPLIERS = {
    3: 1.2,   # 3 dias = 20% bonus
    7: 1.5,   # 7 dias = 50% bonus
    30: 2.0,  # 30 dias = 100% bonus
}

def get_streak_multiplier(streak_days: int) -> float:
    """Retorna multiplicador baseado no streak"""
    for days, multiplier in sorted(STREAK_MULTIPLIERS.items(), reverse=True):
        if streak_days >= days:
            return multiplier
    return 1.0

async def calculate_user_streak(user_id: str) -> int:
    """Calcula streak de dias consecutivos com atividades"""
    supabase = get_supabase_client()
    
    try:
        sixty_days_ago = (datetime.utcnow() - timedelta(days=60)).isoformat()
        
        activities_result = supabase.table('activities')\
            .select('created_at')\
            .eq('user_id', user_id)\
            .gte('created_at', sixty_days_ago)\
            .order('created_at', desc=True)\
            .execute()
        
        if not activities_result.data:
            return 0
        
        # Converter para datas únicas
        activity_dates = set()
        for activity in activities_result.data:
            date_str = activity['created_at'][:10]
            activity_dates.add(date_str)
        
        # Calcular streak consecutivo
        streak = 0
        current_date = datetime.utcnow().date()
        
        while True:
            date_str = current_date.strftime('%Y-%m-%d')
            if date_str in activity_dates:
                streak += 1
                current_date -= timedelta(days=1)
            else:
                break
        
        return streak
        
    except Exception as e:
        print(f"Error calculating streak: {e}")
        return 0

# =====================================
# FASTAPI APP
# =====================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        supabase = get_supabase_client()
        print("✅ Supabase connection successful")
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        raise
    
    yield
    print("🔄 Shutting down ProductiveCasino API")

app = FastAPI(
    title="ProductiveCasino API",
    description="Gamified productivity system with betting mechanics",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# =====================================
# AUTH DEPENDENCIES
# =====================================
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency para rotas protegidas"""
    try:
        payload = verify_token(credentials.credentials)
        user_id = payload.get("sub")
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        supabase = get_supabase_client()
        user_result = supabase.table('users').select('*').eq('id', user_id).execute()
        
        if not user_result.data:
            raise HTTPException(status_code=401, detail="User not found")
        
        return UserResponse(**user_result.data[0])
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")

# =====================================
# ROUTES - BASIC
# =====================================
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

# =====================================
# ROUTES - AUTH
# =====================================
@app.post("/api/auth/register", response_model=TokenResponse)
async def register(user_data: UserCreate):
    """Registra novo usuário"""
    supabase = get_supabase_client()
    
    try:
        # Verificar se email já existe
        existing = supabase.table('users').select('id').eq('email', user_data.email).execute()
        if existing.data:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Hash da senha
        hashed_password = hash_password(user_data.password)
        
        # Criar usuário
        user_result = supabase.table('users').insert({
            'email': user_data.email,
            'password_hash': hashed_password
        }).execute()
        
        if not user_result.data:
            raise HTTPException(status_code=500, detail="Failed to create user")
        
        user = user_result.data[0]
        
        # Criar wallet inicial
        wallet_result = supabase.table('wallets').insert({
            'user_id': user['id'],
            'balance': 100
        }).execute()
        
        if not wallet_result.data:
            supabase.table('users').delete().eq('id', user['id']).execute()
            raise HTTPException(status_code=500, detail="Failed to create wallet")
        
        # Gerar token
        token = create_access_token(user['id'])
        
        return TokenResponse(
            access_token=token,
            user=UserResponse(**user)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@app.post("/api/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    """Login com verificação de senha"""
    supabase = get_supabase_client()
    
    try:
        user_result = supabase.table('users').select('*').eq('email', credentials.email).execute()
        
        if not user_result.data:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        user = user_result.data[0]
        
        if not verify_password(credentials.password, user['password_hash']):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        token = create_access_token(user['id'])
        
        return TokenResponse(
            access_token=token,
            user=UserResponse(**user)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

# =====================================
# ROUTES - WALLET
# =====================================
@app.get("/api/wallet/balance", response_model=WalletResponse)
async def get_balance(current_user: UserResponse = Depends(get_current_user)):
    """Consulta saldo atual"""
    supabase = get_supabase_client()
    
    try:
        wallet_result = supabase.table('wallets').select('*').eq('user_id', current_user.id).execute()
        
        if not wallet_result.data:
            raise HTTPException(status_code=404, detail="Wallet not found")
        
        wallet = wallet_result.data[0]
        return WalletResponse(**wallet)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get balance: {str(e)}")

@app.post("/api/wallet/earn")
async def earn_coins(
    activity: ActivityCreate, 
    current_user: UserResponse = Depends(get_current_user)
):
    """Ganha moedas completando atividades"""
    supabase = get_supabase_client()
    
    try:
        # Calcular moedas
        base_coins = ACTIVITY_COINS[activity.activity_type]
        streak_days = await calculate_user_streak(current_user.id)
        streak_multiplier = get_streak_multiplier(streak_days)
        final_coins = int(base_coins * streak_multiplier)
        
        # Registrar atividade
        activity_result = supabase.table('activities').insert({
            'user_id': current_user.id,
            'activity_type': activity.activity_type.value,
            'coins_earned': final_coins,
            'duration_minutes': activity.duration_minutes,
            'notes': activity.notes,
            'streak_days': streak_days,
            'multiplier_applied': streak_multiplier
        }).execute()
        
        if not activity_result.data:
            raise HTTPException(status_code=500, detail="Failed to record activity")
        
        # Atualizar wallet
        wallet_result = supabase.table('wallets').select('balance').eq('user_id', current_user.id).execute()
        
        if not wallet_result.data:
            raise HTTPException(status_code=404, detail="Wallet not found")
        
        current_balance = wallet_result.data[0]['balance']
        new_balance = current_balance + final_coins
        
        update_result = supabase.table('wallets').update({
            'balance': new_balance,
            'updated_at': datetime.utcnow().isoformat()
        }).eq('user_id', current_user.id).execute()
        
        if not update_result.data:
            raise HTTPException(status_code=500, detail="Failed to update balance")
        
        return {
            "message": "Coins earned successfully! 🎉",
            "activity_type": activity.activity_type.value,
            "base_coins": base_coins,
            "streak_days": streak_days,
            "streak_multiplier": streak_multiplier,
            "final_coins": final_coins,
            "new_balance": new_balance
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to earn coins: {str(e)}")

@app.get("/api/wallet/stats")
async def get_user_stats(current_user: UserResponse = Depends(get_current_user)):
    """Estatísticas do usuário"""
    supabase = get_supabase_client()
    
    try:
        # Saldo atual
        wallet = supabase.table('wallets').select('balance').eq('user_id', current_user.id).execute()
        balance = wallet.data[0]['balance'] if wallet.data else 0
        
        # Atividades
        activities = supabase.table('activities').select('*').eq('user_id', current_user.id).execute()
        total_activities = len(activities.data) if activities.data else 0
        
        # Total ganho
        total_earned = sum(activity['coins_earned'] for activity in activities.data) if activities.data else 0
        
        # Streak atual
        current_streak = await calculate_user_streak(current_user.id)
        
        return {
            "balance": balance,
            "total_activities": total_activities,
            "total_earned": total_earned,
            "current_streak": current_streak,
            "streak_bonus": get_streak_multiplier(current_streak)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)