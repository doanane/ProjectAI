import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from mymain import Base, engine  # Import from your main file


def reset_database():
    """Drop all tables and recreate them with new schema"""
    print("🗑️  Dropping all tables...")
    Base.metadata.drop_all(bind=engine)

    print("🔄 Creating new tables...")
    Base.metadata.create_all(bind=engine)

    print("✅ Database reset successful!")


if __name__ == "__main__":
    reset_database()
