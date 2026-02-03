from sqlalchemy.orm import declarative_base,relationship
from sqlalchemy import Column, Integer, String, ForeignKey,Index,DateTime
from datetime import datetime


Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String(20), default="user")
    phone = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    projects = relationship("Project", back_populates="owner")
    tasks = relationship("Task", back_populates="assignee")
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
    project_id = Column(Integer, ForeignKey("projects.id"))
    assignee_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    project = relationship("Project", back_populates="tasks")
    assignee = relationship("User", back_populates="tasks")
    __table_args__ = (Index('idx_title',"title"),)
class RefreshTokenDB(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True)
    token = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    expires_at = Column(DateTime, nullable=False)
    user = relationship("User", back_populates="refresh_tokens")