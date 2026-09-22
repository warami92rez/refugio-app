import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    rol: Mapped[str] = mapped_column(String(20), default="usuario", nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    temas: Mapped[list["Tema"]] = relationship(back_populates="usuario")
    registros_reto: Mapped[list["RegistroReto"]] = relationship(back_populates="usuario")


class Tema(Base):
    __tablename__ = "temas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    usuario: Mapped["Usuario"] = relationship(back_populates="temas")


# --- Fase 2: modelos listos, aun sin vistas implementadas ---


class RetoSemanal(Base):
    __tablename__ = "retos_semanales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=True)
    fecha_inicio: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    fecha_fin: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)

    registros: Mapped[list["RegistroReto"]] = relationship(back_populates="reto")


class RegistroReto(Base):
    __tablename__ = "registros_reto"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    reto_id: Mapped[int] = mapped_column(ForeignKey("retos_semanales.id"), nullable=False)
    completado_en: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    usuario: Mapped["Usuario"] = relationship(back_populates="registros_reto")
    reto: Mapped["RetoSemanal"] = relationship(back_populates="registros")
