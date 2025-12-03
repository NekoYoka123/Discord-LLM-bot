import random
import aiohttp
from .config import load_config, get_bot_config, load_user_data
from .game_data import get_favorability_stage

async def ask_ai(prompt, bot_token=None, user_name=None, user_id=None, history_context=None, current_fav=0, system_override=None, pure_reply=False, action_type=None):
    """
    action_type: 用于区分行为类型，例如 'gift_receive' (收礼), 'normal_chat' (聊天)
    """
    config = load_config()
    apis = config.get('api_configs', [])
    if not apis: return "❌ 未配置 API。"

    bot_conf = get_bot_config(config, bot_token)

    if system_override:
        final_system_prompt = system_override
    else:
        # 1. 基础人设
        prompts = bot_conf.get("system_prompts", ["You are a helpful assistant."])
        base_prompt = "\n\n".join(p for p in prompts if p.strip())
        knowledge = "\n".join(bot_conf.get("knowledge", []))
        
        final_system_prompt = f"{base_prompt}\n\n【已有知识库】:\n{knowledge}"
        
        if user_id:
            user_data = load_user_data()
            user_info = user_data.get(str(user_id), {})
            card = user_info.get("card", "无")
            equip = user_info.get("equip", {"weapon":"无", "armor":"无"})
            
            # 2. 获取详细的好感度阶段信息
            fav_stage = get_favorability_stage(current_fav)
            
            # 3. 构建动态人设指令
            final_system_prompt += (
                f"\n\n=== 交互对象档案 ===\n"
                f"用户名称: {user_name}\n"
                f"用户人设: {card}\n"
                f"用户装备: 武器<{equip['weapon']}> / 防具<{equip['armor']}>\n"
                f"--------------------\n"
                f"【当前好感度】: {current_fav} / 500\n"
                f"【关系状态】: {fav_stage['title']} ({fav_stage['desc']})\n"
                f"【核心扮演指令】 (必须严格执行): \n"
                f">>> {fav_stage['prompt']} <<<\n"
                f"--------------------"
            )

            # 4. 特殊行为的额外指令 (例如送礼)
            if action_type == 'gift_receive':
                final_system_prompt += (
                    "\n\n【当前事件：收到礼物】\n"
                    "用户刚刚送了你一份礼物。请结合你的性格和当前好感度做出反应。\n"
                    "- 如果好感度低：可能会觉得是贿赂、不屑一顾，或者勉强收下，甚至言语带刺。\n"
                    "- 如果好感度高：会非常开心、惊喜，甚至想要回礼，语气温柔。\n"
                    "- 请不要只是说“谢谢”，要表现出符合当前关系阶段的心理活动。"
                )

        if not pure_reply:
            final_system_prompt += (
                "\n\n【好感度系统】\n"
                "根据用户的对话内容，判断好感度变化：\n"
                "- 冒犯/无聊/重复/作死 -> [FAVORABILITY:-1] 到 -20\n"
                "- 夸奖/有趣/关心/配合 -> [FAVORABILITY:+1] 到 +20\n"
                "请将标签放在回复末尾（不要让用户看到），例如：......哼，这次就原谅你了。[FAVORABILITY:+5]"
            )

    full_message = ""
    if history_context: full_message += f"【历史对话】:\n{history_context}\n\n"
    full_message += f"{prompt}"

    # API Request
    api_setting = random.choice(apis)
    base_url = api_setting['url'].strip().rstrip('/')
    if not base_url.endswith('/chat/completions'): base_url += '/chat/completions'
    
    headers = {"Authorization": f"Bearer {random.choice(api_setting['keys'])}", "Content-Type": "application/json"}
    payload = {
        "model": api_setting.get('model', 'gpt-3.5-turbo'),
        "temperature": float(bot_conf.get('temperature', 0.8)),
        "messages": [{"role": "system", "content": final_system_prompt}, {"role": "user", "content": full_message}]
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(base_url, json=payload, headers=headers, timeout=60) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data['choices'][0]['message']['content']
                return f"API Error: {resp.status}"
    except Exception as e: return f"Connection Error: {e}"