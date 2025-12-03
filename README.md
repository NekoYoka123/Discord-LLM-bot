🤖 Discord AI RPG Bot & Command CenterDiscord AI RPG Bot 是一个集成了 LLM（大语言模型）深度交互、RPG 养成系统、好感度恋爱模拟以及Web 可视化管理后台的综合性 Discord 机器人平台。本项目不仅仅是一个聊天机器人，它拥有完整的“人格”和“记忆”，能够根据玩家的装备、好感度以及历史对话动态调整回复风格，并支持多人格/多实例同时运行。✨ 核心亮点 (Key Features)1. 🧠 深度 AI 交互系统 (Personality Engine)动态人格引擎：AI 的 System Prompt 会根据当前的好感度阶段实时变化。上下文感知：自动读取频道历史消息，支持“总结上下文”、“回答当前话题”等功能。轻量级 RAG（知识库）：通过 Web 后台随时注入世界观或特定知识，AI 会即时掌握。多模型支持：支持 OpenAI 格式的 API（GPT-3.5/4, Claude 等），支持配置多个 API Key 进行负载均衡。2. ❤️ 好感度与恋爱模拟 (Galgame System)情感反馈机制：AI 会分析用户的每一句对话，自动判断是增加还是扣除好感度。20 个情感阶段：从 “☠️ 不共戴天” (-500) 到 “♾️ 灵魂伴侣” (+500)，每个阶段都有独特的 System Prompt 指令，决定了 Bot 是对你冷嘲热讽还是深情款款。礼物系统：在商店购买鲜花、甜点甚至“情书”，AI 会根据收到的礼物做出符合当前关系的反应。3. ⚔️ RPG 战斗与经济系统D100 探索系统：跑团风格的 /explore 指令。AI 实时生成冒险故事，根据检定结果（大成功/大失败）判定金币获取与 HP 扣减。装备系统：可购买 武器（增加 ATK）和 防具（增加 HP/DEF）。AI 会识别你的装备并评价你的造型。PVP 决斗场：D20 战斗引擎：包含 D20 暴击（Nat20 造成 1.5 倍伤害）和大失败（Nat1 自伤）机制。两种模式：💰 赌钱模式：5 回合点数赛，赢家拿走输家一部分金币。☠️ 死斗模式：10 回合死斗，输家 直接删档重置（清空金币、好感度、装备）。AI 赛后解说：战斗结束后，AI 会化身热血解说员点评战斗过程。4. 🖥️ Web 控制中心 (Command Center)可视化管理：无需代码，网页端一键启动/停止 Bot 实例。大脑设定：在线编辑 System Prompt，调整 Temperature（创造力），管理 RAG 知识条目。玩家数据库：查看所有玩家的资产、装备、好感度，支持管理员“删档”或手动修改数据。API 连接池：图形化管理 LLM API 节点和 Key 池。管理员喊话：通过网页后台直接让 Bot 在指定 Discord 频道发言。📖 指令列表 (Commands)🎮 玩家指令指令说明/shop皇家交易所：打开 UI 界面，购买武器、防具或礼物。/explore探索：进行一次 D100 检定冒险，获取金币或受伤。/duel [user]决斗：向他人发起挑战，可选择赌金币或赌命。/my_stats我的数据：查看个人属性、装备、AI 对你的评价。/名片设置人设：设定你自己的背景故事，AI 会读取并记住它。/自定义探索提案：提交新的探索事件，全员投票通过后加入随机事件池。/summarize总结：让 AI 阅读最近 50 条消息并总结重点或回答提问。/提醒 [time] [msg]定时器：设置简单的定时提醒 (如 10m, 1h)。🛡️ 管理员指令指令说明/修改好感度强制增加/减少或设定某位玩家的好感度数值。/清除名片强制重置违规玩家的人设内容。/purge [num]批量清理频道消息。!sync(文本指令) 同步 Slash Commands 命令树。🛠️ 技术栈 (Tech Stack)核心语言: Python 3.9Bot 框架: discord.py (Asynchronous)Web 后端: Quart (基于 asyncio 的 Flask 替代品) + Hypercorn前端 UI: HTML5 + Bootstrap 5 (Dark Mode 风格)数据存储: JSON (轻量级文件存储，易于迁移)部署: Docker 容器化支持🚀 部署指南 (Deployment)方法一：Docker 部署 (推荐)构建镜像docker build -t discord-llm-bot .
运行容器# 映射 5000 端口以访问 Web 控制台
# 挂载 data 目录以持久化保存数据
docker run -d -p 5000:5000 --name my-bot -v $(pwd)/data:/app/data discord-llm-bot
访问控制台打开浏览器访问 http://localhost:5000。在 API 连接池 中配置你的 OpenAI/LLM API Key。在 运行概览 中添加你的 Discord Bot Token 并点击启动。方法二：本地 Python 运行安装依赖pip install -r requirements.txt
启动应用python main.py
注意：生产环境建议使用 hypercorn main:app --bind 0.0.0.0:5000 启动。📂 项目结构.
├── main.py              # 程序入口，同时启动 Web 和 Bot 进程
├── Dockerfile           # 容器构建文件
├── requirements.txt     # 依赖列表
├── templates/
│   └── index.html       # Web 控制台前端页面
└── modules/
    ├── ai.py            # LLM 调用逻辑、构建好感度 System Prompt
    ├── config.py        # 配置加载与保存 (JSON)
    ├── discord_bot.py   # Discord Bot 核心事件、战斗逻辑与指令
    ├── discord_ui.py    # Discord UI 组件 (按钮、模态框、下拉菜单)
    ├── game_data.py     # 游戏数据 (物品库、20级好感度文案)
    └── web.py           # Quart Web 服务器逻辑
