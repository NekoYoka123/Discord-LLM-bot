import os
import asyncio
from quart import Quart, render_template, request, redirect, url_for
from .config import load_config, save_config, load_user_data, save_user_data
from .discord_bot import start_bot, active_bots

app = Quart(__name__, template_folder='../templates')
app.secret_key = os.environ.get('QUART_SECRET_KEY', 'zeabur_secret_key_change_me')

@app.route('/')
async def index():
    config = load_config()
    selected_token = request.args.get('bot', 'default')
    
    if selected_token != 'default' and selected_token in config['bot_tokens']:
        if selected_token not in config['bot_settings']:
            config['bot_settings'][selected_token] = config['default_settings'].copy()
        current_conf = config['bot_settings'][selected_token]
    else:
        selected_token = 'default'
        current_conf = config['default_settings']

    bot_status = []
    for t in config['bot_tokens']:
        status = "🟢 运行中" if t in active_bots else "🔴 已停止"
        user_name = active_bots[t]['bot'].user.name if (t in active_bots and active_bots[t]['bot'].user) else "Bot"
        bot_status.append({"token_mask": t[:6]+"...", "full_token": t, "status": status, "user": user_name})

    users = load_user_data()
    return await render_template('index.html', bots=bot_status, apis=config['api_configs'], config=current_conf, selected_token=selected_token, all_tokens=config['bot_tokens'], users=users)

@app.route('/manage_bot', methods=['POST'])
async def manage_bot():
    form = await request.form
    action = form.get('action')
    token = form.get('token')
    config = load_config()
    if action == 'add':
        new = form.get('new_token').strip()
        if new and new not in config['bot_tokens']:
            config['bot_tokens'].append(new)
            save_config(config)
            asyncio.create_task(start_bot(new))
    elif action == 'start': asyncio.create_task(start_bot(token))
    elif action == 'stop':
        if token in active_bots:
            await active_bots[token]["bot"].close()
            del active_bots[token]
    elif action == 'delete':
        if token in active_bots:
            await active_bots[token]["bot"].close()
            del active_bots[token]
        if token in config['bot_tokens']: config['bot_tokens'].remove(token)
        save_config(config)
    return redirect(url_for('index'))

@app.route('/save_bot_settings', methods=['POST'])
async def save_bot_settings():
    form = await request.form
    target_token = form.get('target_token')
    config = load_config()
    prompts = [form.get(k).strip() for k in form if k.startswith('system_prompt_') and form.get(k).strip()]
    
    new_settings = {
        "system_prompts": prompts,
        "temperature": float(form.get('temperature', 0.7)),
        "knowledge": [],
        "custom_events": []
    }
    
    old_conf = config['bot_settings'].get(target_token, config['default_settings']) if target_token != 'default' else config['default_settings']
    new_settings['knowledge'] = old_conf.get('knowledge', [])
    new_settings['custom_events'] = old_conf.get('custom_events', [])

    if target_token == 'default': config['default_settings'] = new_settings
    else: config['bot_settings'][target_token] = new_settings
    
    save_config(config)
    return redirect(url_for('index', bot=target_token, tab='brain'))

@app.route('/api/knowledge/add', methods=['POST'])
async def api_add_knowledge():
    form = await request.form
    token = form.get('target_token')
    content = form.get('content').strip()
    config = load_config()
    target = config['default_settings'] if token == 'default' else config['bot_settings'].setdefault(token, config['default_settings'].copy())
    if "knowledge" not in target: target["knowledge"] = []
    target["knowledge"].append(content)
    save_config(config)
    return redirect(url_for('index', bot=token, tab='brain'))

@app.route('/api/knowledge/delete', methods=['POST'])
async def api_del_knowledge():
    form = await request.form
    token = form.get('target_token')
    idx = int(form.get('index'))
    config = load_config()
    target = config['default_settings'] if token == 'default' else config['bot_settings'].get(token, {})
    if "knowledge" in target and 0 <= idx < len(target["knowledge"]):
        target["knowledge"].pop(idx)
        save_config(config)
    return redirect(url_for('index', bot=token, tab='brain'))

@app.route('/update_api', methods=['POST'])
async def update_api():
    form = await request.form
    config = load_config()
    keys = [k.strip() for k in form.get('keys').split('\n') if k.strip()]
    config['api_configs'].append({"url": form.get('url'),"keys": keys,"model": form.get('model')})
    save_config(config)
    return redirect(url_for('index', tab='api'))

@app.route('/delete_api', methods=['POST'])
async def delete_api():
    idx = int((await request.form).get('index'))
    config = load_config()
    if 0 <= idx < len(config['api_configs']):
        config['api_configs'].pop(idx)
        save_config(config)
    return redirect(url_for('index', tab='api'))

@app.route('/user_cards')
async def user_cards_page(): return redirect(url_for('index') + "#content-players")

@app.route('/delete_card', methods=['POST'])
async def delete_card():
    uid = (await request.form).get('uid')
    data = load_user_data()
    if uid in data:
        del data[uid]
        save_user_data(data)
    return redirect(url_for('index') + "#content-players")

@app.route('/admin_say', methods=['POST'])
async def admin_say():
    form = await request.form
    token_mask = form.get('bot_token_mask')
    channel_id = int(form.get('channel_id'))
    message = form.get('message')
    target_bot = None
    for token, data in active_bots.items():
        if token.startswith(token_mask.split('.')[0]):
            target_bot = data['bot']
            break
    if target_bot:
        try: await target_bot.get_channel(channel_id).send(message)
        except: pass
    return redirect(url_for('index'))