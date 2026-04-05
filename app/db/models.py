from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func
from app.db.database import Base

class BitrixInstallation(Base):
    __tablename__ = 'bitrix_installations'

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(String(255), unique=True, index=True, nullable=True)
    domain = Column(String(255), unique=True, index=True, nullable=False)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    application_token = Column(Text, nullable=True)
    scope = Column(String(255), nullable=True)
    client_endpoint = Column(Text, nullable=True)
    server_endpoint = Column(Text, nullable=True)
    status = Column(String(10), nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class TaskLog(Base):
    __tablename__ = 'task_logs'

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String(255), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    responsible_id = Column(Integer, nullable=False)
    creator_id = Column(Integer, nullable=False)
    bitrix_task_id = Column(Integer, nullable=True)
    status = Column(String(50), nullable=False, default='pending')
    error_text = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
