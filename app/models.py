from datetime import datetime, date
from sqlalchemy import String, Integer, Float, Date, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base

class Role(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(200))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    is_active: Mapped[bool] = mapped_column(default=True)
    role: Mapped[Role] = relationship()

class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(255))
    department: Mapped[str] = mapped_column(String(50))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | superseded | archived
    sensitivity: Mapped[str] = mapped_column(String(20))               # Public | Internal | Confidential | Restricted
    owner: Mapped[str] = mapped_column(String(120))
    effective_date: Mapped[date] = mapped_column(Date)
    file_format: Mapped[str] = mapped_column(String(10))
    pages: Mapped[int] = mapped_column(Integer, default=1)
    file_hash: Mapped[str] = mapped_column(String(64), index=True)
    file_path: Mapped[str] = mapped_column(String(500))
    edge_case_note: Mapped[str] = mapped_column(String(200), default="")
    ingestion_status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class DocumentACL(Base):
    __tablename__ = "document_acl"
    __table_args__ = (UniqueConstraint("document_id", "role_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))

class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued | processing | done | failed
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(80))
    target: Mapped[str] = mapped_column(String(200), default="")
    result: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)



class Chunk(Base):
    __tablename__ = "chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    page: Mapped[int] = mapped_column(Integer, default=1)
    chunk_no: Mapped[int] = mapped_column(Integer, default=0)
    section: Mapped[str] = mapped_column(String(200), default="")
    text: Mapped[str] = mapped_column(Text)



class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(50))
    question: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30))     # answered | insufficient_evidence | chitchat | error
    answer: Mapped[str] = mapped_column(Text, default="")
    sources: Mapped[str] = mapped_column(Text, default="")   # saved as JSON text
    steps: Mapped[str] = mapped_column(Text, default="")     # saved as JSON text
    fallback: Mapped[bool] = mapped_column(default=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    # which chat this question belongs to (None for runs made before chats were stored)
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True)
    # model usage for this question (all model calls added together)
    llm_calls: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Conversation(Base):
    """One chat of one user. Only the owner can read it."""
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(120), default="New chat")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(10))            # user | assistant
    content: Mapped[str] = mapped_column(Text)               # user text is stored redacted
    run_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True)
    payload: Mapped[str] = mapped_column(Text, default="")   # JSON: sources, steps, details ...
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Feedback(Base):
    __tablename__ = "feedback"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"))
    username: Mapped[str] = mapped_column(String(80))
    rating: Mapped[int] = mapped_column(Integer)         # 1 = helpful, -1 = not helpful
    comment: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)



class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(20))          # archive | revoke
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    requested_by: Mapped[str] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="pending")   # pending | approved | rejected
    reviewed_by: Mapped[str] = mapped_column(String(80), default="")
    review_comment: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)



class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    to_username: Mapped[str] = mapped_column(String(80))
    to_email: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20))      # sent | failed
    detail: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)