from datetime import datetime, timezone
from typing import Optional, List, Any, Dict
from sqlalchemy import Integer, String, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    website: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    leads: Mapped[List["Lead"]] = relationship("Lead", back_populates="client", cascade="all, delete-orphan")


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id"), nullable=False)
    project_description: Mapped[str] = mapped_column(Text, nullable=False)
    budget: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    deadline: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    thread_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="processing")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    client: Mapped["Client"] = relationship("Client", back_populates="leads")
    proposals: Mapped[List["Proposal"]] = relationship("Proposal", back_populates="lead", cascade="all, delete-orphan")


class Proposal(Base):
    __tablename__ = "proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("leads.id"), nullable=False)
    research_summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    retrieved_case_ids: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    proposal_content: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    critic_logs: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    iterations_count: Mapped[int] = mapped_column(Integer, default=1)
    human_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    human_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    lead: Mapped["Lead"] = relationship("Lead", back_populates="proposals")