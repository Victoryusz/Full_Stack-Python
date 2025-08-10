# =====================================
# backend/api/wallet.py - Wallet Management
# =====================================
from fastapi import APIRouter, HTTPException, Depends
from models.schemas import WalletResponse, ActivityCreate, UserResponse, ActivityType
from database.supabase_client import get_supabase_client
from api.auth import get_current_user
from datetime import datetime, timedelta
from typing import Dict

router = APIRouter()

# Configuração de moedas por atividade
ACTIVITY_COINS: Dict[ActivityType, int] = {
    ActivityType.POMODORO: 50,
    ActivityType.EXERCISE: 75,
    ActivityType.STUDY: 100,
    ActivityType.DEEP_WORK: 200,
}

# Bônus por streak
STREAK_MULTIPLIERS = {
    3: 1.2,   # 3 dias = 20% bonus
    7: 1.5,   # 7 dias = 50% bonus
    30: 2.0,  # 30 dias = 100% bonus
}

@router.get("/balance", response_model=WalletResponse)
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

@router.post("/earn")
async def earn_coins(
    activity: ActivityCreate, 
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Ganha moedas completando atividades
    Inclui sistema de streak bonus
    """
    supabase = get_supabase_client()
    
    try:
        # 1. Calcular moedas base
        base_coins = ACTIVITY_COINS[activity.activity_type]
        
        # 2. Calcular streak bonus
        streak_days = await calculate_user_streak(current_user.id)
        streak_multiplier = get_streak_multiplier(streak_days)
        
        final_coins = int(base_coins * streak_multiplier)
        
        # 3. Registrar atividade
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
        
        # 4. Atualizar saldo do wallet
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

@router.get("/activities/history")
async def get_activity_history(
    limit: int = 10,
    current_user: UserResponse = Depends(get_current_user)
):
    """Histórico de atividades recentes"""
    supabase = get_supabase_client()
    
    try:
        activities_result = supabase.table('activities')\
            .select('*')\
            .eq('user_id', current_user.id)\
            .order('created_at', desc=True)\
            .limit(limit)\
            .execute()
        
        return {
            "activities": activities_result.data,
            "total": len(activities_result.data)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")

@router.get("/stats")
async def get_user_stats(current_user: UserResponse = Depends(get_current_user)):
    """Estatísticas do usuário"""
    supabase = get_supabase_client()
    
    try:
        # Saldo atual
        wallet = supabase.table('wallets').select('balance').eq('user_id', current_user.id).execute()
        balance = wallet.data[0]['balance'] if wallet.data else 0
        
        # Total de atividades
        activities = supabase.table('activities').select('*').eq('user_id', current_user.id).execute()
        total_activities = len(activities.data) if activities.data else 0
        
        # Total de moedas ganhas
        total_earned = sum(activity['coins_earned'] for activity in activities.data) if activities.data else 0
        
        # Streak atual
        current_streak = await calculate_user_streak(current_user.id)
        
        # Atividade favorita (mais frequente)
        if activities.data:
            activity_counts = {}
            for activity in activities.data:
                activity_type = activity['activity_type']
                activity_counts[activity_type] = activity_counts.get(activity_type, 0) + 1
            
            favorite_activity = max(activity_counts, key=activity_counts.get)
        else:
            favorite_activity = None
        
        return {
            "balance": balance,
            "total_activities": total_activities,
            "total_earned": total_earned,
            "current_streak": current_streak,
            "favorite_activity": favorite_activity,
            "next_streak_bonus": get_next_streak_target(current_streak)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

# =====================================
# Helper Functions
# =====================================

async def calculate_user_streak(user_id: str) -> int:
    """
    Calcula streak de dias consecutivos com atividades
    Boa prática: Função pura, testável
    """
    supabase = get_supabase_client()
    
    try:
        # Buscar atividades dos últimos 60 dias, agrupadas por data
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
            date_str = activity['created_at'][:10]  # YYYY-MM-DD
            activity_dates.add(date_str)
        
        # Calcular streak consecutivo a partir de hoje
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

def get_streak_multiplier(streak_days: int) -> float:
    """Retorna multiplicador baseado no streak"""
    for days, multiplier in sorted(STREAK_MULTIPLIERS.items(), reverse=True):
        if streak_days >= days:
            return multiplier
    return 1.0

def get_next_streak_target(current_streak: int) -> Dict:
    """Retorna próximo milestone de streak"""
    for days, multiplier in sorted(STREAK_MULTIPLIERS.items()):
        if current_streak < days:
            return {
                "days_needed": days - current_streak,
                "target_days": days,
                "bonus_multiplier": multiplier
            }
    
    return {
        "days_needed": 0,
        "target_days": current_streak,
        "bonus_multiplier": STREAK_MULTIPLIERS[max(STREAK_MULTIPLIERS.keys())],
        "message": "Maximum streak bonus achieved! 🏆"
    }