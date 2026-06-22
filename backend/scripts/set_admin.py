"""Crea o actualiza un usuario admin.

Uso:
    python -m backend.scripts.set_admin <email> <password> ["Nombre Completo"]

Escribe en la misma MongoDB (Atlas) que usa el backend, por lo que sirve
tanto en local como contra producción.
"""
import asyncio
import os
import sys
from datetime import datetime

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from backend.database import get_collection
from backend.auth import get_password_hash


async def set_admin(email: str, password: str, full_name: str):
    users = get_collection("users")
    hashed = get_password_hash(password)
    res = await users.update_one(
        {"email": email},
        {
            "$set": {
                "email": email,
                "full_name": full_name,
                "hashed_password": hashed,
                "is_active": True,
                "is_admin": True,
            },
            "$setOnInsert": {"created_at": datetime.utcnow()},
        },
        upsert=True,
    )
    action = "creado" if res.upserted_id else "actualizado"
    print(f"Admin {action}: {email}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python -m backend.scripts.set_admin <email> <password> [nombre]")
        sys.exit(1)
    _email = sys.argv[1]
    _password = sys.argv[2]
    _name = sys.argv[3] if len(sys.argv) > 3 else "Administrator"
    asyncio.run(set_admin(_email, _password, _name))
