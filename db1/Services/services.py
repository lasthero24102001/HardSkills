import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db1.models.Base1 import User,Project,Task
from db1.Security.security import Utils
from fastapi import HTTPException
from db1.Security.security import BaseService,CreateService,BaseProjectPolicy,BaseUserPolicy,BaseTaskPolicy
from sqlalchemy.orm import selectinload,joinedload
from db1.PydanticModels.Pydantic import *
from config import settings
from db1.Filters.filters import UserFilter,ProjectFilter,TaskFilter
from fastapi_pagination.ext.sqlalchemy import paginate



class AuthService:
    def __init__(self,db:AsyncSession):
        self.db = db

    async def register_user(self, username: str, password: str, email: str):
        try:
            # Существующие проверки
            result = await self.db.execute(select(User).where(User.username == username))
            user = result.scalars().first()
            if user:
                raise HTTPException(status_code=409, detail="User already exists")

            result1 = await self.db.execute(select(User).where(User.email == email))
            user1 = result1.scalars().first()
            if user1:
                raise HTTPException(status_code=409, detail="User already exists")

            # Создание пользователя
            hashed_password = Utils.password_hash(password)
            new_user = User(
                username=username,
                email=email,
                hashed_password=hashed_password,
                role='user'
            )
            self.db.add(new_user)
            await self.db.commit()
            await self.db.refresh(new_user)
            return new_user

        except Exception as e:
            print(f"DEBUG Ошибка в register_user: {e}")  # Вывод в консоль
            await self.db.rollback()
            raise HTTPException(status_code=500, detail="Internal server error")
    async def login_user(self,username:str,password:str):
        result=await self.db.execute(select(User).where(User.username==username))
        user=result.scalars().first()
        if not user or not Utils.password_verify(password,user.hashed_password):
            raise HTTPException(status_code=409,detail="Incorrect password")
        return user
class UserService(BaseService):
    def __init__(self,db:AsyncSession,redis_conn,policy:BaseUserPolicy):
        self.db = db
        self.redis=redis_conn
        self.policy=policy
    async def get_all(self,user_filter:UserFilter):
        result=select(User).options(selectinload(User.projects),selectinload(User.tasks),selectinload(User.refresh_tokens))
        user=user_filter.filter(result)
        return paginate(self.db,user)
    async def get_by_id(self,user_id:int):
        cache_key=f'user:{user_id}'
        cache_user=await self.redis.get(cache_key)
        if cache_user:
            return json.loads(cache_user)
        result=await self.db.execute(select(User).options(selectinload(User.projects),selectinload(User.tasks),selectinload(User.refresh_tokens)).where(User.id == user_id))
        user=result.scalars().first()
        if not user:
            raise HTTPException(status_code=404,detail="User not found")
        if not self.policy.can_read(user):
            raise HTTPException(status_code=401,detail="Not authorized")
        user_data = UserOut.model_validate(user)
        user_json=user_data.model_dump()
        await self.redis.set(cache_key,user_data.model_dump_json(),ex=settings.REDIS_TIME)
        return user_json
    async def update(self,user_id:int,user_update:UpdateUser):
        result=await self.db.execute(select(User).where(User.id == user_id))
        user=result.scalars().first()
        if not user:
            raise HTTPException(status_code=404,detail="User not found")
        if not self.policy.can_update(user):
            raise HTTPException(status_code=403,detail="Forbidden")
        if user_update.username is not None:
            user.username=user_update.username
        if user_update.password is not None:
            user.hashed_password=Utils.password_hash(user_update.password)
        if user_update.email is not None:
            user.email=user_update.email
        if user_update.created_at is not None:
            user.created_at=user_update.created_at
        await self.db.commit()
        await self.redis.delete(f'user:{user_id}')
        await self.db.refresh(user)
        return user
    async def delete(self,user_id:int):
        result=await self.db.execute(select(User).where(User.id == user_id))
        user=result.scalars().first()
        if not user:
            raise HTTPException(status_code=404,detail="User not found")
        if not self.policy.can_delete(user):
            raise HTTPException(status_code=403,detail="Forbidden")
        await self.db.delete(user)
        await self.db.commit()
        await self.redis.delete(f'user:{user_id}')
        return user

class ProjectService(BaseService, CreateService):
    def __init__(self, db: AsyncSession, redis_conn, policy: BaseProjectPolicy):
        self.db = db
        self.redis = redis_conn
        self.policy = policy

    async def get_all(self, project_filter: ProjectFilter):
        result = select(Project).options(joinedload(Project.owner), selectinload(Project.tasks))
        project = project_filter.filter(result)
        return paginate(self.db, project)

    async def get_by_id(self, project_id: int):
        cache_key = f'project:{project_id}'
        cache_project = await self.redis.get(cache_key)
        if cache_project:
            return json.loads(cache_project)
        result = await self.db.execute(
            select(Project).options(joinedload(Project.owner), selectinload(Project.tasks)).where(
                Project.id == project_id))
        project = result.scalars().first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        if not self.policy.can_read(project):
            raise HTTPException(status_code=403, detail="Forbidden")
        project_data = ProjectOut.model_validate(project).model_dump_json()
        await self.redis.set(cache_key, project_data, ex=settings.REDIS_TIME)
        return project_data

    async def create(self, project_in: CreateProject):
        result = await self.db.execute(select(Project).where(Project.title == project_in.title))
        project = result.scalars().first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        if not self.policy.can_create():
            raise HTTPException(status_code=403, detail="Forbidden")
        new_project = Project(title=project_in.title, owner_id=self.policy.user.id, created_at=project_in.created_at)
        self.db.add(new_project)
        await self.db.commit()
        await self.db.refresh(new_project)
        return new_project

    async def update(self, project_id: int, project_update: UpdateProject):
        result = await self.db.execute(select(Project).where(Project.id == project_id))
        project = result.scalars().first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        if not self.policy.can_update(project):
            raise HTTPException(status_code=403, detail="Forbidden")
        if project_update.title is not None:
            project.title = project_update.title
        if project_update.created_at is not None:
            project.created_at = project_update.created_at
        await self.db.commit()
        await self.redis.delete(f'project:{project_id}')
        await self.db.refresh(project)
        return project

    async def delete(self, project_id: int):
        result = await self.db.execute(select(Project).where(Project.id == project_id))
        project = result.scalars().first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        if not self.policy.can_delete(project):
            raise HTTPException(status_code=403, detail="Forbidden")
        await self.db.delete(project)
        await self.db.commit()
        await self.redis.delete(f'project:{project_id}')
        return project
class TaskService(BaseService,CreateService):
    def __init__(self,db:AsyncSession,redis_conn,policy:BaseTaskPolicy):
        self.db = db
        self.redis=redis_conn
        self.policy=policy
    async def get_all(self,task_filter:TaskFilter):
        result=select(Task).options(joinedload(Task.assignee),joinedload(Task.project))
        task=task_filter.filter(result)
        return paginate(self.db,task)
    async def get_by_id(self,task_id:int):
        cache_key=f'task:{task_id}'
        cache_task=await self.redis.get(cache_key)
        if cache_task:
            return json.loads(cache_task)
        result=await self.db.execute(select(Task).options(joinedload(Task.assignee),joinedload(Task.project)).where(Task.id == task_id))
        task=result.scalars().first()
        if not task:
            raise HTTPException(status_code=404,detail="Task not found")
        if not self.policy.can_read(task):
            raise HTTPException(status_code=403,detail="Forbidden")
        task_pydantic=TaskOut.model_validate(task)
        task_data=task_pydantic.model_dump()
        await self.redis.set(cache_key,task_pydantic.model_dump_json(),ex=settings.REDIS_TIME)
        return task_data
    async def create(self,task_in:CreateTask):
        result=await self.db.execute(select(Task).where(Task.title == task_in.title))
        task=result.scalars().first()
        if task:
            raise HTTPException(status_code=409,detail="Task already exists")
        if not self.policy.can_create():
            raise HTTPException(status_code=403,detail="Forbidden")
        result1=await self.db.execute(select(Project).where(Project.id == task_in.project_id))
        project=result1.scalars().first()
        if project:
            raise HTTPException(status_code=404,detail="Project with this task already exists")
        result3=await self.db.execute(select(User).where(User.id == task_in.assignee_id))
        user=result3.scalars().first()
        if not user:
            raise HTTPException(status_code=404,detail="User not found")
        new_task=Task(title=task_in.title,project_id=task_in.project_id,assignee_id=task_in.assignee_id or self.policy.user.id,created_at=task_in.created_at)
        self.db.add(new_task)
        await self.db.commit()
        await self.db.refresh(new_task)
        return new_task
    async def update(self,task_id:int,task_in:UpdateTask):
        result=await self.db.execute(select(Task).where(Task.id == task_id))
        task=result.scalars().first()
        if not task:
            raise HTTPException(status_code=404,detail="Task not found")
        if not self.policy.can_update(task):
            raise HTTPException(status_code=403,detail="Forbidden")
        if task_in.title is not None:
            task.title=task_in.title
        if task_in.created_at is not None:
            task.created_at=task_in.created_at
        await self.db.commit()
        await self.redis.delete(f'task:{task_id}')
        await self.db.refresh(task)
        return task
    async def delete(self,task_id:int):
        result=await self.db.execute(select(Task).where(Task.id == task_id))
        task=result.scalars().first()
        if not task:
            raise HTTPException(status_code=404,detail="Task not found")
        if not self.policy.can_delete(task):
            raise HTTPException(status_code=403,detail="Forbidden")
        await self.db.delete(task)
        await self.db.commit()
        await self.redis.delete(f'task:{task_id}')
        return task