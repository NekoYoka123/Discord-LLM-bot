import os
import json
import random
import asyncio
import aiohttp
from quart import Quart, render_template, request, jsonify, redirect, url_for
import discord
from discord import app_commands
from discord.ext import commands

# --- 配置与初始化 ---
app = Quart(__name__)
app.secret_key = 'zeabur_secret_key_change_me'

# 适配 Zeabur 的路径，如果本地运行请改回 ./data
DATA_DIR = "/app/data" 
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
USER_DATA_FILE = os.path.join(DATA_DIR, "user_data.json")

# 全局变量
active_bots = {}

default_config = {
    "api_configs": [
        {"url": "https://generativelanguage.googleapis.com/v1beta/openai/", "keys": [], "model": "gemini-pro"}
    ],
    "bot_tokens": [],
    "system_prompt": "你是一个非常有用的 Discord 助手。",
    "temperature": 0.7,
    "global_knowledge": []
}

def load_config():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        return default_config
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            for key, val in default_config.items():
                if key not in config:
                    config[key] = val
            return config
    except:
        return default_config

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

def load_user_data():
    if not os.path.exists(USER_DATA_FILE): return {}
    try:
        with open(USER_DATA_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: return {}

def save_user_data(data):
    with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- AI 处理逻辑 (新增 history_context 参数) ---
async def ask_ai(prompt, user_name=None, user_id=None, history_context=None):
    config = load_config()
    apis = config.get('api_configs', [])
    if not apis:
        return "❌ 未配置 API。"

    # 1. 构建系统提示词 (基础人设 + 全局知识)
    system_prompt = config.get('system_prompt', 'You are a helpful assistant.')
    knowledge_list = config.get('global_knowledge', [])
    if knowledge_list:
        knowledge_text = "\n".join(knowledge_list)
        system_prompt += f"\n\n【已有知识库】:\n{knowledge_text}"

    # 2. 构建用户上下文 (名片 + 历史聊天记录)
    context_block = ""
    
    # 插入名片
    if user_id:
        user_data = load_user_data()
        user_card = user_data.get(str(user_id))
        if user_card:
            context_block += f"【当前提问者的名片/设定】:\n名字: {user_name}\n内容: {user_card}\n\n"
            
    # 插入聊天记录 (V3 新增)
    if history_context:
        context_block += f"【当前频道的最近聊天记录(上下文)】:\n{history_context}\n\n"
    
    # 组合最终 Prompt
    full_user_message = f"{context_block}【用户最新提问】:\n{prompt}"

    # API 调用逻辑
    api_setting = random.choice(apis)
    base_url = api_setting['url'].strip()
    if not base_url.endswith('/chat/completions'):
         base_url = base_url.rstrip('/') + '/chat/completions'

    keys = api_setting['keys']
    current_key = random.choice(keys) if keys else ""
    model = api_setting.get('model', 'gpt-3.5-turbo')
    temperature = float(config.get('temperature', 0.7))

    headers = {
        "Authorization": f"Bearer {current_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": full_user_message}
        ]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(base_url, json=payload, headers=headers, timeout=60) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data['choices'][0]['message']['content']
                else:
                    return f"API Error: {resp.status} - {await resp.text()}"
    except Exception as e:
        return f"Connection Error: {str(e)}"

# --- Discord 机器人逻辑 ---
class MyBot(commands.Bot):
    def __init__(self, token_key):
        intents = discord.Intents.all()
        super().__init__(command_prefix='!', intents=intents, help_command=None)
        self.token_key = token_key

    async def setup_hook(self):
        await self.tree.sync()

    async def on_ready(self):
        print(f'Bot {self.user} is online!')

    async def on_message(self, message):
        if message.author.bot:
            return

        is_mentioned = self.user in message.mentions
        is_reply = (message.reference and message.reference.resolved and 
                    message.reference.resolved.author == self.user)

        if is_mentioned or is_reply:
            content = message.content.replace(f'<@{self.user.id}>', '').strip()
            
            # 如果内容为空（只@了），可能是想聊天，给个默认招呼
            if not content:
                content = "（用户只@了你，没有说话，请根据上下文回应）"

            async with message.channel.typing():
                # --- V3 新增: 获取历史消息 ---
                history_list = []
                try:
                    # 获取最近 30 条消息（不包含当前这条触发的消息）
                    async for msg in message.channel.history(limit=30, before=message):
                        # 过滤掉系统消息或空白消息
                        if msg.content.strip():
                            author_name = msg.author.display_name
                            # 清理掉消息里的 @机器人 标记，让阅读更顺畅
                            clean_msg = msg.content.replace(f'<@{self.user.id}>', '@Me')
                            history_list.append(f"{author_name}: {clean_msg}")
                except Exception as e:
                    print(f"读取历史失败: {e}")
                
                # history取出来是倒序的（最新的在最前），我们需要反转回正常时间顺序
                history_text = "\n".join(reversed(history_list))
                # ---------------------------

                reply = await ask_ai(
                    content, 
                    user_name=message.author.display_name, 
                    user_id=message.author.id,
                    history_context=history_text  # 传入历史
                )
                await message.reply(reply)

# --- 注册 Slash Commands (保持不变) ---
def register_commands(bot):
    
    @bot.tree.command(name="禁言", description="管理员专用：禁言某人")
    @app_commands.checks.has_permissions(administrator=True)
    async def mute(interaction: discord.Interaction, member: discord.Member, minutes: int):
        import datetime
        duration = datetime.timedelta(minutes=minutes)
        try:
            await member.timeout(duration, reason="Slash Command Mute")
            await interaction.response.send_message(f"🚫 {member.mention} 已被禁言 {minutes} 分钟。")
        except Exception as e:
            await interaction.response.send_message(f"❌ 失败: {str(e)}", ephemeral=True)

    @bot.tree.command(name="投骰子", description="随机投掷 1-6 点")
    async def roll(interaction: discord.Interaction):
        result = random.randint(1, 6)
        await interaction.response.send_message(f"🎲 {interaction.user.mention} 投出了: **{result}** 点")

    @bot.tree.command(name="检定", description="进行一次 TRPG 事件检定")
    async def check(interaction: discord.Interaction, event: str):
        await interaction.response.defer()
        score = random.randint(1, 100)
        prompt = (f"TRPG判定: 玩家进行了'{event}'。\n" f"骰子结果: {score}/100。\n" f"请判断结果并描述。")
        reply = await ask_ai(prompt, user_name=interaction.user.display_name, user_id=interaction.user.id)
        embed = discord.Embed(title="🎲 事件检定", color=0x00ff00)
        embed.add_field(name="事件", value=event, inline=False)
        embed.add_field(name="点数", value=f"**{score}**", inline=False)
        embed.add_field(name="结果", value=reply, inline=False)
        await interaction.followup.send(embed=embed)

    @bot.tree.command(name="名片", description="设置机器人对你的记忆/人设")
    async def set_card(interaction: discord.Interaction, content: str):
        user_data = load_user_data()
        user_data[str(interaction.user.id)] = content
        save_user_data(user_data)
        await interaction.response.send_message(f"✅ 已记录你的名片：\n> {content}", ephemeral=True)

    @bot.tree.command(name="清除名片", description="清除机器人对你的记忆")
    async def clear_card(interaction: discord.Interaction):
        user_data = load_user_data()
        uid = str(interaction.user.id)
        if uid in user_data:
            del user_data[uid]
            save_user_data(user_data)
            await interaction.response.send_message("🗑️ 你的名片已清除。", ephemeral=True)
        else:
            await interaction.response.send_message("❓ 你还没有设置过名片。", ephemeral=True)

    @bot.tree.command(name="知识输入", description="给机器人大脑里塞入一条全局知识")
    async def add_knowledge(interaction: discord.Interaction, content: str):
        config = load_config()
        if 'global_knowledge' not in config: config['global_knowledge'] = []
        config['global_knowledge'].append(content)
        save_config(config)
        await interaction.response.send_message(f"📚 已录入知识库：\n> {content}", ephemeral=False)

# --- 机器人管理线程 (保持不变) ---
async def start_bot(token):
    if token in active_bots: return
    bot = MyBot(token)
    register_commands(bot)
    task = asyncio.create_task(bot.start(token))
    active_bots[token] = {"bot": bot, "task": task}
    try: await task
    except Exception as e:
        print(f"Bot error: {e}")
        if token in active_bots: del active_bots[token]

async def stop_bot(token):
    if token in active_bots:
        await active_bots[token]["bot"].close()
        del active_bots[token]

# --- Web 路由 (保持不变) ---
@app.route('/')
async def index():
    try:
        config = load_config()
        bot_status = []
        for t in config['bot_tokens']:
            status = "🟢 运行中" if t in active_bots else "🔴 已停止"
            current_bot = active_bots[t]['bot'] if t in active_bots else None
            bot_user = str(current_bot.user) if (current_bot and current_bot.user) else "加载中..."
            bot_status.append({"token_mask": t[:10] + "...", "full_token": t, "status": status, "user": bot_user})
        return await render_template('index.html', bots=bot_status, apis=config['api_configs'], config=config)
    except Exception:
        import traceback
        return f"<pre>{traceback.format_exc()}</pre>"

@app.route('/save_ai_settings', methods=['POST'])
async def save_ai_settings():
    form = await request.form
    config = load_config()
    config['system_prompt'] = form.get('system_prompt', '')
    try: config['temperature'] = float(form.get('temperature', 0.7))
    except: config['temperature'] = 0.7
    save_config(config)
    return redirect(url_for('index'))

@app.route('/update_api', methods=['POST'])
async def update_api():
    form = await request.form
    config = load_config()
    keys = [k.strip() for k in form.get('keys').split('\n') if k.strip()]
    config['api_configs'].append({"url": form.get('url'),"keys": keys,"model": form.get('model')})
    save_config(config)
    return redirect(url_for('index'))

@app.route('/delete_api', methods=['POST'])
async def delete_api():
    config = load_config()
    if config['api_configs']: config['api_configs'].pop()
    save_config(config)
    return redirect(url_for('index'))

@app.route('/manage_bot', methods=['POST'])
async def manage_bot():
    form = await request.form
    action = form.get('action')
    token = form.get('token')
    config = load_config()
    if action == 'add':
        new_token = form.get('new_token').strip()
        if new_token and new_token not in config['bot_tokens']:
            config['bot_tokens'].append(new_token)
            save_config(config)
            asyncio.create_task(start_bot(new_token))
    elif action == 'start': asyncio.create_task(start_bot(token))
    elif action == 'stop': await stop_bot(token)
    elif action == 'delete':
        await stop_bot(token)
        if token in config['bot_tokens']:
            config['bot_tokens'].remove(token)
            save_config(config)
    return redirect(url_for('index'))

@app.route('/test_api', methods=['POST'])
async def test_api():
    res = await ask_ai("Reply OK")
    return jsonify({"response": res})

@app.route('/admin_say', methods=['POST'])
async def admin_say():
    form = await request.form
    token_mask = form.get('bot_token_mask')
    channel_id = int(form.get('channel_id'))
    message = form.get('message')
    for token, data in active_bots.items():
        if token.startswith(token_mask.replace("...", "")):
            try:
                await data['bot'].get_channel(channel_id).send(message)
                return "Sent"
            except: return "Error"
    return "Bot not found"

@app.before_serving
async def startup():
    config = load_config()
    for token in config['bot_tokens']:
        asyncio.create_task(start_bot(token))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)