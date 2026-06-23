import pymysql
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Auto-create database if not exists
try:
    conn = pymysql.connect(
        host=settings.DATABASE_HOST,
        user=settings.DATABASE_USER,
        password=settings.DATABASE_PASSWORD,
        port=int(settings.DATABASE_PORT)
    )
    cursor = conn.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {settings.DATABASE_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    conn.commit()
    cursor.close()
    conn.close()
    print(f"Database '{settings.DATABASE_NAME}' checked/created successfully.")
except Exception as e:
    print(f"Error checking/creating database: {e}")

engine = create_engine(
    settings.db_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
