import json
import uuid
from sqlalchemy.exc import IntegrityError

from db1.Services.order_state import transition_order_status
from db1.models.Base1 import OutboxEvent
from db1.exception.exceptions import ProductNotFound, OutOfStock,OrderNotFound,OrderForbidden
from db1.repository.repositories import OrderRepository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db1.models.Base1 import User,Project,Task
from db1.Security.security import Utils
from db1.Security.security import BaseService,CreateService,BaseProjectPolicy,BaseUserPolicy,BaseTaskPolicy
from db1.PydanticModels.Pydantic import *
from config import settings
from db1.Filters.filters import UserFilter,ProjectFilter,TaskFilter
from db1.exception.exceptions import UserNotFound, UserAlreadyExists, UserForbidden, EmailAlreadyExists, \
    InvalidCredentials, ProjectNotFound, TaskNotFound, TaskForbidden, ProjectForbidden, ProjectAlreadyExists, \
    TaskAlreadyExists
from db1.repository.repositories import UserRepository, ProjectRepository, TaskRepository
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from sqlalchemy.exc import OperationalError
from db1.Services.audit import log_action
from fastapi_pagination.ext.sqlalchemy import paginate



class AuthService:
    def __init__(self,db:AsyncSession):
        self.db = db
        self.user_repo=UserRepository(db)
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(1, min=1, max=4),
        retry=retry_if_exception_type(OperationalError)
    )
    async def register_user(self, username: str, password: str, email: str):
        existing_user = await self.user_repo.get_by_username(username)
        if existing_user:
            raise UserAlreadyExists()
        existing_email = await self.user_repo.get_by_email(email)
        if existing_email:
            raise EmailAlreadyExists()
        hashed_password = Utils.password_hash(password)
        new_user = User(username=username, email=email, hashed_password=hashed_password, role="user")
        self.db.add(new_user)
        await self.db.commit()
        await self.db.refresh(new_user)
        return new_user
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(1, min=1, max=4),
        retry=retry_if_exception_type(OperationalError)
    )
    async def login_user(self,username:str,password:str):
        user=await self.user_repo.get_by_username(username)
        if not user or not Utils.password_verify(password,user.hashed_password):
            raise InvalidCredentials()
        return user
class OrderService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.order_repo = OrderRepository(db)

    async def get_by_id(self, order_id: int, user_id: int):
        order = await self.order_repo.get_by_id(order_id)
        if not order:
            raise OrderNotFound()
        if order.user_id != user_id:
            raise OrderForbidden()
        return order

    async def get_user_orders(self, user_id: int):
        return await self.order_repo.get_user_orders(user_id)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(1, min=1, max=4),
        retry=retry_if_exception_type(OperationalError)
    )
    async def cancel_order(self, order_id: int, user_id: int):
        order = await self.order_repo.get_by_id(order_id)
        if not order:
            raise OrderNotFound()
        if order.user_id != user_id:
            raise OrderForbidden()

        transition_order_status(order, "cancelled")
        await self.order_repo.restore_stock(order.product_id, order.quantity)

        await self.db.commit()
        await self.db.refresh(order)
        return order

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(1, min=1, max=4),
        retry=retry_if_exception_type(OperationalError)
    )
    async def cancel_stale_orders(self, older_than_minutes: int = 15):
        stale_orders = await self.order_repo.get_stale_pending_orders(older_than_minutes)

        cancelled_count = 0
        for order in stale_orders:
            transition_order_status(order, "cancelled")
            await self.order_repo.restore_stock(order.product_id, order.quantity)
            cancelled_count += 1

        await self.db.commit()
        return cancelled_count
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(1, min=1, max=4),
        retry=retry_if_exception_type(OperationalError)
    )
    async def create_order(self, user_id: int, product_id: int, quantity: int, idempotency_key: str | None = None):
        key = idempotency_key or str(uuid.uuid4())

        existing_order = await self.order_repo.find_by_idempotency_key(key)
        if existing_order:
            return existing_order

        try:
            product = await self.order_repo.get_product(product_id)
            if not product:
                raise ProductNotFound()

            amount = product.price * quantity

            success = await self.order_repo.atomic_decrement_stock(product_id, quantity)
            if not success:
                raise OutOfStock()

            new_order = await self.order_repo.create(
                user_id=user_id,
                product_id=product_id,
                quantity=quantity,
                amount=amount,
                idempotency_key=key,
            )

            event = OutboxEvent(
                event_type="order_created",
                payload=json.dumps({
                    "order_id": new_order.id,
                    "user_id": user_id,
                    "amount": amount,
                    "product_id": product_id,
                    "quantity": quantity,
                }),
                status="pending",
            )
            self.db.add(event)

            await self.db.commit()
            await self.db.refresh(new_order)
            return new_order

        except IntegrityError:
            await self.db.rollback()
            existing_order = await self.order_repo.find_by_idempotency_key(key)
            return existing_order


class UserService(BaseService):
    def __init__(self,db:AsyncSession,redis_conn,policy:BaseUserPolicy):
        self.db = db
        self.redis=redis_conn
        self.policy=policy
        self.user_repo=UserRepository(db)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(1, min=1, max=4),
        retry=retry_if_exception_type(OperationalError)
    )
    async def get_all(self,user_filter:UserFilter):
        result=select(User)
        if self.policy.user.role != "admin":
            result = result.where(User.id == self.policy.user.id)
        user=user_filter.filter(result)
        return await paginate(self.db,user)
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(1, min=1, max=4),
        retry=retry_if_exception_type(OperationalError)
    )
    async def get_by_id(self,user_id:int):
        user=await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound()
        if not self.policy.can_read(user):
            raise UserForbidden()
        cache_key = f'user:{user_id}'
        try:
            cache_user=await self.redis.get(cache_key)
            if cache_user:
               return json.loads(cache_user)
        except Exception:
            pass
        user_data = UserOut.model_validate(user)
        user_json=user_data.model_dump()
        try:
             await self.redis.set(cache_key,user_data.model_dump_json(),ex=settings.REDIS_TIME)
        except Exception:
            pass
        return user_json
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(1, min=1, max=4),
        retry=retry_if_exception_type(OperationalError)
    )
    async def update(self,user_id:int,user_update:UpdateUser):
        user=await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound()
        if not self.policy.can_update(user):
            raise UserForbidden()
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
        user = await self.user_repo.get_by_id(user_id)
        return user
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(1, min=1, max=4),
        retry=retry_if_exception_type(OperationalError)
    )
    async def delete(self,user_id:int):
        user=await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound()
        if not self.policy.can_delete(user):
            raise UserForbidden()
        await log_action(
            self.db,
            actor_id=self.policy.user.id,
            action="user.delete",
            target_type="user",
            target_id=user_id,
            details={"deleted_username": user.username, "deleted_email": user.email},
        )
        await self.db.delete(user)
        await self.db.commit()
        await self.redis.delete(f'user:{user_id}')
        return user

class ProjectService(BaseService, CreateService):
    def __init__(self, db: AsyncSession, redis_conn, policy: BaseProjectPolicy):
        self.db = db
        self.redis = redis_conn
        self.policy = policy
        self.project_repo=ProjectRepository(db)
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(1, min=1, max=4),
        retry=retry_if_exception_type(OperationalError)
    )
    async def get_all(self, project_filter: ProjectFilter):
        result = select(Project)
        if self.policy.user.role != "admin":
            result = result.where(Project.owner_id == self.policy.user.id)
        project = project_filter.filter(result)
        return await paginate(self.db, project)
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(1, min=1, max=4),
        retry=retry_if_exception_type(OperationalError)
    )
    async def get_by_id(self, project_id: int):
        project = await self.project_repo.get_project_id(project_id)
        if not project:
            raise ProjectNotFound()
        if not self.policy.can_read(project):
            raise ProjectForbidden()
        cache_key = f'project:{project_id}'
        try:
            cache_project = await self.redis.get(cache_key)
            if cache_project:
               return json.loads(cache_project)
        except Exception:
            pass
        project_data = ProjectOut.model_validate(project).model_dump_json()
        try:
            await self.redis.set(cache_key, project_data, ex=settings.REDIS_TIME)
        except Exception:
            pass
        return project_data
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(1, min=1, max=4),
        retry=retry_if_exception_type(OperationalError)
    )
    async def create(self, project_in: CreateProject):
        project = await self.project_repo.get_title(project_in.title)
        if project:
            raise ProjectAlreadyExists()
        if not self.policy.can_create():
            raise ProjectForbidden()
        new_project = Project(title=project_in.title, owner_id=self.policy.user.id, created_at=project_in.created_at)
        self.db.add(new_project)
        await self.db.commit()
        await self.db.refresh(new_project)
        return new_project
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(1, min=1, max=4),
        retry=retry_if_exception_type(OperationalError)
    )
    async def update(self, project_id: int, project_update: UpdateProject):
        project = await self.project_repo.get_project_id(project_id)
        if not project:
            raise ProjectNotFound()
        if not self.policy.can_update(project):
            raise ProjectForbidden()
        if project_update.title is not None:
            project.title = project_update.title
        if project_update.created_at is not None:
            project.created_at = project_update.created_at
        await self.db.commit()
        await self.redis.delete(f'project:{project_id}')
        await self.db.refresh(project)
        return project
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(1, min=1, max=4),
        retry=retry_if_exception_type(OperationalError)
    )
    async def delete(self, project_id: int):
        project = await self.project_repo.get_project_id(project_id)
        if not project:
            raise ProjectNotFound()
        if not self.policy.can_delete(project):
            raise ProjectForbidden()
        await self.db.delete(project)
        await self.db.commit()
        await self.redis.delete(f'project:{project_id}')
        return project
class TaskService(BaseService,CreateService):
    def __init__(self,db:AsyncSession,redis_conn,policy:BaseTaskPolicy):
        self.db = db
        self.redis=redis_conn
        self.policy=policy
        self.task_repo=TaskRepository(db)
        self.project_repo=ProjectRepository(db)
        self.user_repo=UserRepository(db)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(1, min=1, max=4),
        retry=retry_if_exception_type(OperationalError)
    )
    async def get_all(self,task_filter:TaskFilter):
        result=select(Task)
        if self.policy.user.role != "admin":
            result=result.where(Task.assignee_id == self.policy.user.id)
        task=task_filter.filter(result)
        return await paginate(self.db,task)
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(1, min=1, max=4),
        retry=retry_if_exception_type(OperationalError)
    )
    async def get_by_id(self,task_id:int):
        task=await self.task_repo.get_by_id(task_id)
        if not task:
            raise TaskNotFound()
        if not self.policy.can_read(task):
            raise TaskForbidden()
        cache_key=f'task:{task_id}'
        try:
            cache_task=await self.redis.get(cache_key)
            if cache_task:
                return json.loads(cache_task)
        except Exception:
            pass
        task_pydantic=TaskOut.model_validate(task)
        task_data=task_pydantic.model_dump()
        try:
           await self.redis.set(cache_key,task_pydantic.model_dump_json(),ex=settings.REDIS_TIME)
        except Exception:
            pass
        return task_data
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(1, min=1, max=4),
        retry=retry_if_exception_type(OperationalError)
    )
    async def create(self,task_in:CreateTask):
        task=await self.task_repo.get_by_title_task(task_in.title)
        if task:
            raise TaskAlreadyExists()
        if not self.policy.can_create():
            raise TaskForbidden()
        project=await self.project_repo.get_project_title_to_task(task_in.project_id)
        if not project:
            raise ProjectNotFound()
        user=await self.user_repo.user_task_assignee_id(task_in.assignee_id)
        if not user:
            raise UserNotFound()
        new_task=Task(title=task_in.title,project_id=task_in.project_id,assignee_id=task_in.assignee_id or self.policy.user.id,created_at=task_in.created_at)
        self.db.add(new_task)
        await self.db.commit()
        await self.db.refresh(new_task)
        return new_task
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(1, min=1, max=4),
        retry=retry_if_exception_type(OperationalError)
    )
    async def update(self,task_id:int,task_in:UpdateTask):
        task=await self.task_repo.get_by_id(task_id)
        if not task:
            raise TaskNotFound()
        if not self.policy.can_update(task):
            raise TaskForbidden()
        if task_in.title is not None:
            task.title=task_in.title
        if task_in.created_at is not None:
            task.created_at=task_in.created_at
        await self.db.commit()
        await self.redis.delete(f'task:{task_id}')
        await self.db.refresh(task)
        return task
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(1, min=1, max=4),
        retry=retry_if_exception_type(OperationalError)
    )
    async def delete(self,task_id:int):
        task=await self.task_repo.get_by_id(task_id)
        if not task:
            raise TaskNotFound()
        if not self.policy.can_delete(task):
            raise TaskForbidden()
        await self.db.delete(task)
        await self.db.commit()
        await self.redis.delete(f'task:{task_id}')
        return task