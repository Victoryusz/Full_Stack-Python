# =====================================
# backend/database/supabase_client.py - Database Layer
# =====================================
from supabase import create_client, Client
import os
from typing import Optional

_supabase_client: Optional[Client] = None

def get_supabase_client() -> Client:
    """
    Singleton pattern para Supabase client
    Boa prática: Uma única instância da conexão
    """
    global _supabase_client
    
    if _supabase_client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_ANON_KEY")
        
        if not url or not key:
            raise ValueError("❌ SUPABASE_URL e SUPABASE_ANON_KEY são obrigatórios no .env")
        
        _supabase_client = create_client(url, key)
    
    return _supabase_client

def test_connection() -> bool:
    """Testa conexão com Supabase"""
    try:
        supabase = get_supabase_client()
        # Tenta fazer uma query simples
        result = supabase.table('users').select('id').limit(1).execute()
        return True
    except Exception as e:
        print(f"Connection test failed: {e}")
        return False