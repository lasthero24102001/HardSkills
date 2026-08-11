from pydantic import BaseModel,Field,ConfigDict,EmailStr
from typing import Optional,List
from datetime import datetime

class CreateUser(BaseModel):
    username:str
    email:EmailStr
    password: str = Field(min_length=6, max_length=100)
class CreateProject(BaseModel):
    title:str
    created_at:Optional[datetime]=None
class CreateTask(BaseModel):
    title:str
    status:str
    description: Optional[str] = None
    project_id:int
    assignee_id:int
    created_at:Optional[datetime]=None
class CreateRefreshDBToken(BaseModel):
    token:str
    user_id:int
    expires_at:Optional[datetime]=None

    model_config = ConfigDict(arbitrary_types_allowed=True)
class TokenResponse(BaseModel):
    access_token:str
    refresh_token:str
    token_type:str="Bearer"

class LoginRequest(BaseModel):
    username: str
    password: str
class RefreshToken(BaseModel):
    refresh_token:str
class RefreshDBTokenOut(BaseModel):
    id:int
    token:str
    expires_at:Optional[datetime]=None

    model_config = ConfigDict(from_attributes=True)
class TaskOut(BaseModel):
    id:int
    title:str
    status:str
    description: Optional[str] = None
    created_at:Optional[datetime]=None

    model_config = ConfigDict(from_attributes=True)
class ProjectOut(BaseModel):
    id:int
    title:str
    created_at:Optional[datetime]=None
    tasks:List[TaskOut]=Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
class UserSimpleOut(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
class UserOut(BaseModel):
    id:int
    username:str
    email:EmailStr
    role:str
    created_at:Optional[datetime]=None
    projects:List[ProjectOut]=Field(default_factory=list)
    tasks:List[TaskOut]=Field(default_factory=list)
    refresh_tokens:List[RefreshDBTokenOut]=Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True,arbitrary_types_allowed=True)
class ProductCreate(BaseModel):
    name: str
    price: int
    stock: int = 0


class ProductResponse(BaseModel):
    id: int
    name: str
    price: int
    stock: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------- Order ----------

class CreateOrderRequest(BaseModel):
    product_id: int
    quantity: int
    idempotency_key: str | None = None


class OrderResponse(BaseModel):
    id: int
    user_id: int
    product_id: int
    quantity: int
    amount: int
    status: str
    idempotency_key: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------- OutboxEvent ----------
# Обычно наружу (в API) не отдаётся — используется только внутри системы.
# Но если понадобится, например, для админки/дебага:

class OutboxEventResponse(BaseModel):
    id: int
    event_type: str
    status: str
    created_at: datetime
    processed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


# ---------- Transaction ----------
# Тоже в основном внутренняя сущность, наружу может понадобиться для истории платежей юзера:

class TransactionResponse(BaseModel):
    id: int
    order_id: int
    provider: str
    provider_transaction_id: str | None
    amount: int
    state: int
    created_at: datetime
    performed_at: datetime | None
    cancelled_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
class UpdateUser(BaseModel):
    username:Optional[str]=None
    password:Optional[str]=None
    email:Optional[EmailStr]=None
    created_at:Optional[datetime]=None

    model_config = ConfigDict(from_attributes=True)
class UpdateProject(BaseModel):
    title:Optional[str]=None
    created_at:Optional[datetime]=None

    model_config = ConfigDict(from_attributes=True)
class UpdateTask(BaseModel):
    title:Optional[str]=None
    status:Optional[str]=None
    created_at:Optional[datetime]=None
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)