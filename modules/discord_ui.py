# modules/discord_ui.py
import discord
from discord import ui
from .config import load_config, save_config, load_user_data, save_user_data
from .game_data import ITEMS_DB, get_favorability_stage
from .ai import ask_ai

# --- 决斗系统 UI ---

class DuelBetView(ui.View):
    def __init__(self, bot, challenger, target):
        super().__init__(timeout=60)
        self.bot = bot
        self.challenger = challenger
        self.target = target
        self.mode = None
        self.message = None

    @ui.button(label="💰 赌钱 (5轮点数赛)", style=discord.ButtonStyle.primary)
    async def bet_money(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.challenger.id: return await interaction.response.send_message("只有发起者能选择模式", ephemeral=True)
        self.mode = "money"
        await self.start_duel(interaction)

    @ui.button(label="☠️ 赌命 (死斗模式)", style=discord.ButtonStyle.danger)
    async def bet_life(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.challenger.id: return await interaction.response.send_message("只有发起者能选择模式", ephemeral=True)
        self.mode = "life"
        await self.start_duel(interaction)

    async def start_duel(self, interaction):
        for child in self.children: child.disabled = True
        await interaction.response.edit_message(content=f"⚔️ **决斗模式已确认：{self.children[0].label if self.mode=='money' else self.children[1].label}**\n战斗即将开始...", view=self)
        if hasattr(self.bot, 'start_combat_engine'):
            await self.bot.start_combat_engine(interaction, self.challenger, self.target, self.mode)

class DuelInviteView(ui.View):
    def __init__(self, bot, challenger, target):
        super().__init__(timeout=60)
        self.bot = bot
        self.challenger = challenger
        self.target = target
        self.accepted = False

    @ui.button(label="⚔️ 接受挑战", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.target.id:
            return await interaction.response.send_message("这不是发给你的挑战书！", ephemeral=True)
        
        self.accepted = True
        for child in self.children: child.disabled = True
        await interaction.response.edit_message(content=f"🔥 **{self.target.display_name}** 接受了挑战！\n请发起者选择决斗规则：", view=DuelBetView(self.bot, self.challenger, self.target))

    @ui.button(label="🏃 认怂/拒绝", style=discord.ButtonStyle.secondary)
    async def reject(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.target.id: return
        self.stop()
        await interaction.response.edit_message(content=f"🏳️ **{self.target.display_name}** 拒绝了决斗。", view=None)

# --- 商店特殊物品 Modal ---

class LoveLetterModal(ui.Modal, title="💌 书写情书"):
    content = ui.TextInput(label="情书内容", style=discord.TextStyle.paragraph, placeholder="亲爱的...", required=True, max_length=500)

    def __init__(self, bot_token, item_name, cost):
        super().__init__()
        self.bot_token = bot_token
        self.item_name = item_name
        self.cost = cost

    async def on_submit(self, interaction: discord.Interaction):
        user_data = load_user_data()
        uid = str(interaction.user.id)
        if uid not in user_data: user_data[uid] = {"gold":0, "favorability":0, "equip":{}}
        
        if user_data[uid]["gold"] < self.cost:
            return await interaction.response.send_message("💸 你的钱不够了...", ephemeral=True)

        user_data[uid]["gold"] -= self.cost
        item_data = ITEMS_DB['gifts'][self.item_name]
        fav_add = item_data['fav']
        user_data[uid]["favorability"] = user_data[uid].get("favorability", 0) + fav_add
        save_user_data(user_data)

        msg = f"💌 你羞涩地递出了 **{self.item_name}**！ (好感度 +{fav_add})\n> *{self.content.value}*"
        
        ai_prompt = (
            f"用户送了你一封情书，内容是：“{self.content.value}”。\n"
            f"这是非常贵重的礼物（价值{self.cost}G）。\n"
            f"请仔细阅读情书内容，并根据当前好感度做出深刻的情感反馈。"
        )

        reply = await ask_ai(
            ai_prompt, 
            self.bot_token, 
            interaction.user.display_name, 
            user_id=interaction.user.id,
            current_fav=user_data[uid].get("favorability", 0),
            pure_reply=True,
            action_type="gift_receive"
        )
        
        await interaction.response.send_message(f"{msg}\n\n🤖 **Bot:** {reply}", ephemeral=True)

# --- 商店选择器 ---

class ShopItemSelect(ui.Select):
    def __init__(self, category, bot_token):
        self.category = category
        self.bot_token = bot_token
        items = ITEMS_DB[category]
        options = []
        for name, data in items.items():
            cost = data['cost']
            desc = data['desc'][:50]
            
            # 根据类别生成不同的描述前缀
            if category == 'gifts': desc = f"[好感+{data['fav']}] {desc}"
            elif category == 'armors' and 'def' in data: desc = f"[DEF+{data['def']}] {desc}"
            elif category == 'potions': desc = f"[HP+{data['hp_rec']}] {desc}"
            
            label = f"{name} ({cost}G)"
            options.append(discord.SelectOption(label=label, description=desc, value=name))
        super().__init__(placeholder=f"选择要购买的{category}...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        item_name = self.values[0]
        item_data = ITEMS_DB[self.category][item_name]
        cost = item_data['cost']
        
        # 特殊处理情书
        if item_name == "情书":
             user_data = load_user_data()
             uid = str(interaction.user.id)
             gold = user_data.get(uid, {}).get("gold", 0)
             if gold < cost: return await interaction.response.send_message(f"💸 余额不足！需要 {cost}G。", ephemeral=True)
             return await interaction.response.send_modal(LoveLetterModal(self.bot_token, item_name, cost))

        user_data = load_user_data()
        uid = str(interaction.user.id)
        if uid not in user_data: user_data[uid] = {"gold":0, "rpg":{"lv":1,"hp":100,"atk":10}, "favorability":0, "equip":{"weapon":"无","armor":"无"}}
        u = user_data[uid]
        
        if u["gold"] < cost:
            return await interaction.response.send_message(f"💸 余额不足！", ephemeral=True)
        
        msg = ""
        ai_prompt = ""
        action_type = "normal_chat"
        fav_stage = get_favorability_stage(u.get("favorability", 0))

        # --- 购买逻辑分发 ---
        if self.category == "potions":
            # 回复类：直接加血
            hp_rec = item_data['hp_rec']
            current_hp = u.get("rpg", {}).get("hp", 100)
            
            # 简单假设上限是 100 + 装备加成，这里为了简单只判断基础上限100
            # 或者直接允许溢出一点点也行，这里做个简单限制
            if current_hp >= 500: # 假设绝对上限
                return await interaction.response.send_message("❌ 你的状态已经很好了，喝不下了！", ephemeral=True)
            
            u["gold"] -= cost
            u["rpg"]["hp"] = current_hp + hp_rec
            msg = f"🧪 咕嘟咕嘟... 你喝下了 **{item_name}**！ (HP +{hp_rec} -> {u['rpg']['hp']})"
            ai_prompt = f"用户在你面前喝下了{item_name}，气色变好了。请评价一句。"

        elif self.category == "tools":
            # 功能类
            if item_name == "赎罪券":
                current_fav = u.get("favorability", 0)
                if current_fav >= 0:
                     return await interaction.response.send_message("❌ 你和Bot并没有仇恨，不需要赎罪。", ephemeral=True)
                u["gold"] -= cost
                u["favorability"] = 0
                msg = f"📜 你使用了 **赎罪券**。神圣的光芒照耀下，过去的恩怨一笔勾销。(好感度重置为 0)"
                ai_prompt = f"用户使用了赎罪券，消除了你对他的所有仇恨（原本好感度{current_fav}）。你感觉突然释怀了，请表现出这种态度的转变。"
            else:
                 # 其他道具暂未实现
                 return await interaction.response.send_message("❌ 该道具暂未实装效果。", ephemeral=True)

        elif self.category == "weapons":
            u["gold"] -= cost
            u["equip"]["weapon"] = item_name
            u.setdefault("rpg", {})["atk"] = 10 + item_data['atk']
            msg = f"✅ 购买并装备了 **{item_name}**！(ATK {u['rpg']['atk']})"
            ai_prompt = f"用户在你这里买了一把{item_name}。当前好感度阶段：{fav_stage['title']}。请评价他的眼光。"

        elif self.category == "armors":
            u["gold"] -= cost
            u["equip"]["armor"] = item_name
            u.setdefault("rpg", {})["hp"] = 100 + item_data['hp'] 
            u["rpg"]["def"] = item_data.get('def', 0)
            msg = f"✅ 购买并穿戴了 **{item_name}**！(HP {u['rpg']['hp']} | DEF {u['rpg']['def']})"
            ai_prompt = f"用户换上了{item_name}。当前好感度阶段：{fav_stage['title']}。请评价他的新造型。"

        elif self.category == "gifts":
            u["gold"] -= cost
            fav_add = item_data['fav']
            u["favorability"] = u.get("favorability", 0) + fav_add
            msg = f"🎁 送出了 **{item_name}**！ (好感度 +{fav_add})"
            action_type = "gift_receive"
            ai_prompt = (
                f"用户送了你一份礼物：【{item_name}】。\n"
                f"礼物描述：{item_data['desc']}。\n"
                f"礼物价值：{cost}G。\n"
            )
        
        save_user_data(user_data)
        
        # 统一调用 AI 回复
        reply = await ask_ai(
            ai_prompt, 
            self.bot_token, 
            interaction.user.display_name, 
            user_id=interaction.user.id,
            current_fav=u.get("favorability", 0),
            pure_reply=True,
            action_type=action_type
        )
        
        await interaction.response.send_message(f"{msg}\n\n🤖 **Bot:** {reply}", ephemeral=True)

class ShopCategoryView(ui.View):
    def __init__(self, bot_token):
        super().__init__()
        self.bot_token = bot_token

    @ui.button(label="⚔️ 武器区", style=discord.ButtonStyle.primary)
    async def show_weapons(self, interaction: discord.Interaction, button: ui.Button):
        view = ui.View()
        view.add_item(ShopItemSelect("weapons", self.bot_token))
        await interaction.response.send_message("🛡️ **请选择武器：**", view=view, ephemeral=True)

    @ui.button(label="🛡️ 防具区", style=discord.ButtonStyle.primary)
    async def show_armors(self, interaction: discord.Interaction, button: ui.Button):
        view = ui.View()
        view.add_item(ShopItemSelect("armors", self.bot_token))
        await interaction.response.send_message("👕 **请选择防具/服装：**", view=view, ephemeral=True)

    @ui.button(label="💊 炼金药房", style=discord.ButtonStyle.success)
    async def show_potions(self, interaction: discord.Interaction, button: ui.Button):
        view = ui.View()
        view.add_item(ShopItemSelect("potions", self.bot_token))
        await interaction.response.send_message("🧪 **来点什么药水？**", view=view, ephemeral=True)

    @ui.button(label="🔮 奇物店", style=discord.ButtonStyle.secondary)
    async def show_tools(self, interaction: discord.Interaction, button: ui.Button):
        view = ui.View()
        view.add_item(ShopItemSelect("tools", self.bot_token))
        await interaction.response.send_message("🔮 **这里出售一些不可思议的道具...**", view=view, ephemeral=True)

    @ui.button(label="🎁 礼物区", style=discord.ButtonStyle.danger)
    async def show_gifts(self, interaction: discord.Interaction, button: ui.Button):
        view = ui.View()
        view.add_item(ShopItemSelect("gifts", self.bot_token))
        await interaction.response.send_message("🎀 **想送什么给我呢？**", view=view, ephemeral=True)

class EventVoteView(ui.View):
    def __init__(self, bot, event_data):
        super().__init__(timeout=None)
        self.bot = bot
        self.event_data = event_data
        self.approvals = set()
        self.rejections = set()
        self.passed = False

    def update_stats(self):
        return f"✅ 同意: {len(self.approvals)}/3  |  ❌ 反对: {len(self.rejections)}/3"

    @ui.button(label="同意", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id in self.approvals: return await interaction.response.send_message("你已经投过赞成票了", ephemeral=True)
        if interaction.user.id in self.rejections: self.rejections.remove(interaction.user.id)
        self.approvals.add(interaction.user.id)
        if len(self.approvals) >= 3 and not self.passed:
            self.passed = True
            config = load_config()
            if "custom_events" not in config["default_settings"]: config["default_settings"]["custom_events"] = []
            config["default_settings"]["custom_events"].append(self.event_data)
            save_config(config)
            for child in self.children: child.disabled = True
            await interaction.response.edit_message(content=f"🎉 **事件已通过并录入！**\n{self.update_stats()}", view=self)
        else:
            await interaction.response.edit_message(content=f"📊 **投票进行中...**\n{self.update_stats()}", view=self)

    @ui.button(label="反对", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id in self.rejections: return await interaction.response.send_message("你已经投过反对票了", ephemeral=True)
        if interaction.user.id in self.approvals: self.approvals.remove(interaction.user.id)
        self.rejections.add(interaction.user.id)
        if len(self.rejections) >= 3 and not self.passed:
            self.passed = True
            for child in self.children: child.disabled = True
            await interaction.response.edit_message(content=f"🚫 **事件被驳回。**\n{self.update_stats()}", view=self)
        else:
            await interaction.response.edit_message(content=f"📊 **投票进行中...**\n{self.update_stats()}", view=self)

class EventDefineModal(ui.Modal, title="📝 定义探索事件"):
    content = ui.TextInput(label="探索内容", style=discord.TextStyle.short, required=True)
    success = ui.TextInput(label="成功结果", style=discord.TextStyle.paragraph, required=True)
    fail = ui.TextInput(label="失败结果", style=discord.TextStyle.paragraph, required=True)
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
    async def on_submit(self, interaction: discord.Interaction):
        event_data = {"author": interaction.user.display_name,"content": self.content.value,"success": self.success.value,"fail": self.fail.value}
        embed = discord.Embed(title="🗳️ 新探索事件提案", description=f"提案人: {interaction.user.mention}", color=0xffff00)
        embed.add_field(name="📜 事件", value=self.content.value, inline=False)
        embed.add_field(name="✅ 成功时", value=self.success.value, inline=True)
        embed.add_field(name="❌ 失败时", value=self.fail.value, inline=True)
        view = EventVoteView(self.bot, event_data)
        await interaction.response.send_message(embed=embed, view=view)

class CardModal(ui.Modal, title="✨ 个人档案设置"):
    story = ui.TextInput(label="人设 / 背景故事", style=discord.TextStyle.paragraph, max_length=1000)
    def __init__(self, bot_token):
        super().__init__()
        self.bot_token = bot_token
    async def on_submit(self, interaction: discord.Interaction):
        user_data = load_user_data()
        uid = str(interaction.user.id)
        if uid not in user_data: user_data[uid] = {"favorability": 0, "rpg": {"lv":1, "hp":100}, "gold":0}
        user_data[uid]["card"] = self.story.value
        save_user_data(user_data)
        reply = await ask_ai(f"用户更新了名片：{self.story.value}。请评价。", self.bot_token, interaction.user.display_name, pure_reply=True)
        await interaction.response.send_message(f"✅ 更新成功。\n🤖 {reply}", ephemeral=True)