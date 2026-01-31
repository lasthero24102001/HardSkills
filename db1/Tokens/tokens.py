from sqlalchemy.ext.asyncio import AsyncSession
from config import settings
from datetime import datetime,timedelta
from jose import jwt,JWTError
from db1.models.Base1 import RefreshTokenDB,User
from db1.Security.security import Utils,oauth2_scheme
from fastapi import HTTPException, Depends
from sqlalchemy import select
from db1.Database.database import get_db



def create_access_token(user_id:int,role:str):
    payload = {'sub':str(user_id),'role':role,'type':'access','exp':datetime.utcnow()+timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES) }
    return jwt.encode(payload,settings.SECRET_KEY,algorithm=settings.ALGORITHM)
def create_refresh_token(user_id:int,role:str):
    payload={'sub':str(user_id),'role':role,'type':'refresh','exp':datetime.utcnow()+timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)}
    return jwt.encode(payload,settings.SECRET_KEY,algorithm=settings.ALGORITHM)
async def save_refresh_token(db:AsyncSession,user_id:int,refresh_token:str):
    hashed_refresh=Utils.password_hash(refresh_token)
    db_token=RefreshTokenDB(user_id=user_id,token=hashed_refresh,expires_at=datetime.utcnow()+timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))
    db.add(db_token)
    await db.commit()
    await db.refresh(db_token)
    return db_token
async def delete_refresh_token(db:AsyncSession,user_id:int,refresh_token:str):
    result=await db.execute(select(RefreshTokenDB).where(RefreshTokenDB.user_id == user_id))
    user=result.scalars().all()
    for token1 in user:
        if Utils.password_verify(refresh_token,token1.token):
           await db.delete(token1)
           await db.commit()
           return token1
    raise HTTPException(status_code=404,detail="Refresh Token Not Found")
async def validate_refresh_token(db:AsyncSession,user_id:int,refresh_token:str):
    result=await db.execute(select(RefreshTokenDB).where(RefreshTokenDB.user_id == user_id))
    user=result.scalars().first()
    if not user or not Utils.password_verify(refresh_token,user.token):
        raise HTTPException(status_code=404,detail="Refresh Token Not Found")
    return user
def decode_token(token:str):
    try:
        payload=jwt.decode(token,settings.SECRET_KEY,algorithms=[settings.ALGORITHM])
        if 'sub' not in payload:
            raise HTTPException(status_code=404,detail="Token is invalid")
        return payload
    except JWTError:
        raise HTTPException(status_code=404,detail="Token is invalid")
async def get_current_user(token:str=Depends(oauth2_scheme),db:AsyncSession=Depends(get_db)):
    try:
        payload=decode_token(token)
        user_id=payload['sub']
        if not user_id:
            raise HTTPException(status_code=404,detail="Token is invalid")
        if payload['type'] != 'access':
            raise HTTPException(status_code=404,detail="Token is invalid")
        result=await db.execute(select(User).where(User.id == user_id))
        user=result.scalars().first()
        if not user:
            raise HTTPException(status_code=404,detail="Token is invalid")
        return user
    except JWTError:
        raise HTTPException(status_code=404,detail="Token is invalid")
async def require_admin(current_user:User=Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403,detail="You are not an admin")
    return current_user
