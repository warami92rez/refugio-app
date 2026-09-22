import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/refugio_app"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def sync_schema(engine):
    """Agrega columnas nuevas a tablas ya existentes.

    Base.metadata.create_all solo crea tablas que faltan, no altera las
    que ya existen. Como el proyecto no usa Alembic, los cambios de
    columnas en modelos existentes se aplican aqui con DDL idempotente.
    """
    statements = [
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS rol VARCHAR(20) NOT NULL DEFAULT 'usuario'",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT TRUE",
    ]
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))