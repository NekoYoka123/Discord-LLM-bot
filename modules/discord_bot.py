# modules/discord_bot.py
import discord
import asyncio
import re
import random
from discord.ext import commands
from discord import app_commands
from .config import load_config, save_config, load_user_data, save_user_data
from .game_data import get_favorability_stage
from .ai import ask_ai
from .discord_ui import ShopCategoryView, CardModal, EventDefineModal, DuelInviteView

active_bots = {}

class MyBot(commands.Bot):
    def __init__(self, token_key, enabled_modules=None):
        super().__init__(command_prefix='!', intents=discord.Intents.all(), help_command=None)
        self.token_key = token_key 
        self.enabled_modules = enabled_modules or ["chat", "rpg", "admin", "utility"]

    async def setup_hook(self):
        await self.tree.sync()

    # --- 🎲 底层检定逻辑 (Dice System) ---
    def roll_check(self, bonus=0):
        """
        D100 检定系统
        返回: (roll_value, status_key, status_text)
        """
        roll = random.randint(1, 100)
        final_roll = max(1, min(100, roll + bonus)) 
        
        if final_roll <= 5:
            return final_roll, "FUMBLE", "💀 大失败"
        elif final_roll <= 50:
            return final_roll, "FAIL", "❌ 失败"
        elif final_roll <= 95:
            return final_roll, "SUCCESS", "✅ 成功"
        else:
            return final_roll, "CRITICAL", "🎉 大成功"

    # --- ⚔️ 战斗引擎 (升级版) ---
    async def start_combat_engine(self, interaction, p1, p2, mode):
        """
        引入 D20 暴击/大失败机制的战斗系统
        """
        user_data = load_user_data()
        d1 = user_data.get(str(p1.id), {"rpg":{"hp":100, "atk":10, "def":0}, "gold":0})
        d2 = user_data.get(str(p2.id), {"rpg":{"hp":100, "atk":10, "def":0}, "gold":0})

        hp1, max_hp1 = d1["rpg"].get("hp", 100), d1["rpg"].get("hp", 100)
        hp2, max_hp2 = d2["rpg"].get("hp", 100), d2["rpg"].get("hp", 100)
        atk1, def1 = d1["rpg"].get("atk", 10), d1["rpg"].get("def", 0)
        atk2, def2 = d2["rpg"].get("atk", 10), d2["rpg"].get("def", 0)

        rounds = 5 if mode == 'money' else 10
        winner = None

        embed = discord.Embed(title=f"⚔️ 决斗开始: {p1.display_name} VS {p2.display_name}", color=0xff0000)
        embed.add_field(name=f"{p1.display_name}", value=f"HP {hp1}/{max_hp1}", inline=True)
        embed.add_field(name=f"{p2.display_name}", value=f"HP {hp2}/{max_hp2}", inline=True)
        msg = await interaction.channel.send(embed=embed)

        log_history = [] 

        for r in range(1, rounds + 1):
            await asyncio.sleep(2)

            round_log = f"**Round {r}**\n"
            
            # --- P1 攻击 P2 ---
            d20_1 = random.randint(1, 20)
            dmg1 = 0
            
            if d20_1 == 1: # 大失败
                self_dmg = random.randint(1, 5)
                hp1 -= self_dmg
                round_log += f"💀 {p1.display_name} 脚下一滑(大失败)，受到反噬 **{self_dmg}**！\n"
            elif d20_1 == 20: # 暴击
                raw_dmg = int((atk1 + random.randint(1, 5)) * 1.5)
                dmg1 = max(1, raw_dmg - def2)
                hp2 -= dmg1
                round_log += f"🔥 {p1.display_name} 暴击！(Nat20) 造成 **{dmg1}** 伤害！\n"
            else: # 普通
                hit_roll = atk1 + d20_1
                def_roll = def2 + random.randint(1, 10)
                dmg1 = max(1, hit_roll - def_roll)
                hp2 -= dmg1
                round_log += f"👊 {p1.display_name} 造成 **{dmg1}** 伤害 (🎲{d20_1})\n"

            # --- P2 攻击 P1 ---
            if hp2 > 0:
                d20_2 = random.randint(1, 20)
                dmg2 = 0
                
                if d20_2 == 1:
                    self_dmg = random.randint(1, 5)
                    hp2 -= self_dmg
                    round_log += f"💀 {p2.display_name} 攻击失误(大失败)，自损 **{self_dmg}**！\n"
                elif d20_2 == 20:
                    raw_dmg = int((atk2 + random.randint(1, 5)) * 1.5)
                    dmg2 = max(1, raw_dmg - def1)
                    hp1 -= dmg2
                    round_log += f"🔥 {p2.display_name} 暴击！(Nat20) 造成 **{dmg2}** 伤害！"
                else:
                    hit_roll = atk2 + d20_2
                    def_roll = def1 + random.randint(1, 10)
                    dmg2 = max(1, hit_roll - def_roll)
                    hp1 -= dmg2
                    round_log += f"👊 {p2.display_name} 造成 **{dmg2}** 伤害 (🎲{d20_2})"

            log_history.append(round_log)
            
            embed.description = round_log
            bar1 = "🟩" * int(max(0, hp1)/max_hp1*10) + "⬛" * (10 - int(max(0, hp1)/max_hp1*10))
            bar2 = "🟩" * int(max(0, hp2)/max_hp2*10) + "⬛" * (10 - int(max(0, hp2)/max_hp2*10))
            
            embed.set_field_at(0, name=f"{p1.display_name}", value=f"HP {max(0,hp1)} | {bar1}", inline=True)
            embed.set_field_at(1, name=f"{p2.display_name}", value=f"HP {max(0,hp2)} | {bar2}", inline=True)
            await msg.edit(embed=embed)

            if hp1 <= 0 or hp2 <= 0: break

        # 结算
        result_text = ""
        loser = None
        
        if hp1 <= 0 and hp2 <= 0:
            result_text = "💀 **同归于尽！双方都倒下了！**"
        elif hp1 > hp2:
            winner = p1
            loser = p2
            result_text = f"🏆 **{p1.display_name} 胜利！**"
        else:
            winner = p2
            loser = p1
            result_text = f"🏆 **{p2.display_name} 胜利！**"

        user_data = load_user_data()
        s_p1, s_p2 = str(p1.id), str(p2.id)
        if s_p1 in user_data: user_data[s_p1]["rpg"]["hp"] = max(0, hp1)
        if s_p2 in user_data: user_data[s_p2]["rpg"]["hp"] = max(0, hp2)

        if mode == 'money' and winner and loser:
            l_id, w_id = str(loser.id), str(winner.id)
            loser_gold = user_data.get(l_id, {}).get("gold", 0)
            steal = int(loser_gold * random.uniform(0.1, 0.5))
            user_data[l_id]["gold"] -= steal
            user_data[w_id]["gold"] += steal
            result_text += f"\n💰 赢家拿走了 **{steal} G**！"
        
        elif mode == 'life' and loser:
            l_id = str(loser.id)
            user_data[l_id] = {"gold": 0, "favorability": 0, "rpg": {"lv": 1, "hp": 100, "atk": 10, "def": 0}, "equip": {"weapon": "无", "armor": "无"}}
            result_text += f"\n💀 **{loser.display_name} 已死亡，存档被清空重置。**"
        
        save_user_data(user_data)
        
        embed.description = result_text
        embed.color = 0xffd700
        await msg.edit(embed=embed)

        if "chat" in self.enabled_modules:
            combat_log_str = "\n".join(log_history)
            prompt = (
                f"请以热血解说员的身份总结这场战斗。\n"
                f"对阵：{p1.display_name} vs {p2.display_name}\n"
                f"战斗过程记录：\n{combat_log_str}\n"
                f"最终结果：{result_text}\n"
                f"请特别点评其中的【暴击】或【大失败】镜头。"
            )
            commentary = await ask_ai(prompt, self.token_key, pure_reply=True)
            await interaction.channel.send(f"🎙️ **赛后点评:**\n{commentary}")

    async def on_message(self, message):
        if message.author.bot: return

        if "chat" not in self.enabled_modules:
            if message.content == "!sync" and message.author.guild_permissions.administrator:
                pass
            else:
                return

        if message.content == "!sync" and message.author.guild_permissions.administrator:
            await self.tree.sync()
            await message.reply(f"✅ 指令树已同步。当前启用模块: {self.enabled_modules}")
            return

        is_mentioned = self.user in message.mentions
        is_reply = (message.reference and message.reference.resolved and message.reference.resolved.author == self.user)

        if is_mentioned or is_reply:
            content = message.content.replace(f'<@{self.user.id}>', '').strip() or "..."
            async with message.channel.typing():
                history = [f"{m.author.display_name}: {m.content}" async for m in message.channel.history(limit=40, before=message) if not m.author.bot]
                history_text = "\n".join(reversed(history))
                
                user_data = load_user_data()
                uid = str(message.author.id)
                if uid not in user_data: 
                    user_data[uid] = {"card": "", "favorability": 0, "rpg": {"lv": 1, "hp": 100}, "gold": 0, "equip":{"weapon":"无", "armor":"无"}}
                
                reply = await ask_ai(
                    content, 
                    bot_token=self.token_key,
                    user_name=message.author.display_name, 
                    user_id=message.author.id,
                    history_context=history_text,
                    current_fav=user_data[uid].get("favorability", 0)
                )

                fav_match = re.search(r'\[FAVORABILITY:([+-]?\d+)\]', reply)
                final_reply = reply
                if fav_match:
                    change = int(fav_match.group(1))
                    new_fav = max(-500, min(500, user_data[uid]["favorability"] + change))
                    user_data[uid]["favorability"] = new_fav
                    save_user_data(user_data)
                    final_reply = reply.replace(fav_match.group(0), "").strip()

                if len(final_reply) > 2000:
                    for i in range(0, len(final_reply), 1900): await message.reply(final_reply[i:i+1900])
                elif final_reply:
                    await message.reply(final_reply)


# --- 模块化指令注册函数 ---

def register_rpg_commands(bot):
    @bot.tree.command(name="决斗", description="发起决斗 (赌钱/赌命)")
    async def duel(interaction: discord.Interaction, target: discord.User):
        if target.bot or target.id == interaction.user.id:
            return await interaction.response.send_message("❌ 无效的目标。", ephemeral=True)
        
        embed = discord.Embed(title="⚔️ 决斗挑战", description=f"{interaction.user.mention} 挑战 {target.mention}！\n接受吗？", color=0xff0000)
        view = DuelInviteView(bot, interaction.user, target)
        await interaction.response.send_message(content=target.mention, embed=embed, view=view)

    @bot.tree.command(name="商店", description="装备/礼物/情书/药水")
    async def shop(interaction: discord.Interaction):
        embed = discord.Embed(title="🏰 皇家交易所", description="请选择商品分类：", color=0xffd700)
        user_data = load_user_data()
        gold = user_data.get(str(interaction.user.id), {}).get("gold", 0)
        embed.set_footer(text=f"金币: {gold} G")
        await interaction.response.send_message(embed=embed, view=ShopCategoryView(bot.token_key), ephemeral=True)

    @bot.tree.command(name="自定义探索", description="创建探索事件")
    async def define_event(interaction: discord.Interaction):
        await interaction.response.send_modal(EventDefineModal(bot))

    @bot.tree.command(name="探索", description="[检定] 进行冒险，可能有大成功或大失败")
    async def explore(interaction: discord.Interaction):
        await interaction.response.defer()
        user_data = load_user_data()
        uid = str(interaction.user.id)
        if uid not in user_data: user_data[uid] = {"gold":0, "rpg":{"lv":1,"hp":100}, "favorability":0, "equip":{"weapon":"无","armor":"无"}}
        
        if user_data[uid].get("rpg", {}).get("hp", 0) <= 0:
            return await interaction.followup.send("💀 你已重伤（HP<=0），无法行动。请联系管理员复活或等待剧情。")

        config = load_config()
        custom_events = config.get("default_settings", {}).get("custom_events", [])
        
        event_text = "随机探索遭遇"
        if custom_events and random.random() < 0.5:
            evt = random.choice(custom_events)
            event_text = f"遭遇自定义事件：{evt['content']} (成功则: {evt['success']}, 失败则: {evt['fail']})"
        else:
            event_text = "在未知的地下城中探索，前方似乎有动静..."

        roll_val, status_key, status_text = bot.roll_check()
        
        gold_change = 0
        hp_change = 0
        defense = user_data[uid].get("rpg", {}).get("def", 0)

        if status_key == "CRITICAL":
            gold_change = random.randint(100, 200)
            hp_change = 20
            result_desc = "你简直是被幸运女神眷顾！不仅毫发无伤，还发现了隐藏的密室！"
        elif status_key == "SUCCESS":
            gold_change = random.randint(30, 80)
            hp_change = 0
            result_desc = "凭借过人的身手，你成功解决了麻烦，获得了一些战利品。"
        elif status_key == "FAIL":
            gold_change = 0
            raw_dmg = random.randint(10, 20)
            hp_change = -max(1, raw_dmg - defense)
            result_desc = "情况不妙，你受了些伤，只好空手而归。"
        elif status_key == "FUMBLE":
            gold_change = -random.randint(10, 30)
            raw_dmg = random.randint(30, 50)
            hp_change = -max(5, raw_dmg - defense)
            result_desc = "灾难！你不仅踩中了陷阱，逃跑时还弄丢了钱袋！"

        user_data[uid]["gold"] = max(0, user_data[uid]["gold"] + gold_change)
        current_hp = user_data[uid].get("rpg", {}).get("hp", 100)
        user_data[uid]["rpg"]["hp"] = current_hp + hp_change
        save_user_data(user_data)
        
        if "chat" in bot.enabled_modules:
            # --- 视角修正：强制 DM 第二人称视角 ---
            prompt = (
                f"【指令】：你现在是TRPG跑团游戏的DM（地下城主）。\n"
                f"【玩家】：{interaction.user.display_name}\n"
                f"【遭遇事件】：{event_text}\n"
                f"【检定结果】：🎲D100 = {roll_val} -> 【{status_text}】\n"
                f"【后果】：{result_desc}\n"
                f"【数值变动】：金币 {gold_change:+}, HP {hp_change:+} (当前HP: {user_data[uid]['rpg']['hp']})\n\n"
                f"请根据检定结果，用生动、有画面感的文字描述玩家经历了什么。\n"
                f"⚠️ 严格要求：\n"
                f"1. 必须使用第二人称“你”（例如：你挥舞着剑...，你跌跌撞撞地...）。\n"
                f"2. 绝对不要出现“作为AI”、“好的”、“根据结果”等出戏的语言，直接开始描写。\n"
                f"3. 如果是大成功，描写得帅气/幸运；如果是大失败，描写得狼狈/倒霉。"
            )
            story = await ask_ai(prompt, bot.token_key, interaction.user.display_name, pure_reply=True)
        else:
            story = f"{event_text}\n结果: {result_desc}"
        
        color_map = {"CRITICAL": 0xffd700, "SUCCESS": 0x00ff00, "FAIL": 0xff9900, "FUMBLE": 0xff0000}
        
        embed = discord.Embed(title=f"🎲 探索检定: {status_text}", description=story, color=color_map.get(status_key, 0x95a5a6))
        embed.add_field(name="检定详情", value=f"D100 = **{roll_val}**", inline=True)
        embed.add_field(name="结算", value=f"💰 {gold_change:+}\n🩸 {hp_change:+}", inline=True)
        
        await interaction.followup.send(embed=embed)

    @bot.tree.command(name="我的数据", description="查看档案")
    async def my_stats(interaction: discord.Interaction):
        await interaction.response.defer()
        user_data = load_user_data()
        uid = str(interaction.user.id)
        u = user_data.get(uid, {"gold":0, "favorability":0, "rpg":{"lv":1,"hp":100}, "equip":{"weapon":"无","armor":"无"}})
        
        comment = "..."
        if "chat" in bot.enabled_modules:
            fav_stage = get_favorability_stage(u.get('favorability', 0))
            prompt = f"请评价面前的玩家。关系: {fav_stage['title']}。装备: {u['equip']}。请用第二人称。"
            comment = await ask_ai(prompt, bot.token_key, interaction.user.display_name, user_id=interaction.user.id, current_fav=u.get('favorability', 0), pure_reply=True)
        
        embed = discord.Embed(title=f"📜 {interaction.user.display_name}", color=0x9b59b6)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="💬 评价", value=comment, inline=False)
        
        rpg = u.get("rpg", {})
        embed.add_field(name="📊 属性", value=f"HP: {rpg.get('hp')} | ATK: {rpg.get('atk',10)} | DEF: {rpg.get('def',0)}", inline=True)
        embed.add_field(name="💰 金币", value=f"{u.get('gold')} G", inline=True)
        embed.add_field(name="⚔️ 装备", value=f"🗡️ {u['equip'].get('weapon')}\n🛡️ {u['equip'].get('armor')}", inline=False)
        
        await interaction.followup.send(embed=embed)

def register_admin_commands(bot):
    @bot.tree.command(name="修改好感度", description="[管理] 修改指定用户的好感度")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(target="目标用户", value="数值", mode="模式: add(增加)/set(设定)")
    @app_commands.choices(mode=[
        app_commands.Choice(name="➕ 增加/减少 (Add)", value="add"),
        app_commands.Choice(name="🎯 设定为 (Set)", value="set")
    ])
    async def modify_fav(interaction: discord.Interaction, target: discord.User, value: int, mode: str = "add"):
        await interaction.response.defer(ephemeral=True)
        user_data = load_user_data()
        uid = str(target.id)
        if uid not in user_data: 
             user_data[uid] = {"gold":0, "rpg":{"lv":1,"hp":100}, "favorability":0, "equip":{"weapon":"无","armor":"无"}}

        old_fav = user_data[uid].get("favorability", 0)
        
        if mode == "add":
            new_fav = old_fav + value
        else:
            new_fav = value
            
        new_fav = max(-500, min(500, new_fav))
        user_data[uid]["favorability"] = new_fav
        save_user_data(user_data)
        
        await interaction.followup.send(f"✅ 已修改 {target.mention} 的好感度。\n📊 变动: {old_fav} -> **{new_fav}**", ephemeral=True)

    @bot.tree.command(name="清除名片", description="[管理] 强制清除/重置用户的名片")
    @app_commands.checks.has_permissions(administrator=True)
    async def clear_card(interaction: discord.Interaction, target: discord.User):
        await interaction.response.defer(ephemeral=True)
        user_data = load_user_data()
        uid = str(target.id)
        
        if uid in user_data:
            old_card = user_data[uid].get("card", "无")
            user_data[uid]["card"] = "" 
            save_user_data(user_data)
            await interaction.followup.send(f"✅ 已清除 {target.mention} 的名片。\n🗑️ 原内容: {old_card[:50]}...", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ 找不到 {target.mention} 的数据。", ephemeral=True)
    
    @bot.tree.command(name="清理", description="清理消息")
    @app_commands.checks.has_permissions(administrator=True)
    async def purge(interaction: discord.Interaction, count: int):
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=count)
        await interaction.followup.send(f"🧹 已清理 {len(deleted)} 条", ephemeral=True)

def register_utility_commands(bot):
    @bot.tree.command(name="名片", description="设置人设")
    async def set_card_cmd(interaction: discord.Interaction):
        await interaction.response.send_modal(CardModal(bot.token_key))

    @bot.tree.command(name="提醒", description="设置提醒")
    async def remind(interaction: discord.Interaction, time_str: str, matter: str):
        unit = time_str[-1].lower()
        try:
            val = int(time_str[:-1])
            seconds = val * (60 if unit == 'm' else 3600 if unit == 'h' else 1)
        except: return await interaction.response.send_message("❌ 格式: 10m, 1h", ephemeral=True)
        await interaction.response.send_message(f"⏰ 已设定提醒: {matter}")
        await asyncio.sleep(seconds)
        try: await interaction.user.send(f"🔔 提醒: {matter}")
        except: pass

    @bot.tree.command(name="总结", description="智能总结/提问 (自动读取上下文)")
    async def summarize(interaction: discord.Interaction, instruction: str = None):
        if "chat" not in bot.enabled_modules:
             return await interaction.response.send_message("❌ 聊天模块已禁用，无法使用智能总结。", ephemeral=True)

        await interaction.response.defer()
        hist = [f"{m.author.display_name}: {m.content}" async for m in interaction.channel.history(limit=50)]
        text = "\n".join(reversed(hist))
        
        user_query = instruction if instruction else "请总结刚才发生了什么，大家的讨论重点和情绪如何？"
        prompt = (
            f"以下是 Discord 频道的最近聊天记录（上下文）：\n\n{text}\n\n"
            f"用户指令/问题：{user_query}\n"
            f"请根据聊天记录执行用户的指令。"
        )
        res = await ask_ai(prompt, bot.token_key, pure_reply=True)
        
        embed = discord.Embed(title="📝 智能助手", description=res, color=0x3498db)
        embed.set_footer(text=f"基于最近 50 条消息 | 指令: {user_query}")
        await interaction.followup.send(embed=embed)

async def start_bot(token):
    if token in active_bots: return
    try:
        config = load_config()
        bot_conf = config["bot_settings"].get(token, config["default_settings"])
        modules = bot_conf.get("enabled_modules", ["chat", "rpg", "admin", "utility"])
        
        print(f"🤖 Starting Bot [{token[:6]}...] with modules: {modules}")
        
        bot = MyBot(token, enabled_modules=modules)
        
        if "rpg" in modules: register_rpg_commands(bot)
        if "admin" in modules: register_admin_commands(bot)
        if "utility" in modules: register_utility_commands(bot)
        
        task = asyncio.create_task(bot.start(token))
        active_bots[token] = {"bot": bot, "task": task}
        await task
    except Exception as e:
        print(f"Error starting bot {token}: {e}")
        if token in active_bots: del active_bots[token]