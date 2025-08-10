# =====================================
# backend/models/schemas.py - Pydantic Models
# =====================================
from pydantic import BaseModel, EmailStr, validator
from typing import Optional
from datetime import datetime
from enum import Enum

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
    
    class Config:
        from_attributes = True

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