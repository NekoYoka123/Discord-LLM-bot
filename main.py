import asyncio
from modules.web import app
from modules.config import load_config
from modules.discord_bot import start_bot

# 启动时钩子
@app.before_serving
async def startup():
    config = load_config()
    for token in config['bot_tokens']:
        # 后台启动所有已配置的 Bot
        asyncio.create_task(start_bot(token))

if __name__ == '__main__':
    # 开发环境运行
    app.run(host='0.0.0.0', port=5000)
    
    # 生产环境 (Docker) 请使用:
    # hypercorn main:app --bind 0.0.0.0:5000