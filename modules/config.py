import os
import json
import hashlib

DATA_DIR = "/app/data"
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
USER_DATA_FILE = os.path.join(DATA_DIR, "user_data.json")

# --- 新增：指令与模块的定义 (用于前端渲染和后端权限判断) ---
# 格式: "模块key": {"label": "显示名称", "commands": {"指令名": "描述"}}
MODULE_DEFINITIONS = {
    "chat": {
        "label": "💬 智能聊天 (LLM)",
        "desc": "核心对话功能 (上下文记忆/自动回复)",
        "commands": {} # Chat 是被动触发，没有 Slash Command
    },
    "rpg": {
        "label": "⚔️ RPG 游戏系统",
        "desc": "战斗、经济与探索",
        "commands": {
            "商店": "购买装备/礼物/药水",
            "决斗": "发起赌钱或赌命的战斗",
            "探索": "随机事件检定 (D100)",
            "自定义探索": "创建新的探索事件",
            "我的数据": "查看属性/好感度评价"
        }
    },
    "utility": {
        "label": "🔧 实用工具",
        "desc": "名片与辅助功能",
        "commands": {
            "名片": "设置个人背景/人设",
            "提醒": "设置倒计时提醒",
            "总结": "AI 总结聊天记录"
        }
    },
    "admin": {
        "label": "🛡️ 管理员指令",
        "desc": "维护与作弊",
        "commands": {
            "修改好感度": "强制修改玩家好感",
            "清除名片": "重置玩家人设",
            "清理": "批量删除消息"
        }
    }
}

default_config = {
    "api_configs": [
        {"url": "https://api.openai.com/v1", "keys": [], "model": "gpt-3.5-turbo"}
    ],
    "bot_tokens": [],
    "default_settings": {
        "system_prompts": ["你是一个非常有用的 Discord 助手。"],
        "temperature": 0.8,
        "knowledge": [],
        "custom_events": [],
        # 变更：默认开启所有核心指令
        "enabled_commands": ["chat", "商店", "决斗", "探索", "自定义探索", "我的数据", "名片", "提醒", "总结", "修改好感度", "清除名片", "清理"]
    },
    "bot_settings": {}
}

def get_token_hash(token):
    """生成Token的短哈希，作为数据隔离的Key，避免明文Token作为Key"""
    if not token: return "default"
    return hashlib.md5(token.strip().encode()).hexdigest()[:10]

def load_config():
    if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        return default_config
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            
            # --- 兼容性迁移逻辑 ---
            # 将旧的 enabled_modules 转换为 enabled_commands
            def migrate_settings(settings):
                if "enabled_modules" in settings:
                    cmds = []
                    mods = settings.pop("enabled_modules")
                    if "chat" in mods: cmds.append("chat")
                    if "rpg" in mods: cmds.extend(MODULE_DEFINITIONS["rpg"]["commands"].keys())
                    if "utility" in mods: cmds.extend(MODULE_DEFINITIONS["utility"]["commands"].keys())
                    if "admin" in mods: cmds.extend(MODULE_DEFINITIONS["admin"]["commands"].keys())
                    settings["enabled_commands"] = list(set(cmds)) # 去重
                # 确保字段存在
                if "enabled_commands" not in settings:
                     settings["enabled_commands"] = default_config["default_settings"]["enabled_commands"]

            migrate_settings(config.get("default_settings", {}))
            for token in config.get("bot_settings", {}):
                migrate_settings(config["bot_settings"][token])
                
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
            return json.load(f)
    except: return {}

def save_user_data(data):
    with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_player_data(user_data, uid, bot_token):
    """
    核心隔离函数：获取指定用户在指定Bot下的数据。
    数据结构变更: 
    旧: user_data[uid] = { gold: 100, ... }
    新: user_data[uid] = { "token_hash_A": { gold: 100, ... }, "token_hash_B": { ... } }
    """
    uid = str(uid)
    token_hash = get_token_hash(bot_token)
    
    if uid not in user_data:
        user_data[uid] = {}
        
    # 兼容性处理：如果发现旧版数据结构（直接包含gold字段），将其归档到当前Bot或默认位置
    if "gold" in user_data[uid] or "rpg" in user_data[uid]: 
        old_content = user_data[uid].copy()
        # 清空旧结构，建立新结构
        user_data[uid] = {token_hash: old_content} 
    
    # 初始化该 Bot 下的数据
    if token_hash not in user_data[uid]:
        user_data[uid][token_hash] = {
            "card": "", 
            "favorability": 0, 
            "gold": 0,
            "rpg": {"lv": 1, "hp": 100, "atk": 10, "def": 0},
            "equip": {"weapon": "无", "armor": "无"}
        }
    
    # 二次检查确保关键字段存在（防止旧档缺失字段）
    target_data = user_data[uid][token_hash]
    if "rpg" not in target_data: target_data["rpg"] = {"lv": 1, "hp": 100, "atk": 10}
    if "gold" not in target_data: target_data["gold"] = 0
    if "equip" not in target_data: target_data["equip"] = {"weapon": "无", "armor": "无"}
    if "favorability" not in target_data: target_data["favorability"] = 0
        
    return target_data