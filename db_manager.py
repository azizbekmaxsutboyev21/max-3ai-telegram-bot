import json
import os
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

DB_FILE = "bot_data.json"

class DatabaseManager:
    def __init__(self, filename: str = DB_FILE):
        self.filename = filename
        self.data: Dict[str, Any] = {
            "users": {},      # {user_id: {"name": str, "username": str, "joined_at": str}}
            "chats": {},      # {chat_id: {"title": str, "type": str, "username": str}}
        }
        self.load()

    def load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception as e:
                logger.error(f"Ma'lumotlar bazasini yuklashda xatolik: {e}")

    def save(self):
        try:
            with open(self.filename, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ma'lumotlarni saqlashda xatolik: {e}")

    def register_user(self, user_id: int, full_name: str, username: str = None):
        uid = str(user_id)
        if uid not in self.data["users"]:
            self.data["users"][uid] = {
                "name": full_name,
                "username": username,
            }
            self.save()

    def register_chat(self, chat_id: int, title: str, chat_type: str, username: str = None):
        cid = str(chat_id)
        self.data["chats"][cid] = {
            "title": title,
            "type": chat_type,
            "username": username,
        }
        self.save()

    def remove_chat(self, chat_id: int):
        cid = str(chat_id)
        if cid in self.data["chats"]:
            del self.data["chats"][cid]
            self.save()

    def get_users(self) -> Dict[str, Any]:
        return self.data.get("users", {})

    def get_chats(self) -> Dict[str, Any]:
        return self.data.get("chats", {})

    def get_stats(self) -> Dict[str, int]:
        users = self.data.get("users", {})
        chats = self.data.get("chats", {})
        groups = sum(1 for c in chats.values() if c.get("type") in ["group", "supergroup"])
        channels = sum(1 for c in chats.values() if c.get("type") == "channel")
        return {
            "total_users": len(users),
            "total_groups": groups,
            "total_channels": channels,
            "total_chats": len(chats)
        }

db = DatabaseManager()
