import os
import json

DATA_DIR = "/app/data"
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
USER_DATA_FILE = os.path.join(DATA_DIR, "user_data.json")

default_config = {
    "api_configs": [
        {"url": "https://api.openai.com/v1", "keys": [], "model": "gpt-3.5-turbo"}
    ],
    "bot_tokens": [],
    "default_settings": {
        "system_prompts": ["你是一个非常有用的 Discord 助手。"],
        "temperature": 0.8,
        "knowledge": [],
        "custom_events": []
    },
    "bot_settings": {}
}

def load_config():
    if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        return default_config
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            if "bot_settings" not in config: config["bot_settings"] = {}
            if "default_settings" not in config: config["default_settings"] = default_config["default_settings"]
            if "custom_events" not in config["default_settings"]: config["default_settings"]["custom_events"] = []
            return config
    except: return default_config

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

def get_bot_config(config, token):
    return config["bot_settings"].get(token, config["default_settings"])

def load_user_data():
    if not os.path.exists(USER_DATA_FILE): return {}
    try:
        with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            new_data = {}
            for uid, content in data.items():
                # 数据结构迁移/补全
                if isinstance(content, str):
                    new_data[uid] = {"card": content, "favorability": 0, "rpg": {"lv": 1, "hp": 100, "atk": 10}, "gold": 0, "equip": {"weapon": "无", "armor": "无"}}
                else:
                    if "rpg" not in content: content["rpg"] = {"lv": 1, "hp": 100, "atk": 10}
                    if "gold" not in content: content["gold"] = 0
                    if "equip" not in content: content["equip"] = {"weapon": "无", "armor": "无"}
                    if "favorability" not in content: content["favorability"] = 0
                    new_data[uid] = content
            return new_data
    except: return {}

def save_user_data(data):
    with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)