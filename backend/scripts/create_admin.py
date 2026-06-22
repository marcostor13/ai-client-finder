import asyncio
import os
import sys

# Add root directory to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from backend.database import get_collection
from backend.auth import get_password_hash
from datetime import datetime

async def create_admin():
    users_collection = get_collection("users")
    
    admin_email = "admin@example.com"
    admin_password = "adminpassword123"
    
    # Check if admin already exists
    existing_user = await users_collection.find_one({"email": admin_email})
    if existing_user:
        print(f"Admin user {admin_email} already exists.")
        return

    admin_user = {
        "email": admin_email,
        "full_name": "System Administrator",
        "hashed_password": get_password_hash(admin_password),
        "is_active": True,
        "is_admin": True,
        "created_at": datetime.utcnow()
    }
    
    await users_collection.insert_one(admin_user)
    print(f"Admin user created successfully!")
    print(f"Email: {admin_email}")
    print(f"Password: {admin_password}")

if __name__ == "__main__":
    asyncio.run(create_admin())
