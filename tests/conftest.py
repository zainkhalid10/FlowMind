import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session")
def app():
    from flowmind import app as fastapi_app

    return fastapi_app


@pytest.fixture(scope="session")
def test_engine(tmp_path_factory):
    from database import Base

    db_dir = tmp_path_factory.mktemp("flowmind_test_db")
    db_path = db_dir / "test_flowmind.db"
    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        engine.dispose()
        try:
            os.remove(db_path)
        except OSError:
            pass


@pytest.fixture(scope="session")
def TestingSessionLocal(test_engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture
def db_session(TestingSessionLocal):
    from database import (
        Feature,
        IntegrationConfig,
        ParsedFile,
        ReviewAssignment,
        ReviewFeedback,
        User,
    )

    db = TestingSessionLocal()
    try:
        manager = User(
            email="manager_test@flowmind.local",
            username="manager_test",
            hashed_password="test",
            role="manager",
            is_active=1,
        )
        client = User(
            email="client_test@flowmind.local",
            username="client_test",
            hashed_password="test",
            role="client",
            is_active=1,
        )
        db.add_all([manager, client])
        db.commit()
        db.refresh(manager)
        db.refresh(client)

        yield {
            "db": db,
            "manager": manager,
            "client": client,
        }
    finally:
        db.query(ReviewFeedback).delete()
        db.query(ReviewAssignment).delete()
        db.query(Feature).delete()
        db.query(ParsedFile).delete()
        db.query(IntegrationConfig).delete()
        db.query(User).delete()
        db.commit()
        db.close()


@pytest.fixture
def auth_state(db_session):
    return {"user_id": db_session["manager"].id}


@pytest.fixture
def client(app, TestingSessionLocal, auth_state):
    import auth

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_get_current_user():
        db = TestingSessionLocal()
        try:
            user = db.query(auth.User).filter(auth.User.id == auth_state["user_id"]).first()
            if not user:
                raise RuntimeError("Test user not found")
            return user
        finally:
            db.close()

    app.dependency_overrides[auth.get_db] = override_get_db
    app.dependency_overrides[auth.get_current_user] = override_get_current_user

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
