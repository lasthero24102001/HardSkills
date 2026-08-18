import pytest
import redis.asyncio as redis
from fastapi_limiter import FastAPILimiter
from sqlalchemy import text
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from main import app
from db1.Database.database import async_factory
from config import settings
from scripts.create_admin import create_admin
from db1.models.Base1 import Base
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# fixture для клиента
@pytest_asyncio.fixture
async def client():
    redis_client = await redis.from_url(
        f"{settings.REDIS_URL}/1",
        decode_responses=True
    )
    # очищаем ДО теста
    await redis_client.flushdb()

    app.state.redis = redis_client
    await FastAPILimiter.init(redis_client)

    async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
    ) as client:
        yield client

    await redis_client.aclose()
@pytest_asyncio.fixture(autouse=True)
async def clean_db():
    yield
    async with async_factory() as db:
        await db.execute(text(
            "TRUNCATE TABLE refresh_tokens, tasks, projects, orders, "
            "outbox_events, transactions, products, users RESTART IDENTITY CASCADE"
        ))
        await db.commit()
# fixture для авторизации

@pytest_asyncio.fixture
async def auth_headers(client):
    # создаём админа напрямую в БД тем же способом, что и в проде (bootstrap-скрипт)
    await create_admin(username="testadmin", email="admin@test.com", password="123456")
    # логинимся
    response = await client.post("/users/login", json={
        "username": "testadmin",
        "password": "123456"
    })
    return response.cookies
# ===== REGISTER =====
@pytest.mark.asyncio
async def test_register_success(client):
    response = await client.post("/users/register", json={
        "username": "newuser",
        "password": "123456",
        "email": "new@test.com"
    })
    assert response.status_code == 201
    assert response.json()["username"] == "newuser"

@pytest.mark.asyncio
async def test_register_duplicate_username(client):
    await client.post("/users/register", json={
        "username": "dupuser",
        "password": "123456",
        "email": "dup1@test.com"
    })
    response = await client.post("/users/register", json={
        "username": "dupuser",
        "password": "123456",
        "email": "dup2@test.com"
    })
    assert response.status_code == 409

@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    await client.post("/users/register", json={
        "username": "user1",
        "password": "123456",
        "email": "same@test.com"
    })
    response = await client.post("/users/register", json={
        "username": "user2",
        "password": "123456",
        "email": "same@test.com"
    })
    assert response.status_code == 409

# ===== LOGIN =====
@pytest.mark.asyncio
async def test_login_success(client):
    await client.post("/users/register", json={
        "username": "loginuser",
        "password": "123456",
        "email": "login@test.com"
    })
    response = await client.post("/users/login", json={
        "username": "loginuser",
        "password": "123456"
    })
    assert response.status_code == 200
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies

@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/users/register", json={
        "username": "wrongpass",
        "password": "123456",
        "email": "wrong@test.com"
    })
    response = await client.post("/users/login", json={
        "username": "wrongpass",
        "password": "wrongpassword"
    })
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_login_wrong_username(client):
    response = await client.post("/users/login", json={
        "username": "notexist",
        "password": "123456"
    })
    assert response.status_code == 401

# ===== GET USER =====
@pytest.mark.asyncio
async def test_get_user_unauthorized(client):
    response = await client.get("/users/1")
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_get_user_not_found(client, auth_headers):
    response = await client.get("/users/99999", cookies=auth_headers)
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_get_user_success(client, auth_headers):
    # регистрируем пользователя
    reg = await client.post("/users/register", json={
        "username": "getuser",
        "password": "123456",
        "email": "getuser@test.com"
    })
    user_id = reg.json()["id"]
    response = await client.get(f"/users/{user_id}", cookies=auth_headers)
    assert response.status_code == 200
    assert response.json()["username"] == "getuser"

# ===== UPDATE USER =====
@pytest.mark.asyncio
async def test_update_user_success(client, auth_headers):
    reg = await client.post("/users/register", json={
        "username": "updateuser",
        "password": "123456",
        "email": "update@test.com"
    })
    user_id = reg.json()["id"]
    response = await client.put(
        f"/users/{user_id}",
        json={"username": "updatedname"},
        cookies=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["username"] == "updatedname"

# ===== DELETE USER =====
@pytest.mark.asyncio
async def test_delete_user_success(client, auth_headers):
    reg = await client.post("/users/register", json={
        "username": "deleteuser",
        "password": "123456",
        "email": "delete@test.com"
    })
    user_id = reg.json()["id"]
    response = await client.delete(
        f"/users/{user_id}",
        cookies=auth_headers
    )
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_delete_user_not_found(client, auth_headers):
    response = await client.delete("/users/99999", cookies=auth_headers)
    assert response.status_code == 404

# ===== LOGOUT =====
@pytest.mark.asyncio
async def test_logout_success(client):
    await client.post("/users/register", json={
        "username": "logoutuser",
        "password": "123456",
        "email": "logout@test.com"
    })
    login = await client.post("/users/login", json={
        "username": "logoutuser",
        "password": "123456"
    })

    response = await client.post("/users/logout", cookies=login.cookies)
    assert response.status_code == 200
    assert response.json() == {"message": "Success"}