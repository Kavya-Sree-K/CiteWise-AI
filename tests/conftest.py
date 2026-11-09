import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Work on a COPY of the real database, so tests never touch your data.
_tmp = Path(tempfile.mkdtemp()) / "test.db"
_src, _dst = sqlite3.connect(ROOT / "knowledge.db"), sqlite3.connect(_tmp)
_src.backup(_dst)
_src.close()
_dst.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.as_posix()}"
os.environ["CHECKPOINT_DB"] = str(_tmp.with_name("checkpoints.sqlite"))
os.environ["OLLAMA_URL"] = "http://127.0.0.1:9"      # no AI model in tests: fast fallback
os.environ["EMBED_BACKEND"] = "hash"                       # no embedding model needed in tests
os.environ["CHROMA_PATH"] = str(Path(tempfile.mkdtemp()) / "chroma")
os.environ.pop("ANTHROPIC_API_KEY", None)

from fastapi.testclient import TestClient  # noqa: E402

PASSWORD = "TestPass123"


@pytest.fixture(scope="session", autouse=True)
def test_users():
    import bcrypt
    from app.db import SessionLocal
    from app.models import Role, User

    db = SessionLocal()
    hashed = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode()
    for username, role in [("testadmin_a", "admin"), ("testadmin_b", "admin"),
                           ("testemp", "employee"), ("testhr", "hr")]:
        if not db.query(User).filter(User.username == username).first():
            r = db.query(Role).filter(Role.name == role).first()
            db.add(User(username=username, full_name=username,
                        password_hash=hashed, role_id=r.id))
    db.commit()
    db.close()


@pytest.fixture(scope="session")
def sent_notifications():
    return []


@pytest.fixture(scope="session")
def client(tmp_path_factory, sent_notifications):
    import app.admin as admin_module
    admin_module.UPLOAD_DIR = tmp_path_factory.mktemp("uploads")
    admin_module.notify = lambda *args, **kwargs: sent_notifications.append(args)
    from app.main import app
    return TestClient(app)


def login(client, username):
    r = client.post("/login", json={"username": username, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"X-Token": r.json()["token"]}


@pytest.fixture(scope="session")
def admin_a(client):
    return login(client, "testadmin_a")


@pytest.fixture(scope="session")
def admin_b(client):
    return login(client, "testadmin_b")


@pytest.fixture(scope="session")
def emp(client):
    return login(client, "testemp")


@pytest.fixture(scope="session")
def hr(client):
    return login(client, "testhr")


@pytest.fixture()
def db():
    from app.db import SessionLocal
    session = SessionLocal()
    yield session
    session.close()