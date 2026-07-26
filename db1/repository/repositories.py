from abc import ABC

from sqlalchemy import select
from sqlalchemy.orm import selectinload,joinedload

from db1.Filters.filters import ProjectFilter
from db1.models.Base1 import User,Project,Task
from db1.PydanticModels.Pydantic import CreateTask

from db1.Database.database import AsyncSession


class BaseRepository(ABC):
    def __init__(self, db: AsyncSession):
        self.db = db


class UserRepository(BaseRepository):
    async def get_by_id(self, user_id: int):
        result = await self.db.execute(
            select(User)
            .options(
                selectinload(User.projects).selectinload(Project.tasks),  # добавь .selectinload(Project.tasks)
                selectinload(User.tasks),
                selectinload(User.refresh_tokens),
            )
            .where(User.id == user_id)
        )
        return result.scalars().first()
    async def get_by_username(self, username: str):
        result = await self.db.execute(select(User).where(User.username == username))
        return result.scalars().first()
    async def get_by_email(self, email: str):
        result=await self.db.execute(select(User).where(User.email == email))
        return result.scalars().first()
    async def user_task_assignee_id(self, assignee_id: int):
        result = await self.db.execute(select(User).where(User.id == assignee_id))
        return result.scalars().first()

class ProjectRepository(BaseRepository):
    async def get_project_id(self, project_id:int):
        result = await self.db.execute(
            select(Project)
            .options(joinedload(Project.owner), selectinload(Project.tasks))
            .where(Project.id == project_id)
        )
        return result.scalars().first()
    async def get_title(self, title:str):
        result = await self.db.execute(
            select(Project).where(Project.title == title)
        )
        return result.scalars().first()
    async def get_project_title_to_task(self,project_id:int):
        result = await self.db.execute(select(Project).where(Project.id == project_id))
        return result.scalars().first()

class TaskRepository(BaseRepository):
    async def get_by_id(self, task_id: int):
        result =await self.db.execute(select(Task).options(joinedload(Task.assignee),joinedload(Task.project)).where(Task.id == task_id))
        return result.scalars().first()
    async def get_by_title_task(self,title:str):
        result=await self.db.execute(select(Task).where(Task.title == title))
        return result.scalars().first()