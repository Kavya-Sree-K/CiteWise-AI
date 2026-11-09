import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bcrypt
from app.db import SessionLocal
from app.models import Role, User

username = input("Username: ").strip()
full_name = input("Full name: ").strip()
password = input("Password: ").strip()
role_name = input("Role (employee, hr, it, finance, legal, admin): ").strip().lower()

db = SessionLocal()
role = db.query(Role).filter(Role.name == role_name).first()

if not username or not password:
    print("Username and password cannot be empty.")
elif not role:
    print("That role does not exist.")
elif db.query(User).filter(User.username == username).first():
    print("That username already exists.")
else:
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    db.add(User(username=username, full_name=full_name or username,
                password_hash=hashed, role_id=role.id))
    db.commit()
    print(f"User '{username}' created with role '{role_name}'.")
db.close()