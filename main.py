from __future__ import annotations
import logging
import redis.asyncio as redis
from contextlib import asynccontextmanager
from fastapi import FastAPI,Request,status,Depends,HTTPException
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from fastapi_pagination import add_pagination, Page
from db1.PydanticModels.Pydantic import UserOut,UserSimpleOut,CreateUser,TokenResponse,RefreshToken,UpdateUser
from db1.Tokens.tokens import  create_access_token,create_refresh_token,save_refresh_token,delete_refresh_token,jwt,JWTError,get_current_user,validate_refresh_token
from db1.Services.services import AuthService,UserService
from db1.Security.security import UserPolicy,OAuth2PasswordRequestForm
from db1.Database.database import engine,AsyncSession,get_db
from db1.Filters.filters import UserFilter
from db1.models.Base1 import User
from sqlalchemy import select


from db1.models.Base1 import Base

from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Создание таблиц при запуске сервера ---
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # ------------------------------------------

    # ... ваш код Redis ...
    app.state.redis = await redis.from_url("redis://localhost:6379",
        decode_responses=True)
    await FastAPILimiter.init(app.state.redis)
    yield
    await app.state.redis.close()

async def get_redis(request: Request):
    # Берем уже созданное соединение из lifespan
    return request.app.state.redis




app=FastAPI(lifespan=lifespan)
add_pagination(app)
@app.post('/users/register', response_model=UserSimpleOut, status_code=status.HTTP_201_CREATED)
async def register(user: CreateUser, db: AsyncSession = Depends(get_db)):
    auth = AuthService(db)
    new_user_obj = await auth.register_user(
        username=user.username,
        password=user.password,
        email=user.email
    )
    return new_user_obj
@app.post('/users/login',response_model=TokenResponse,dependencies=[Depends(RateLimiter(times=6,minutes=60))])
async def login(form_data:OAuth2PasswordRequestForm=Depends(),db:AsyncSession=Depends(get_db)):
    auth=AuthService(db)
    user=await auth.login_user(username=form_data.username,password=form_data.password)
    access_token=create_access_token(user_id=user.id,role=user.role)
    refresh_token=create_refresh_token(user_id=user.id,role=user.role)
    await save_refresh_token(db,user_id=user.id,refresh_token=refresh_token)
    return TokenResponse(access_token=access_token,refresh_token=refresh_token,token_type="Bearer")
@app.post('/users/refresh',response_model=TokenResponse)
async def refresh(data:RefreshToken,db:AsyncSession=Depends(get_db)):
    try:
        payload=jwt.decode(data.refresh_token,settings.SECRET_KEY,algorithms=[settings.ALGORITHM])
        user_id=payload['sub']
        if not user_id:
            raise HTTPException(status_code=400,detail="Invalid token")
        if payload['type'] != 'refresh':
            raise HTTPException(status_code=400,detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=400,detail="Invalid token")
    result=await db.execute(select(User).where(User.id == user_id))
    user=result.scalars().first()
    if not user:
        raise HTTPException(status_code=404,detail="User not found")
    await validate_refresh_token(db,user_id=user.id,refresh_token=data.refresh_token)
    await delete_refresh_token(db,user_id=user.id,refresh_token=data.refresh_token)
    new_access=create_access_token(user_id=user.id,role=user.role)
    new_refresh=create_refresh_token(user_id=user.id,role=user.role)
    await save_refresh_token(db,user_id=user.id,refresh_token=new_refresh)
    return TokenResponse(access_token=new_access,refresh_token=new_refresh,token_type="Bearer")
@app.post('/users/logout')
async def logout(data:RefreshToken,db:AsyncSession=Depends(get_db)):
    try:
        payload=jwt.decode(data.refresh_token,settings.SECRET_KEY,algorithms=[settings.ALGORITHM])
        user_id=payload['sub']
        if not user_id:
            raise HTTPException(status_code=400,detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=400,detail="Invalid token")
    await delete_refresh_token(db,user_id=user_id,refresh_token=data.refresh_token)
    await db.commit()
    return {'message':'Success'}
@app.get('/users',response_model=Page[UserOut])
async def read_users(db:AsyncSession=Depends(get_db),redis_conn=Depends(get_redis),user_filter:UserFilter=Depends(),current_user:User=Depends(get_current_user)):
    policy=UserPolicy(current_user)
    service=UserService(db,redis_conn,policy)
    user=await service.get_all(user_filter)
    return user
@app.get('/users/{user_id}',response_model=UserOut)
async def get_user(user_id:int,db:AsyncSession=Depends(get_db),redis_conn=Depends(get_redis),current_user:User=Depends(get_current_user)):
    policy=UserPolicy(current_user)
    service=UserService(db,redis_conn,policy)
    new_user=await service.get_by_id(user_id)
    return new_user
@app.put('/users/{user_id}',response_model=UserOut)
async def update_user(user_id:int,update_user1:UpdateUser,redis_conn=Depends(get_redis),db:AsyncSession=Depends(get_db),current_user:User=Depends(get_current_user)):
    policy=UserPolicy(current_user)
    service=UserService(db,redis_conn,policy)
    put_user=await service.update(user_id,update_user1)
    return put_user
@app.delete('/users/{user_id}',response_model=UserOut)
async def delete_user(user_id:int,db:AsyncSession=Depends(get_db),redis_conn=Depends(get_redis),current_user:User=Depends(get_current_user)):
    policy=UserPolicy(current_user)
    service=UserService(db,redis_conn,policy)
    delete_user1=await service.delete(user_id)
    return delete_user1












