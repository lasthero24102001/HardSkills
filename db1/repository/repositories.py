from abc import ABC
from datetime import datetime, timedelta
from db1.models.Base1 import AuditLog, RequestLog
from sqlalchemy import select,update,delete,func
from sqlalchemy.orm import selectinload,joinedload

from db1.Filters.filters import ProjectFilter
from db1.models.Base1 import User,Project,Task,Order,Product
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

class AuditLogRepository(BaseRepository):
    async def get_all(self, actor_id: int | None = None, action: str | None = None):
        query = select(AuditLog).order_by(AuditLog.created_at.desc())
        if actor_id is not None:
            query = query.where(AuditLog.actor_id == actor_id)
        if action is not None:
            query = query.where(AuditLog.action == action)
        return query
class RequestLogRepository(BaseRepository):
    def _apply_filters(self, query, user_id=None, method=None, path=None, status_code=None,
                        since: datetime | None = None, until: datetime | None = None):
        if user_id is not None:
            query = query.where(RequestLog.user_id == user_id)
        if method is not None:
            query = query.where(RequestLog.method == method.upper())
        if path is not None:
            query = query.where(RequestLog.path.ilike(f"%{path}%"))
        if status_code is not None:
            query = query.where(RequestLog.status_code == status_code)
        if since is not None:
            query = query.where(RequestLog.created_at >= since)
        if until is not None:
            query = query.where(RequestLog.created_at <= until)
        return query

    async def get_all(self, user_id=None, method=None, path=None, status_code=None,
                       since=None, until=None):
        query = select(RequestLog).order_by(RequestLog.created_at.desc())
        query = self._apply_filters(query, user_id, method, path, status_code, since, until)
        return query

    async def delete_filtered(self, user_id=None, method=None, path=None, status_code=None,
                               since=None, until=None) -> int:
        if not any([user_id, method, path, status_code, since, until]):
            raise ValueError("At least one filter is required to delete request logs")
        query = delete(RequestLog)
        query = self._apply_filters(query, user_id, method, path, status_code, since, until)
        result = await self.db.execute(query)
        await self.db.commit()
        return result.rowcount

    async def delete_older_than(self, older_than_days: int) -> int:
        threshold = datetime.utcnow() - timedelta(days=older_than_days)
        result = await self.db.execute(delete(RequestLog).where(RequestLog.created_at < threshold))
        await self.db.commit()
        return result.rowcount

    async def count_since(self, since: datetime) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(RequestLog).where(RequestLog.created_at >= since)
        )
        return result.scalar_one()

    async def count_unique_users_since(self, since: datetime) -> int:
        result = await self.db.execute(
            select(func.count(func.distinct(RequestLog.user_id)))
            .where(RequestLog.created_at >= since, RequestLog.user_id.isnot(None))
        )
        return result.scalar_one()

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
class OrderRepository(BaseRepository):
    async def find_by_idempotency_key(self, key: str):
        result = await self.db.execute(
            select(Order).where(Order.idempotency_key == key)
        )
        return result.scalars().first()

    async def get_product(self, product_id: int):
        result = await self.db.execute(
            select(Product).where(Product.id == product_id)
        )
        return result.scalars().first()

    async def atomic_decrement_stock(self, product_id: int, quantity: int) -> bool:
        """
        Атомарно списывает stock. True — списание удалось, False — товара не хватило.
        """
        result = await self.db.execute(
            update(Product)
            .where(
                Product.id == product_id,
                Product.stock >= quantity,
            )
            .values(stock=Product.stock - quantity)
            .returning(Product.id)
        )
        return result.fetchone() is not None

    async def create(
        self,
        user_id: int,
        product_id: int,
        quantity: int,
        amount: int,
        idempotency_key: str,
    ):
        order = Order(
            user_id=user_id,
            product_id=product_id,
            quantity=quantity,
            amount=amount,
            idempotency_key=idempotency_key,
            status="pending",
        )
        self.db.add(order)
        await self.db.flush()
        return order

    async def restore_stock(self, product_id: int, quantity: int):
        await self.db.execute(
            update(Product)
            .where(Product.id == product_id)
            .values(stock=Product.stock + quantity)
        )

    async def get_by_id(self, order_id: int):
        result = await self.db.execute(
            select(Order).where(Order.id == order_id)
        )
        return result.scalars().first()

    async def get_user_orders(self, user_id: int):
        result = await self.db.execute(
            select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc())
        )
        return result.scalars().all()

    async def get_stale_pending_orders(self, older_than_minutes: int = 15):
        threshold = datetime.utcnow() - timedelta(minutes=older_than_minutes)
        result = await self.db.execute(
            select(Order)
            .where(Order.status == "pending", Order.created_at < threshold)
            .with_for_update(skip_locked=True)
        )
        return result.scalars().all()