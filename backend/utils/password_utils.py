# =====================================
# backend/utils/password_utils.py - Password Security
# =====================================
import bcrypt

def hash_password(password: str) -> str:
    """Hash seguro da senha com bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verifica senha contra hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))