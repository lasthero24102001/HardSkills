from sqlalchemy.orm import declarative_base,relationship
from sqlalchemy import Column, Integer, String, ForeignKey,Index,DateTime,Boolean
from datetime import datetime, timezone

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String(20), default="user")
    created_at = Column(DateTime, default=datetime.utcnow)
    is_banned = Column(Boolean, default=False, nullable=False)
    projects = relationship("Project", back_populates="owner")
    tasks = relationship("Task", back_populates="assignee")
    orders = relationship("Order", back_populates="user")
    refresh_tokens = relationship(
        "RefreshTokenDB",
        back_populates="user",
        cascade="all, delete"
    )
    __table_args__ = (Index('idx_username_email',"username","email"),)
class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    owner = relationship("User", back_populates="projects")
    tasks = relationship(
        "Task",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    __table_args__ = (Index('idx_title_owner_id',"title","owner_id"),)
class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    status = Column(String(50), default="pending")
    description = Column(String(1000), nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    assignee_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    project = relationship("Project", back_populates="tasks")
    assignee = relationship("User", back_populates="tasks")
    __table_args__ = (Index('idx_title',"title"),)
class RefreshTokenDB(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True)
    token = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))
    # в Base1.py
    expires_at = Column(DateTime(timezone=True), nullable=False)
    user = relationship("User", back_populates="refresh_tokens")

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    price = Column(Integer, nullable=False)  # в тийинах
    stock = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    orders = relationship("Order", back_populates="product")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    idempotency_key = Column(String, unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    amount = Column(Integer, nullable=False)
    status = Column(String(20), default="pending", nullable=False)  # pending/paid/cancelled/refunded
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    user = relationship("User", back_populates="orders")
    product = relationship("Product", back_populates="orders")
    transactions = relationship("Transaction", back_populates="order")

    __table_args__ = (
        Index("idx_order_user_status", "user_id", "status"),
    )


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id = Column(Integer, primary_key=True)
    event_type = Column(String(100), nullable=False)
    payload = Column(String, nullable=False)
    status = Column(String(20), default="pending", nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    processed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_outbox_status_created", "status", "created_at"),
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    provider = Column(String(20), nullable=False)  # "payme" / "click"
    provider_transaction_id = Column(String, unique=True, nullable=True)
    amount = Column(Integer, nullable=False)
    state = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    performed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)

    order = relationship("Order", back_populates="transactions")

    __table_args__ = (
        Index("idx_transaction_provider", "provider", "provider_transaction_id"),



    )

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # кто совершил действие (nullable — на случай системных действий)
    action = Column(String(100), nullable=False)          # напр. "user.delete", "user.ban", "project.delete"
    target_type = Column(String(50), nullable=True)        # "user" / "project" / "task"
    target_id = Column(Integer, nullable=True)
    details = Column(String(1000), nullable=True)          # JSON-строка с доп. контекстом (что именно изменилось)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    actor = relationship("User", foreign_keys=[actor_id])

    __table_args__ = (
        Index("idx_audit_actor_created", "actor_id", "created_at"),
        Index("idx_audit_action", "action"),
    )

class RequestLog(Base):
    __tablename__ = "request_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    method = Column(String(10), nullable=False)
    path = Column(String(255), nullable=False)
    status_code = Column(Integer, nullable=False)
    duration_ms = Column(Integer, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index("idx_reqlog_user_created", "user_id", "created_at"),
        Index("idx_reqlog_path", "path"),
        Index("idx_reqlog_status", "status_code"),
        Index("idx_reqlog_created", "created_at"),
    )