from __future__ import annotations
import logging
import uuid
import time
import sentry_sdk
import redis.asyncio as redis
from contextlib import asynccontextmanager
from sqlalchemy import text
from fastapi.responses import Response
from prometheus_fastapi_instrumentator import Instrumentator
from circuitbreaker import circuit
from fastapi.responses import JSONResponse
from db1.exception.exceptions import AppException, InvalidTokenException, UserNotFound
from fastapi import FastAPI,Request,status,Depends
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from fastapi_pagination import add_pagination, Page
from db1.PydanticModels.Pydantic import UserOut, UserSimpleOut, CreateUser, UpdateUser, \
    CreateOrderRequest, OrderResponse, LoginRequest
from db1.Tokens.tokens import  create_access_token,create_refresh_token,save_refresh_token,delete_refresh_token,jwt,JWTError,get_current_user,validate_refresh_token
from db1.Services.services import AuthService,UserService,OrderService
from db1.Security.security import UserPolicy
from db1.Database.database import engine,AsyncSession,get_db
from db1.Filters.filters import UserFilter
from db1.models.Base1 import User
from fastapi_pagination.ext.sqlalchemy import paginate
from db1.repository.repositories import AuditLogRepository
from db1.PydanticModels.Pydantic import AuditLogOut
from db1.Tokens.tokens import require_admin
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from db1.tasks.task import send_welcome_email
from db1.Services.services import ProjectService, TaskService
from db1.Security.security import ProjectPolicy, TaskPolicy
from db1.Filters.filters import ProjectFilter, TaskFilter
from db1.repository.repositories import ProjectRepository
from db1.repository.repositories import TaskRepository

from db1.PydanticModels.Pydantic import CreateProject, UpdateProject, ProjectOut, CreateTask, UpdateTask, TaskOut
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Используем settings.REDIS_URL вместо ручного написания адреса
    app.state.redis = await redis.from_url(
        settings.REDIS_URL, decode_responses=True,
        socket_timeout=2, socket_connect_timeout=2,
    )
    await FastAPILimiter.init(app.state.redis)
    yield
    await app.state.redis.close()
    await engine.dispose()

async def get_redis(request: Request):
    return request.app.state.redis


sentry_sdk.init(
    dsn=settings.SENTRY_DSN,
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
)
app=FastAPI(lifespan=lifespan)
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:63342",
    "null",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


Instrumentator().instrument(app).expose(app)

add_pagination(app)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    request_id = str(uuid.uuid4())
    sentry_sdk.set_tag("request_id", request_id)
    request.state.request_id = request_id

    start_time = time.time()

    response = await call_next(request)

    process_time = time.time() - start_time
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time:.4f}"

    return response
@app.exception_handler(AppException)
async def app_exception_handler(request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


@app.get('/health')
async def health(db: AsyncSession = Depends(get_db), redis=Depends(get_redis)):
    health_status = {"status": "ok", "db": "ok", "redis": "ok"}
    status_code = 200

    # проверяем БД
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        health_status["db"] = "error"
        health_status["status"] = "error"
        status_code = 503

    # проверяем Redis
    try:
        await redis.ping()
    except Exception as e:
        health_status["redis"] = "error"
        health_status["status"] = "error"
        status_code = 503

    return JSONResponse(
        status_code=status_code,
        content=health_status
    )
@circuit(failure_threshold=5, recovery_timeout=30)
async def get_redis_data(redis, key):
    return await redis.get(key)
@circuit(failure_threshold=5, recovery_timeout=30)
async def set_redis_data(redis, key, value, ex=None):
    return await redis.set(key, value, ex=ex)

@circuit(failure_threshold=5, recovery_timeout=30)
async def execute_db_query(db, query):
    return await db.execute(query)
@app.post('/users/register', response_model=UserSimpleOut, status_code=status.HTTP_201_CREATED,dependencies=[Depends(RateLimiter(times=6,seconds=60))])
async def register(user: CreateUser, db: AsyncSession = Depends(get_db)):
    auth = AuthService(db)
    new_user_obj = await auth.register_user(
        username=user.username,
        password=user.password,
        email=user.email,
    )
    send_welcome_email.delay(user_id=new_user_obj.id, email=new_user_obj.email)
    return new_user_obj


@app.post('/users/login',dependencies=[Depends(RateLimiter(times=6,seconds=60))])
async def login(response: Response,data: LoginRequest,db:AsyncSession=Depends(get_db)):
    auth=AuthService(db)
    user=await auth.login_user(username=data.username,password=data.password)
    access_token=create_access_token(user_id=user.id,role=user.role)
    refresh_token=create_refresh_token(user_id=user.id,role=user.role)
    await save_refresh_token(db,user_id=user.id,refresh_token=refresh_token)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,  # True в продакшене с HTTPS
        samesite="strict",
        max_age=1800
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="strict",
        max_age=60 * 60 * 24 * 30
    )
    return {"message": "Login successful"}


@app.post('/users/refresh',dependencies=[Depends(RateLimiter(times=6,seconds=60))])
async def refresh(request:Request,response:Response,db:AsyncSession=Depends(get_db)):
    try:
        refresh_token = request.cookies.get("refresh_token")
        if not refresh_token:
            raise InvalidTokenException()
        payload=jwt.decode(refresh_token,settings.SECRET_KEY,algorithms=[settings.ALGORITHM])
        user_id=payload['sub']
        if not user_id:
            raise InvalidTokenException()
        if payload['type'] != 'refresh':
            raise InvalidTokenException()
    except JWTError:
        raise InvalidTokenException()
    result=await db.execute(select(User).where(User.id == user_id))
    user=result.scalars().first()
    if not user:
        raise UserNotFound()
    await validate_refresh_token(db,user_id=user.id,refresh_token=refresh_token)
    await delete_refresh_token(db,user_id=user.id,refresh_token=refresh_token)
    new_access=create_access_token(user_id=user.id,role=user.role)
    new_refresh=create_refresh_token(user_id=user.id,role=user.role)
    await save_refresh_token(db,user_id=user.id,refresh_token=new_refresh)
    response.set_cookie(
        key="access_token",
        value=new_access,
        httponly=True,
        secure=False,  # True в продакшене с HTTPS
        samesite="strict",
        max_age=1800
    )
    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=False,
        samesite="strict",
        max_age=60 * 60 * 24 * 30
    )
    return {"message": "Token refreshed"}

@app.post('/users/logout')
async def logout(request:Request,response:Response,db:AsyncSession=Depends(get_db)):
    try:
        refresh_token = request.cookies.get("refresh_token")
        if not refresh_token:
            raise InvalidTokenException()
        payload=jwt.decode(refresh_token,settings.SECRET_KEY,algorithms=[settings.ALGORITHM])
        user_id=payload['sub']
        if not user_id:
            raise InvalidTokenException()
    except JWTError:
        raise InvalidTokenException()
    await delete_refresh_token(db,user_id=user_id,refresh_token=refresh_token)
    await db.commit()
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {'message':'Success'}

@app.get('/audit-logs', response_model=Page[AuditLogOut])
async def get_audit_logs(
    actor_id: int | None = None,
    action: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),  # уже готовый dependency у тебя в tokens.py
):
    repo = AuditLogRepository(db)
    query = await repo.get_all(actor_id=actor_id, action=action)
    return await paginate(db, query)

@app.post('/orders', response_model=OrderResponse, status_code=status.HTTP_201_CREATED,
          dependencies=[Depends(RateLimiter(times=10, seconds=60))])
async def create_order(
    order: CreateOrderRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = OrderService(db)
    new_order = await service.create_order(
        user_id=current_user.id,
        product_id=order.product_id,
        quantity=order.quantity,
        idempotency_key=order.idempotency_key
    )
    return new_order
@app.get('/orders', response_model=list[OrderResponse])
async def get_orders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = OrderService(db)
    return await service.get_user_orders(current_user.id)


@app.get('/orders/{order_id}', response_model=OrderResponse)
async def get_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = OrderService(db)
    return await service.get_by_id(order_id, current_user.id)


@app.post('/orders/{order_id}/cancel', response_model=OrderResponse)
async def cancel_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = OrderService(db)
    return await service.cancel_order(order_id, current_user.id)
@app.get('/users',response_model=Page[UserOut])
async def read_users(db:AsyncSession=Depends(get_db),redis_conn=Depends(get_redis),user_filter:UserFilter=Depends(),current_user:User=Depends(get_current_user)):
    policy=UserPolicy(current_user)
    service=UserService(db,redis_conn,policy)
    user=await service.get_all(user_filter)
    return user

@app.get('/users/me', response_model=UserOut)
async def get_me(db: AsyncSession = Depends(get_db), redis_conn=Depends(get_redis), current_user: User = Depends(get_current_user)):
    policy = UserPolicy(current_user)
    service = UserService(db, redis_conn, policy)
    return await service.get_by_id(current_user.id)

@app.get('/users/{user_id}', response_model=UserOut)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db), redis_conn=Depends(get_redis), current_user: User = Depends(get_current_user)):
    policy = UserPolicy(current_user)
    service = UserService(db, redis_conn, policy)
    new_user = await service.get_by_id(user_id)
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

@app.post('/projects', response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(project: CreateProject, db: AsyncSession = Depends(get_db), redis_conn=Depends(get_redis), current_user: User = Depends(get_current_user)):
    policy = ProjectPolicy(current_user)
    service = ProjectService(db, redis_conn, policy)
    new_project = await service.create(project)
    repo = ProjectRepository(db)
    return await repo.get_project_id(new_project.id)

@app.get('/projects', response_model=Page[ProjectOut])
async def get_projects(db: AsyncSession = Depends(get_db), redis_conn=Depends(get_redis), project_filter: ProjectFilter = Depends(), current_user: User = Depends(get_current_user)):
    policy = ProjectPolicy(current_user)
    service = ProjectService(db, redis_conn, policy)
    return await service.get_all(project_filter)

@app.get('/projects/{project_id}', response_model=ProjectOut)
async def get_project(project_id: int, db: AsyncSession = Depends(get_db), redis_conn=Depends(get_redis), current_user: User = Depends(get_current_user)):
    policy = ProjectPolicy(current_user)
    service = ProjectService(db, redis_conn, policy)
    return await service.get_by_id(project_id)

@app.put('/projects/{project_id}', response_model=ProjectOut)
async def update_project(project_id: int, project: UpdateProject, db: AsyncSession = Depends(get_db), redis_conn=Depends(get_redis), current_user: User = Depends(get_current_user)):
    policy = ProjectPolicy(current_user)
    service = ProjectService(db, redis_conn, policy)
    return await service.update(project_id, project)

@app.delete('/projects/{project_id}', response_model=ProjectOut)
async def delete_project(project_id: int, db: AsyncSession = Depends(get_db), redis_conn=Depends(get_redis), current_user: User = Depends(get_current_user)):
    policy = ProjectPolicy(current_user)
    service = ProjectService(db, redis_conn, policy)
    return await service.delete(project_id)

# =================== TASKS ===================

@app.post('/tasks', response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(task: CreateTask, db: AsyncSession = Depends(get_db), redis_conn=Depends(get_redis), current_user: User = Depends(get_current_user)):
    policy = TaskPolicy(current_user)
    service = TaskService(db, redis_conn, policy)
    new_task = await service.create(task)
    repo = TaskRepository(db)
    return await repo.get_by_id(new_task.id)
@app.get('/tasks', response_model=Page[TaskOut])
async def get_tasks(db: AsyncSession = Depends(get_db), redis_conn=Depends(get_redis), task_filter: TaskFilter = Depends(), current_user: User = Depends(get_current_user)):
    policy = TaskPolicy(current_user)
    service = TaskService(db, redis_conn, policy)
    return await service.get_all(task_filter)

@app.get('/tasks/{task_id}', response_model=TaskOut)
async def get_task(task_id: int, db: AsyncSession = Depends(get_db), redis_conn=Depends(get_redis), current_user: User = Depends(get_current_user)):
    policy = TaskPolicy(current_user)
    service = TaskService(db, redis_conn, policy)
    return await service.get_by_id(task_id)

@app.put('/tasks/{task_id}', response_model=TaskOut)
async def update_task(task_id: int, task: UpdateTask, db: AsyncSession = Depends(get_db), redis_conn=Depends(get_redis), current_user: User = Depends(get_current_user)):
    policy = TaskPolicy(current_user)
    service = TaskService(db, redis_conn, policy)
    return await service.update(task_id, task)

@app.delete('/tasks/{task_id}', response_model=TaskOut)
async def delete_task(task_id: int, db: AsyncSession = Depends(get_db), redis_conn=Depends(get_redis), current_user: User = Depends(get_current_user)):
    policy = TaskPolicy(current_user)
    service = TaskService(db, redis_conn, policy)
    return await service.delete(task_id)










