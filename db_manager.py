import json
import os
import time
import logging
from typing import Dict, List, Any, Optional

import config

logger = logging.getLogger(__name__)

DB_FILE = "bot_data.json"

DEFAULT_AGENT_PROMPT = (
    "Hozir men biroz bandman yoki yo'ldaman. "
    "Menga yozgan insonga o'ta samimiy, xushmuomala va tabiiy tarzda javob qaytaring. "
    "Muhim savollarga imkon qadar yordam bering, zarur bo'lsa tez orada o'zim ko'rib chiqishimni ayting. "
    "Javoblaringiz ixcham, do'stona va samimiy bo'lsin. "
    "AGAR suhbat davom etayotgan bo'lsa, qayta-qayta 'salom' deb salomlashmang!"
)

DEFAULT_OWNER_INFO = (
    "Ism: Azizbek. Kasb: Dasturchi va AI muhandisi. "
    "Telegram akkaunt egasi. O'zbek va rus tillarida erkin muloqot qiladi."
)

DEFAULT_PERSONA = {
    "owner_name": "Azizbek",
    "about_me": "Dasturchi, IT mutaxassisi va AI muhandisi.",
    "communication_style": "Samimiy, madaniyatli, do'stona, lo'nda va insoniy.",
    "custom_rules": "Hech qachon o'zingizni bot deb aytmang. Suhbatdosh bilan har bir xabarda qayta salomlashmang."
}

class DatabaseManager:
    def __init__(self, filename: str = DB_FILE):
        self.filename = filename
        self.data: Dict[str, Any] = {
            "users": {},      # {user_id: {"name": str, "username": str, "joined_at": str}}
            "chats": {},      # {chat_id: {"title": str, "type": str, "username": str}}
            "auth": {
                "access_code": config.get_access_code(),
                "authenticated_users": []
            },
            "persona": DEFAULT_PERSONA.copy(),
            "agent_settings": {
                "enabled": True,
                "mode": "as_me",     # "as_me" (to'g'ridan-to'g'ri mening nomimdan) yoki "assistant" (yordamchi sifatida)
                "prompt": DEFAULT_AGENT_PROMPT,
                "owner_info": DEFAULT_OWNER_INFO,
                "blacklist": {},     # {user_id_str: {"name": str, "username": str, "date": str}}
                "replied_count": 0,
                "smart_filter": True, # Keraksiz/spam xabarlarga javob bermaslik
                "debounce_seconds": 4 # Bir vaqtda yozilgan xabarlarni birlashtirish
            }
        }
        self.load()

    def load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self.data.update(loaded)
                    
                    # Auth sozlamalari
                    if "auth" not in self.data:
                        self.data["auth"] = {
                            "access_code": config.get_access_code(),
                            "authenticated_users": []
                        }
                    else:
                        self.data["auth"].setdefault("access_code", config.get_access_code())
                        self.data["auth"].setdefault("authenticated_users", [])

                    # Persona (Moslashuvchanlik) sozlamalari
                    if "persona" not in self.data:
                        self.data["persona"] = DEFAULT_PERSONA.copy()
                    else:
                        for k, v in DEFAULT_PERSONA.items():
                            self.data["persona"].setdefault(k, v)

                    # Agent sozlamalari
                    if "agent_settings" not in self.data:
                        self.data["agent_settings"] = {
                            "enabled": True,
                            "mode": "as_me",
                            "prompt": DEFAULT_AGENT_PROMPT,
                            "owner_info": DEFAULT_OWNER_INFO,
                            "blacklist": {},
                            "replied_count": 0,
                            "smart_filter": True,
                            "debounce_seconds": 4
                        }
                    else:
                        self.data["agent_settings"].setdefault("mode", "as_me")
                        self.data["agent_settings"].setdefault("prompt", DEFAULT_AGENT_PROMPT)
                        self.data["agent_settings"].setdefault("owner_info", DEFAULT_OWNER_INFO)
                        self.data["agent_settings"].setdefault("smart_filter", True)
                        self.data["agent_settings"].setdefault("debounce_seconds", 4)
                        # Blacklist formatini normallashtirish (agar ro'yxat bo'lsa dictga o'tkazish)
                        bl = self.data["agent_settings"].get("blacklist", {})
                        if isinstance(bl, list):
                            new_bl = {}
                            for uid in bl:
                                new_bl[str(uid)] = {"name": f"ID: {uid}", "username": "", "date": "Avval kiritilgan"}
                            self.data["agent_settings"]["blacklist"] = new_bl
            except Exception as e:
                logger.error(f"Ma'lumotlar bazasini yuklashda xatolik: {e}")

    def save(self):
        try:
            with open(self.filename, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ma'lumotlarni saqlashda xatolik: {e}")

    # ---------------- FOYDALANUVCHILAR VA CHATLAR ----------------
    def register_user(self, user_id: int, full_name: str, username: Optional[str] = None):
        uid = str(user_id)
        if uid not in self.data["users"]:
            self.data["users"][uid] = {
                "name": full_name,
                "username": username or "",
                "joined_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            self.save()

    def register_chat(self, chat_id: int, title: str, chat_type: str, username: Optional[str] = None):
        cid = str(chat_id)
        self.data["chats"][cid] = {
            "title": title,
            "type": chat_type,
            "username": username or "",
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
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

    # ---------------- PERSONA & MOSLASHISH (ADAPTATION) ----------------
    def get_persona(self) -> Dict[str, str]:
        return self.data.get("persona", DEFAULT_PERSONA.copy())

    def update_persona(self, key: str, value: str):
        if "persona" not in self.data:
            self.data["persona"] = DEFAULT_PERSONA.copy()
        self.data["persona"][key] = value.strip()
        self.save()

    def set_full_adaptation(self, about: str, style: str = "", rules: str = ""):
        if "persona" not in self.data:
            self.data["persona"] = DEFAULT_PERSONA.copy()
        if about:
            self.data["persona"]["about_me"] = about.strip()
            self.data["agent_settings"]["owner_info"] = about.strip()
        if style:
            self.data["persona"]["communication_style"] = style.strip()
        if rules:
            self.data["persona"]["custom_rules"] = rules.strip()
        self.save()

    # ---------------- AI AGENT SOZLAMALARI ----------------
    def is_agent_enabled(self) -> bool:
        return self.data.get("agent_settings", {}).get("enabled", True)

    def set_agent_enabled(self, enabled: bool):
        if "agent_settings" not in self.data:
            self.data["agent_settings"] = {}
        self.data["agent_settings"]["enabled"] = enabled
        self.save()

    def is_smart_filter_enabled(self) -> bool:
        return self.data.get("agent_settings", {}).get("smart_filter", True)

    def set_smart_filter(self, enabled: bool):
        if "agent_settings" not in self.data:
            self.data["agent_settings"] = {}
        self.data["agent_settings"]["smart_filter"] = enabled
        self.save()

    def get_agent_prompt(self) -> str:
        return self.data.get("agent_settings", {}).get("prompt", DEFAULT_AGENT_PROMPT)

    def set_agent_prompt(self, prompt: str):
        if "agent_settings" not in self.data:
            self.data["agent_settings"] = {}
        self.data["agent_settings"]["prompt"] = prompt.strip()
        self.save()

    # ---------------- QORA RO'YXAT (BLACKLIST) ----------------
    def get_agent_blacklist(self) -> List[int]:
        bl = self.data.get("agent_settings", {}).get("blacklist", {})
        if isinstance(bl, dict):
            return [int(uid) for uid in bl.keys() if uid.lstrip("-").isdigit()]
        elif isinstance(bl, list):
            return [int(uid) for uid in bl if str(uid).lstrip("-").isdigit()]
        return []

    def get_blacklist_detailed(self) -> List[Dict[str, Any]]:
        """Qora ro'yxatdagilar haqida to'liq ma'lumot"""
        bl = self.data.get("agent_settings", {}).get("blacklist", {})
        result = []
        if isinstance(bl, dict):
            for uid, info in bl.items():
                result.append({
                    "id": int(uid),
                    "name": info.get("name", "Nomsiz"),
                    "username": info.get("username", ""),
                    "date": info.get("date", "")
                })
        elif isinstance(bl, list):
            for uid in bl:
                result.append({
                    "id": int(uid),
                    "name": f"ID: {uid}",
                    "username": "",
                    "date": ""
                })
        return result

    def add_to_blacklist(self, user_id: int, name: str = "", username: str = ""):
        if "agent_settings" not in self.data:
            self.data["agent_settings"] = {}
        bl = self.data["agent_settings"].setdefault("blacklist", {})
        if isinstance(bl, list):
            new_bl = {str(uid): {"name": f"ID: {uid}", "username": "", "date": ""} for uid in bl}
            self.data["agent_settings"]["blacklist"] = new_bl
            bl = new_bl

        uid_str = str(user_id)
        bl[uid_str] = {
            "name": name or f"Foydalanuvchi ({user_id})",
            "username": username or "",
            "date": time.strftime("%Y-%m-%d %H:%M")
        }
        self.save()

    def remove_from_blacklist(self, user_id: int) -> bool:
        if "agent_settings" not in self.data:
            return False
        bl = self.data["agent_settings"].get("blacklist", {})
        uid_str = str(user_id)
        if isinstance(bl, dict) and uid_str in bl:
            del bl[uid_str]
            self.save()
            return True
        elif isinstance(bl, list) and user_id in bl:
            bl.remove(user_id)
            self.save()
            return True
        return False

    def is_blacklisted(self, user_id: int) -> bool:
        bl = self.data.get("agent_settings", {}).get("blacklist", {})
        uid_str = str(user_id)
        if isinstance(bl, dict):
            return uid_str in bl
        elif isinstance(bl, list):
            return user_id in bl
        return False

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
            "smart_filter": self.is_smart_filter_enabled(),
            "replied_count": self.data.get("agent_settings", {}).get("replied_count", 0),
            "blacklist_count": len(self.get_agent_blacklist())
        }

    # ---------------- XAVFSIZLIK VA AUTENTIFIKATSIYA ----------------
    def get_access_code(self) -> str:
        code = self.data.get("auth", {}).get("access_code")
        if not code:
            code = config.get_access_code()
            if "auth" not in self.data:
                self.data["auth"] = {}
            self.data["auth"]["access_code"] = code
            self.save()
        return str(code).strip()

    def set_access_code(self, new_code: str):
        if "auth" not in self.data:
            self.data["auth"] = {}
        self.data["auth"]["access_code"] = str(new_code).strip()
        self.save()

    def is_authenticated(self, user_id: int) -> bool:
        """Foydalanuvchi tasdiqlangan adminmi?"""
        if user_id == config.CREATOR_ID:
            return True
        auth_users = self.data.get("auth", {}).get("authenticated_users", [])
        return user_id in auth_users

    def set_authenticated(self, user_id: int, status: bool):
        if "auth" not in self.data:
            self.data["auth"] = {"access_code": config.get_access_code(), "authenticated_users": []}
        auth_users = self.data["auth"].setdefault("authenticated_users", [])
        if status:
            if user_id not in auth_users:
                auth_users.append(user_id)
        else:
            if user_id in auth_users:
                auth_users.remove(user_id)
        self.save()

db = DatabaseManager()
