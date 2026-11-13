"""Relational schema (PostgreSQL). Structured facts live here; vectors live in Qdrant.

Design notes:
- school_id NULL on a document = university-wide (applies to every school).
- document_versions lets one policy have many versions; only one is `is_current`.
- chunks keep page numbers so every answer can cite "document, page".
- chunks.tsv is a full-text-search column (keyword half of hybrid search).
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (JSON, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text,
                        func)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class School(Base):
    __tablename__ = "schools"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)  # e.g. SoAI
    name: Mapped[str] = mapped_column(String(200), unique=True)
    programmes: Mapped[list["Programme"]] = relationship(back_populates="school")


class Programme(Base):
    __tablename__ = "programmes"
    id: Mapped[str] = mapped_column(String(160), primary_key=True)  # slug
    name: Mapped[str] = mapped_column(String(300))
    school_id: Mapped[str | None] = mapped_column(ForeignKey("schools.id"), nullable=True)
    level: Mapped[str | None] = mapped_column(String(10))  # UG / PG / PhD / Diploma
    duration: Mapped[str | None] = mapped_column(String(60))
    credits: Mapped[str | None] = mapped_column(String(60))
    specialisations: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(500))
    school: Mapped[School | None] = relationship(back_populates="programmes")


class AdmissionCriteria(Base):
    __tablename__ = "admission_criteria"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    programme_name: Mapped[str] = mapped_column(String(300))
    programme_id: Mapped[str] = mapped_column(String(160), index=True)
    school_id: Mapped[str | None] = mapped_column(ForeignKey("schools.id"))
    academic_year: Mapped[str | None] = mapped_column(String(10))
    eligibility_text: Mapped[str] = mapped_column(Text)
    nri_text: Mapped[str | None] = mapped_column(Text)
    selection_text: Mapped[str | None] = mapped_column(Text)
    rules: Mapped[dict] = mapped_column(JSON)  # machine-checkable fields used by the rule engine
    source_url: Mapped[str] = mapped_column(String(500))


class FeeStructure(Base):
    __tablename__ = "fee_structures"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    programme_name: Mapped[str] = mapped_column(String(300))
    programme_id: Mapped[str] = mapped_column(String(160), index=True)
    academic_year: Mapped[str | None] = mapped_column(String(10))
    tuition_by_year: Mapped[dict | None] = mapped_column(JSON)
    total_tuition: Mapped[int | None] = mapped_column(Integer)
    tables: Mapped[list] = mapped_column(JSON)
    other_charges: Mapped[list | None] = mapped_column(JSON)
    notes: Mapped[list | None] = mapped_column(JSON)
    source_url: Mapped[str] = mapped_column(String(500))


class Document(Base):
    """A logical policy/document family, e.g. 'Academic Calendar' or 'Refund Policy'."""
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family: Mapped[str] = mapped_column(String(200), index=True)  # normalised key for versioning
    title: Mapped[str] = mapped_column(String(400))
    category: Mapped[str] = mapped_column(String(60))  # academic, exam, attendance, fees, ...
    school_id: Mapped[str | None] = mapped_column(ForeignKey("schools.id"), nullable=True)
    audience: Mapped[str] = mapped_column(String(30), default="all")  # all / prospective / enrolled
    status: Mapped[str] = mapped_column(String(20), default="approved")  # pending/approved/rejected
    versions: Mapped[list["DocumentVersion"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    version_label: Mapped[str] = mapped_column(String(60))  # e.g. "2025-26" or "2024-05"
    academic_year: Mapped[str | None] = mapped_column(String(10))
    published_on: Mapped[date | None] = mapped_column(Date)  # from upload path yyyy/mm when nothing better
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("document_versions.id"), nullable=True)
    source_url: Mapped[str] = mapped_column(String(500))
    file_path: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str | None] = mapped_column(String(64))
    pages: Mapped[int | None] = mapped_column(Integer)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    document: Mapped[Document] = relationship(back_populates="versions")


class Chunk(Base):
    __tablename__ = "chunks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("document_versions.id", ondelete="CASCADE"), index=True)
    page: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(300))
    text: Mapped[str] = mapped_column(Text)
    tsv: Mapped[str | None] = mapped_column(TSVECTOR)
    __table_args__ = (Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),)


class Conflict(Base):
    __tablename__ = "conflicts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic: Mapped[str] = mapped_column(String(200))
    chunk_a: Mapped[int] = mapped_column(ForeignKey("chunks.id", ondelete="CASCADE"))
    chunk_b: Mapped[int] = mapped_column(ForeignKey("chunks.id", ondelete="CASCADE"))
    explanation: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open / resolved / dismissed
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20))  # prospective / student / faculty / admin
    password_hash: Mapped[str] = mapped_column(String(200))
    profile: Mapped[dict] = mapped_column(JSON, default=dict)  # school, programme, semester, ...


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    detail: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
