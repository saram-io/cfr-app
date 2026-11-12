from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from .config import DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
db_url = (
    DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
    if DATABASE_URL.startswith("postgresql://")
    else DATABASE_URL
)

engine = create_engine(db_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
