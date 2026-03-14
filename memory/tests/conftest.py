import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import memory.database as database
from memory.database import Base, get_db
from memory.main import app
from memory.tests.seed_data import seed_test_catalog

# Use a file for tests to avoid thread issues with in-memory and StaticPool
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_api.db"

# Force environment variable for tests
os.environ["DATABASE_URL"] = SQLALCHEMY_DATABASE_URL

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Point the database module to our test engine
database.engine = engine
database.SessionLocal = TestingSessionLocal

@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    seed_test_catalog(db)
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db):
    from fastapi.testclient import TestClient
    def override_get_db():
        # In a real app with StaticPool, another session on same engine 
        # will see the same data even if it's a different session object,
        # but sharing the same session object is even safer for tests.
        try:
            yield db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
