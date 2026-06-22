import os
from contextlib import contextmanager
from dotenv import load_dotenv
from sqlalchemy import Column, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = os.getenv("POSTGRES_PORT")
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
DATABASE_URL = (
    f"postgresql://{POSTGRES_USER}:"
    f"{POSTGRES_PASSWORD}@"
    f"{POSTGRES_HOST}:"
    f"{POSTGRES_PORT}/"
    f"{POSTGRES_DB}"
)

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class DocumentDB(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True)
    title = Column(String)
    content = Column(Text)
    source_type = Column(String)
    source_path = Column(String)

Base.metadata.create_all(bind=engine)

@contextmanager
def database():
    """Context manager for handling database sessions safely."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()