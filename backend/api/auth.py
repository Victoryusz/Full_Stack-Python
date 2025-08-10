# =====================================
# backend/api/auth.py - Authentication Router
# =====================================
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from models.schemas import UserCreate, UserLogin, TokenResponse, UserResponse
from database.supabase_client import get_supabase_client
from utils.auth_utils import create_access_token, verify_token
from utils.password_utils import hash_password, verify_password

router = APIRouter()
security = HTTPBearer()

@router.post("/register", response_model=TokenResponse)
async def register(user_data: UserCreate):
    """
    Registra novo usuário
    Boa prática: Hash da senha + criação automática de wallet
    """
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
        
        # Criar wallet inicial (100 moedas de bônus)
        wallet_result = supabase.table('wallets').insert({
            'user_id': user['id'],
            'balance': 100
        }).execute()
        
        if not wallet_result.data:
            # Rollback: deletar usuário se wallet falhou
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

@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    """Login com verificação de senha"""
    supabase = get_supabase_client()
    
    try:
        # Buscar usuário
        user_result = supabase.table('users').select('*').eq('email', credentials.email).execute()
        
        if not user_result.data:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        user = user_result.data[0]
        
        # Verificar senha
        if not verify_password(credentials.password, user['password_hash']):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Gerar token
        token = create_access_token(user['id'])
        
        return TokenResponse(
            access_token=token,
            user=UserResponse(**user)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Dependency para rotas protegidas
    Boa prática: Reutilizável em qualquer endpoint
    """
    try:
        payload = verify_token(credentials.credentials)
        user_id = payload.get("sub")
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Buscar dados atualizados do usuário
        supabase = get_supabase_client()
        user_result = supabase.table('users').select('*').eq('id', user_id).execute()
        
        if not user_result.data:
            raise HTTPException(status_code=401, detail="User not found")
        
        return UserResponse(**user_result.data[0])
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")