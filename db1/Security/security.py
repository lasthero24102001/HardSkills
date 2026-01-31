from fastapi.security import OAuth2PasswordBearer,OAuth2PasswordRequestForm
from passlib.context import CryptContext
from abc import ABC, abstractmethod
from db1.models.Base1 import User,Project,Task
from typing import Any


password_context = CryptContext(schemes=["argon2"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login")
class Utils:
    @staticmethod
    def password_hash(password:str):
        return password_context.hash(password)
    @staticmethod
    def password_verify(password:str,password_hash:str):
        return password_context.verify(password,password_hash)

class BaseUserPolicy(ABC):
    def __init__(self,user:User):
        self.user = user
    @abstractmethod
    def can_read(self,user:User):
        pass
    @abstractmethod
    def can_create(self,user:User):
        pass
    @abstractmethod
    def can_update(self,user:User):
        pass
    @abstractmethod
    def can_delete(self,user:User):
        pass
class UserPolicy(BaseUserPolicy):
    def can_read(self,user:User):
        return self.user.role == "admin" or self.user.id==user.id
    def can_create(self,user:User):
        return self.user.role == "admin"
    def can_update(self,user:User):
        return self.user.role == "admin" or self.user.id == user.id
    def can_delete(self,user:User):
        return self.user.role == 'admin'
class BaseProjectPolicy(ABC):
    def __init__(self,user:User):
        self.user = user
    @abstractmethod
    def can_read(self,project:Project):
        pass
    @abstractmethod
    def can_create(self):
        pass
    @abstractmethod
    def can_update(self,project:Project):
        pass
    @abstractmethod
    def can_delete(self,project:Project):
        pass
class ProjectPolicy(BaseProjectPolicy):
    def can_read(self,project:Project):
        return self.user.role == "admin" or project.owner_id == self.user.id
    def can_create(self):
        return self.user.id
    def can_update(self,project:Project):
        return project.owner_id == self.user.id
    def can_delete(self,project:Project):
        return self.user.role=='admin' or project.owner_id == self.user.id
class BaseTaskPolicy(ABC):
    def __init__(self,user:User):
        self.user = user
    @abstractmethod
    def can_read(self,task:Task):
        pass
    @abstractmethod
    def can_create(self,task:Task):
        pass
    @abstractmethod
    def can_update(self,task:Task):
        pass
    @abstractmethod
    def can_delete(self,task:Task):
        pass
class TaskPolicy(BaseTaskPolicy):
    def can_read(self,task:Task):
        return self.user.role == "admin" or task.assignee_id == self.user.id
    def can_create(self,task:Task):
        return self.user.role == "admin"
    def can_update(self,task:Task):
        return self.user.role == "admin"
    def can_delete(self,task:Task):
        return self.user.role == 'admin'
class BaseService(ABC):
    @abstractmethod
    async def get_all(self):
        pass
    @abstractmethod
    async def get_by_id(self,obj_id:int):
        pass
    @abstractmethod
    async def update(self,obj_id:int,obj_in:Any):
        pass
    @abstractmethod
    async def delete(self,obj_id:int):
        pass
class CreateService(ABC):
    @abstractmethod
    async def create(self,obj_in:Any):
        pass