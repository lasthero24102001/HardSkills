from jose import jwt
import pytest
from db1.Security.security import Utils
from db1.Tokens.tokens import create_access_token,create_refresh_token
from config import settings



def test_password_hashing_and_verify():
    password='12355678'
    hashed_password=Utils.password_hash(password)

    assert Utils.password_verify(password,hashed_password) is True
    assert Utils.password_verify('WrongPassword',hashed_password) is False
def test_create_access_token():
    user_id=1
    role='user'
    token=create_access_token(user_id,role)
    assert isinstance(token,str)

    payload=jwt.decode(token,settings.SECRET_KEY,algorithms=[settings.ALGORITHM])
    assert payload['role'] == role
    assert payload['sub'] == str(user_id)
    assert payload['type']=='access'
def test_create_refresh_token():
    user_id=32
    role='user'
    token=create_refresh_token(user_id,role)
    assert isinstance(token,str)

    payload=jwt.decode(token,settings.SECRET_KEY,algorithms=[settings.ALGORITHM])
    assert payload['role'] == role
    assert payload['sub'] == str(user_id)
    assert payload['type']=='refresh'