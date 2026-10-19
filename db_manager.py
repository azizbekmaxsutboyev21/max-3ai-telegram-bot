import json
import os
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

DB_FILE = "bot_data.json"

DEFAULT_AGENT_PROMPT = (
    "Hozir men biroz bandman yoki yo'ldaman. "
    "Menga yozgan insonga o'ta samimiy, xushmuomala va tabiiy tarzda javob qaytaring. "
    "Muhim savollarga imkon qadar yordam bering, zarur bo'lsa tez orada o'zim ko'rib chiqishimni ayting. "
    "Javoblaringiz ixcham, do'stona va samimiy bo'lsin."
)

DEFAULT_OWNER_INFO = (
    "Ism: Azizbek. Kasb: Dasturchi va AI muhandisi. "
    "Telegram akkaunt egasi. O'zbek va rus tillarida erkin muloqot qiladi."
)

class DatabaseManager:
    def __init__(self, filename: str = DB_FILE):
        self.filename = filename
        self.data: Dict[str, Any] = {
            "users": {},      # {user_id: {"name": str, "username": str, "joined_at": str}}
            "chats": {},      # {chat_id: {"title": str, "type": str, "username": str}}
            "agent_settings": {
                "enabled": True,
                "mode": "as_me",     # "as_me" (to'g'ridan-to'g'ri mening nomimdan) yoki "assistant" (yordamchi sifatida)
                "prompt": DEFAULT_AGENT_PROMPT,
                "owner_info": DEFAULT_OWNER_INFO,
                "blacklist": [],
                "replied_count": 0
            }
        }
        self.load()

    def load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self.data.update(loaded)
                    if "agent_settings" not in self.data:
                        self.data["agent_settings"] = {
                            "enabled": True,
                            "mode": "as_me",
                            "prompt": DEFAULT_AGENT_PROMPT,
                            "owner_info": DEFAULT_OWNER_INFO,
                            "blacklist": [],
                            "replied_count": 0
                        }
                    else:
                        self.data["agent_settings"].setdefault("mode", "as_me")
                        self.data["agent_settings"].setdefault("owner_info", DEFAULT_OWNER_INFO)
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

    # ---------------- AI AGENT SOZLAMALARI ----------------
    def is_agent_enabled(self) -> bool:
        return self.data.get("agent_settings", {}).get("enabled", True)

    def set_agent_enabled(self, enabled: bool):
        if "agent_settings" not in self.data:
            self.data["agent_settings"] = {}
        self.data["agent_settings"]["enabled"] = enabled
        self.save()

    def get_agent_prompt(self) -> str:
        return self.data.get("agent_settings", {}).get("prompt", DEFAULT_AGENT_PROMPT)

    def set_agent_prompt(self, prompt: str):
        if "agent_settings" not in self.data:
            self.data["agent_settings"] = {}
        self.data["agent_settings"]["prompt"] = prompt.strip()
        self.save()

    def get_agent_blacklist(self) -> List[int]:
        return self.data.get("agent_settings", {}).get("blacklist", [])

    def add_to_blacklist(self, user_id: int):
        if "agent_settings" not in self.data:
            self.data["agent_settings"] = {}
        bl = self.data["agent_settings"].setdefault("blacklist", [])
        if user_id not in bl:
            bl.append(user_id)
            self.save()

    def remove_from_blacklist(self, user_id: int):
        if "agent_settings" not in self.data:
            return
        bl = self.data["agent_settings"].get("blacklist", [])
        if user_id in bl:
            bl.remove(user_id)
            self.save()

    def is_blacklisted(self, user_id: int) -> bool:
        return user_id in self.data.get("agent_settings", {}).get("blacklist", [])

    def increment_agent_stat(self):
        if "agent_settings" not in self.data:
            self.data["agent_settings"] = {}
        self.data["agent_settings"]["replied_count"] = self.data["agent_settings"].get("replied_count", 0) + 1
        self.save()

    def get_agent_mode(self) -> str:
        return self.data.get("agent_settings", {}).get("mode", "as_me")

    def set_agent_mode(self, mode: str):
        if "agent_settings" not in self.data:
            self.data["agent_settings"] = {}
        self.data["agent_settings"]["mode"] = mode
        self.save()

    def get_owner_info(self) -> str:
        return self.data.get("agent_settings", {}).get("owner_info", DEFAULT_OWNER_INFO)

    def set_owner_info(self, info: str):
        if "agent_settings" not in self.data:
            self.data["agent_settings"] = {}
        self.data["agent_settings"]["owner_info"] = info.strip()
        self.save()

    def get_agent_stats(self) -> Dict[str, Any]:
        return {
            "enabled": self.is_agent_enabled(),
            "mode": self.get_agent_mode(),
            "owner_info": self.get_owner_info(),
            "replied_count": self.data.get("agent_settings", {}).get("replied_count", 0),
            "blacklist_count": len(self.get_agent_blacklist())
        }

db = DatabaseManager()
