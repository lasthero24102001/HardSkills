from pydantic import BaseModel,constr,Field,ConfigDict
from typing import Optional,List
from datetime import datetime

class CreateUser(BaseModel):
    username:str
    email:str
    password:str=constr(min_length=6,max_length=10)
    role:str="user"
class CreateProject(BaseModel):
    title:str
    created_at:Optional[datetime]=None
class CreateTask(BaseModel):
    title:str
    status:str
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
    email: str
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
class UserOut(BaseModel):
    id:int
    username:str
    email:str
    role:str
    created_at:Optional[datetime]=None
    projects:List[ProjectOut]=Field(default_factory=list)
    tasks:List[TaskOut]=Field(default_factory=list)
    refresh_tokens:List[RefreshDBTokenOut]=Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True,arbitrary_types_allowed=True)
class UpdateUser(BaseModel):
    username:Optional[str]=None
    password:Optional[str]=None
    email:Optional[str]=None
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

    model_config = ConfigDict(from_attributes=True)