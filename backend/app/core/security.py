import hashlib,secrets
from datetime import datetime,timedelta,timezone
from cryptography.fernet import Fernet
from jose import jwt
from pwdlib import PasswordHash
from .config import settings

ph=PasswordHash.recommended()

def hash_password(v): return ph.hash(v)
def verify_password(v,h): return ph.verify(v,h)

def access_token(user,tenant,role):
 s=settings(); return jwt.encode({'sub':user,'tid':tenant,'role':role,'type':'access','exp':datetime.now(timezone.utc)+timedelta(minutes=s.access_token_minutes)},s.jwt_secret.get_secret_value(),algorithm='HS256')

def decode_token(v): return jwt.decode(v,settings().jwt_secret.get_secret_value(),algorithms=['HS256'])
def new_refresh(): return secrets.token_urlsafe(48)
def token_hash(v): return hashlib.sha256(v.encode()).hexdigest()
def encrypt(v): return Fernet(settings().field_encryption_key.get_secret_value().encode()).encrypt(v.encode()).decode()
def decrypt(v): return Fernet(settings().field_encryption_key.get_secret_value().encode()).decrypt(v.encode()).decode()