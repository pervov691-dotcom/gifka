import requests
import logging
import random
import json
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaAnimation
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ========== КОНФИГИ ==========
TELEGRAM_TOKEN = "8746170424:AAFns7K0FrVQoZYUFkprabymePhH8bW3c-k"
GIPHY_API_KEY = "OFZTXXAeFZTtVyyNhSRfTHdokqwgAglu"
ADMIN_IDS = [1320819190]
FREE_REQUESTS_LIMIT = 3
REFERRAL_BONUS = 3
DAILY_BONUS = 1

# ========== НАСТРОЙКИ ==========
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# ========== ДАННЫЕ ==========
user_data = {}
user_stats = defaultdict(int)
daily_stats = defaultdict(int)
last_gifs = {}
popular_cache = {}
user_history = defaultdict(list)  # default dict - автоматически создаёт список
user_favorites = defaultdict(list)
user_daily = {}
user_referrals = defaultdict(int)

# ========== ФАЙЛЫ ДЛЯ СОХРАНЕНИЯ ==========
FILES = {
    'user_data': 'user_data.json',
    'user_stats': 'user_stats.json',
    'daily_stats': 'daily_stats.json',
    'user_favorites': 'user_favorites.json',
    'user_history': 'user_history.json',
    'popular_cache': 'popular_cache.json',
    'user_daily': 'user_daily.json',
    'user_referrals': 'user_referrals.json'
}

# ========== ЗАГРУЗКА/СОХРАНЕНИЕ ДАННЫХ ==========
def load_all_data():
    global user_data, user_stats, daily_stats, user_favorites, user_history, popular_cache, user_daily, user_referrals
    try:
        with open(FILES['user_data'], 'r', encoding='utf-8') as f:
            user_data = {int(k): v for k, v in json.load(f).items()}
    except: user_data = {}
    try:
        with open(FILES['user_stats'], 'r', encoding='utf-8') as f:
            loaded = json.load(f)
            user_stats = defaultdict(int, loaded)
    except: user_stats = defaultdict(int)
    try:
        with open(FILES['daily_stats'], 'r', encoding='utf-8') as f:
            loaded = json.load(f)
            daily_stats = defaultdict(int, loaded)
    except: daily_stats = defaultdict(int)
    try:
        with open(FILES['user_favorites'], 'r', encoding='utf-8') as f:
            loaded = json.load(f)
            user_favorites = defaultdict(list, {int(k): v for k, v in loaded.items()})
    except: user_favorites = defaultdict(list)
    try:
        with open(FILES['user_history'], 'r', encoding='utf-8') as f:
            loaded = json.load(f)
            user_history = defaultdict(list, {int(k): v for k, v in loaded.items()})
    except: user_history = defaultdict(list)
    try:
        with open(FILES['popular_cache'], 'r', encoding='utf-8') as f:
            popular_cache = json.load(f)
    except: popular_cache = {}
    try:
        with open(FILES['user_daily'], 'r', encoding='utf-8') as f:
            user_daily = {int(k): v for k, v in json.load(f).items()}
    except: user_daily = {}
    try:
        with open(FILES['user_referrals'], 'r', encoding='utf-8') as f:
            loaded = json.load(f)
            user_referrals = defaultdict(int, loaded)
    except: user_referrals = defaultdict(int)
    print(f"✅ Загружены данные: {len(user_data)} пользователей")

def save_all_data():
    try:
        with open(FILES['user_data'], 'w', encoding='utf-8') as f:
            json.dump(user_data, f, ensure_ascii=False, indent=2)
        with open(FILES['user_stats'], 'w', encoding='utf-8') as f:
            json.dump(dict(user_stats), f, ensure_ascii=False, indent=2)
        with open(FILES['daily_stats'], 'w', encoding='utf-8') as f:
            json.dump(dict(daily_stats), f, ensure_ascii=False, indent=2)
        with open(FILES['user_favorites'], 'w', encoding='utf-8') as f:
            json.dump(dict(user_favorites), f, ensure_ascii=False, indent=2)
        with open(FILES['user_history'], 'w', encoding='utf-8') as f:
            json.dump({k: v for k, v in user_history.items()}, f, ensure_ascii=False, indent=2)
        with open(FILES['popular_cache'], 'w', encoding='utf-8') as f:
            json.dump(popular_cache, f, ensure_ascii=False, indent=2)
        with open(FILES['user_daily'], 'w', encoding='utf-8') as f:
            json.dump(user_daily, f, ensure_ascii=False, indent=2)
        with open(FILES['user_referrals'], 'w', encoding='utf-8') as f:
            json.dump(dict(user_referrals), f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
        return False

async def auto_save():
    while True:
        await asyncio.sleep(300)
        save_all_data()

# ========== УМНЫЙ ПЕРЕВОД ЗАПРОСОВ ==========
TRANSLATION_DICT = {
    "смешной кот": "funny cat", "смешная кошка": "funny cat", "кот": "cat", "кошка": "cat",
    "собака": "dog", "пёс": "dog", "смех": "laugh", "смешно": "funny", "ржу": "laughing",
    "привет": "hello", "здравствуй": "hello", "пока": "goodbye", "до свидания": "goodbye",
    "любовь": "love", "сердце": "heart", "обнимаю": "hug", "целую": "kiss",
    "победа": "victory", "ура": "hooray", "красава": "awesome", "круто": "cool",
    "грустно": "sad", "печаль": "sad", "плачу": "crying", "с днём рождения": "happy birthday",
    "спасибо": "thank you", "извини": "sorry", "да": "yes", "нет": "no", "ок": "ok",
    "вау": "wow", "класс": "great", "супер": "super", "ого": "wow"
}

def smart_translate(query):
    query_lower = query.lower()
    if query_lower in TRANSLATION_DICT:
        return TRANSLATION_DICT[query_lower]
    for ru, en in TRANSLATION_DICT.items():
        if ru in query_lower:
            return en
    return query

# ========== GIPHY API ==========
def search_gif(query, limit=20):
    global popular_cache
    cache_key = query.lower()
    if cache_key in popular_cache:
        cached = popular_cache[cache_key]
        if datetime.now().timestamp() - cached['timestamp'] < 3600:
            print(f"📦 Кэш: {query}")
            return cached['gifs']
    
    search_query = smart_translate(query)
    url = "https://api.giphy.com/v1/gifs/search"
    params = {
        "api_key": GIPHY_API_KEY,
        "q": search_query,
        "limit": limit,
        "rating": "g",
        "lang": "ru"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            gifs_data = data.get("data", [])
            if gifs_data:
                gifs = [{"url": g["images"]["original"]["url"], "title": g.get("title", query), "id": g["id"]} for g in gifs_data[:limit]]
                if gifs:
                    popular_cache[cache_key] = {'gifs': gifs, 'timestamp': datetime.now().timestamp()}
                    return gifs
        return []
    except Exception as e:
        print(f"❌ Ошибка GIPHY: {e}")
        return []

def get_random_gif(query=None):
    if query:
        gifs = search_gif(query, limit=20)
        return random.choice(gifs) if gifs else None
    random_queries = ["funny", "cute", "awesome", "cool", "happy", "love", "cat", "dog"]
    gifs = search_gif(random.choice(random_queries), limit=20)
    return random.choice(gifs) if gifs else None

# ========== ПРОВЕРКА ПОДПИСКИ ==========
async def check_sub(user_id, context):
    try:
        member = await context.bot.get_chat_member(chat_id="@vne_sebya_ai", user_id=user_id)
        return member.status in ['member', 'creator', 'administrator']
    except:
        return False

def can_use(user_id, is_sub):
    if is_sub:
        return True, "Безлимит ✨"
    if user_id not in user_data:
        user_data[user_id] = {"requests": 0, "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    remaining = FREE_REQUESTS_LIMIT - user_data[user_id]["requests"]
    if remaining > 0:
        return True, f"Осталось {remaining}/{FREE_REQUESTS_LIMIT} 🎁"
    return False, "Лимит исчерпан 🔒"

# ========== ЕЖЕДНЕВНЫЙ БОНУС ==========
async def check_daily_bonus(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    if user_id not in user_daily or user_daily[user_id] != today:
        user_daily[user_id] = today
        if user_id not in user_data:
            user_data[user_id] = {"requests": 0}
        user_data[user_id]["requests"] = max(0, user_data[user_id]["requests"] - DAILY_BONUS)
        save_all_data()
        return True, DAILY_BONUS
    return False, 0

# ========== СТАТИСТИКА ==========
def get_today_stats():
    today = datetime.now().strftime("%Y-%m-%d")
    active_users = len([uid for uid, data in user_data.items() if data.get("last_active", "").startswith(today)])
    return daily_stats.get(today, 0), active_users

def generate_hourly_stats():
    hourly = defaultdict(int)
    today = datetime.now().strftime("%Y-%m-%d")
    for uid, data in user_data.items():
        if data.get("last_active", "").startswith(today):
            try:
                hour = int(data["last_active"].split()[1].split(":")[0])
                hourly[hour] += 1
            except: pass
    if not hourly:
        return "Пока нет данных"
    result = ""
    for hour in range(24):
        count = hourly.get(hour, 0)
        bar = "█" * min(count, 10) if count > 0 else "░"
        result += f"{hour:02d}:00 {bar} {count}\n"
    return result

# ========== КЛАВИАТУРЫ ==========
def main_keyboard(user_id=None):
    keyboard = [
        [InlineKeyboardButton("🔍 Найти гифку", callback_data="search"), InlineKeyboardButton("🎲 Случайная", callback_data="random_gif")],
        [InlineKeyboardButton("⭐ Избранное", callback_data="favorites"), InlineKeyboardButton("📜 История", callback_data="history")],
        [InlineKeyboardButton("📢 Наш канал", url="https://t.me/vne_sebya_ai"), InlineKeyboardButton("👥 Пригласить друга", callback_data="referral")],
        [InlineKeyboardButton("✅ Проверить подписку", callback_data="check_sub"), InlineKeyboardButton("🎁 Ежедневный бонус", callback_data="daily_bonus")],
        [InlineKeyboardButton("🏆 Топ пользователей", callback_data="top_users"), InlineKeyboardButton("❓ Помощь", callback_data="help")]
    ]
    if user_id and user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("⚙️ Админка", callback_data="admin")])
    return InlineKeyboardMarkup(keyboard)

def gif_keyboard(gif_id, query, user_id=None):
    keyboard = [
        [InlineKeyboardButton("🔄 Другая", callback_data=f"again_{query}"), InlineKeyboardButton("⭐ В избранное", callback_data=f"fav_{gif_id}_{query}")],
        [InlineKeyboardButton("📤 Отправить другу", callback_data=f"share_{gif_id}_{query}"), InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]
    ]
    if user_id and user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("⚙️ Админка", callback_data="admin")])
    return InlineKeyboardMarkup(keyboard)

def admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("📝 Редактировать тексты", callback_data="edit_texts")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"), InlineKeyboardButton("📅 Статистика за день", callback_data="admin_daily_stats")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"), InlineKeyboardButton("💾 Сохранить данные", callback_data="admin_save")],
        [InlineKeyboardButton("🔙 Назад", callback_data="menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def texts_edit_keyboard():
    keyboard = [
        [InlineKeyboardButton("📝 Приветствие", callback_data="edit_welcome"), InlineKeyboardButton("🏠 Главное меню", callback_data="edit_main_menu_text")],
        [InlineKeyboardButton("📖 Помощь", callback_data="edit_help_text"), InlineKeyboardButton("🔍 Поиск", callback_data="edit_search_prompt")],
        [InlineKeyboardButton("🔒 Подписка", callback_data="edit_subscribe_prompt"), InlineKeyboardButton("🎁 Бонус", callback_data="edit_daily_bonus_text")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ========== ТЕКСТЫ ==========
default_texts = {
    "welcome": "🌟 Привет, {name}!\n\n🎁 У тебя: {status}\n👥 Приглашено друзей: {referrals}\n\n🔍 Просто напиши запрос или нажми кнопку!",
    "main_menu_text": "🌟 Главное меню\n\nВыбери действие:",
    "help_text": "📖 **Как пользоваться**\n\n• Напиши любое слово или фразу\n• Нажми «Другая» для другой гифки\n• ⭐ Добавляй в избранное\n• 👥 Приглашай друзей за бонусы\n• 🎁 Забирай ежедневный бонус\n\n📢 Канал: @vne_sebya_ai",
    "search_prompt": "🔍 Напиши что хочешь найти...\n\nПримеры: кот, смех, любовь, победа",
    "loading": "🔍 Ищу гифку...",
    "not_found": "😕 Ничего не нашёл по запросу «{query}»",
    "subscribe_prompt": "🔒 Подпишись на канал @vne_sebya_ai\n\n🎁 Осталось {remaining}/{limit}",
    "subscribed": "✅ Подписка подтверждена! Безлимит ✨",
    "not_subscribed": "❌ Ты не подписан на канал @vne_sebya_ai",
    "daily_bonus_text": "🎁 Ежедневный бонус!\n\n+{bonus} бесплатных запросов",
    "already_claimed": "⏰ Ты уже забирал бонус сегодня!\n\nВозвращайся завтра!",
    "referral_text": "👥 **Пригласи друга!**\n\nОтправь другу ссылку:\n`https://t.me/{bot_username}?start={user_id}`\n\nЗа каждого друга +{bonus} запросов!"
}

texts = default_texts.copy()
TEXTS_FILE = 'bot_texts.json'

def load_texts():
    global texts
    try:
        with open(TEXTS_FILE, 'r', encoding='utf-8') as f:
            texts.update(json.load(f))
    except: save_texts()
def save_texts():
    with open(TEXTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(texts, f, ensure_ascii=False, indent=2)

load_texts()

# ========== КОМАНДЫ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.effective_user.first_name or "друг"
    
    args = context.args
    if args and args[0].isdigit() and int(args[0]) != user_id:
        referrer = int(args[0])
        if referrer in user_data:
            if 'referrals' not in user_data[referrer]:
                user_data[referrer]['referrals'] = []
            if user_id not in user_data[referrer]['referrals']:
                user_data[referrer]["requests"] = user_data[referrer].get("requests", 0) + REFERRAL_BONUS
                user_data[referrer]['referrals'].append(user_id)
                user_referrals[referrer] += 1
                await context.bot.send_message(referrer, f"🎉 Друг присоединился по твоей ссылке! +{REFERRAL_BONUS} запросов!")
    
    if user_id not in user_data:
        user_data[user_id] = {"requests": 0, "name": name, "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    user_data[user_id]["last_active"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    is_sub = await check_sub(user_id, context)
    remaining = FREE_REQUESTS_LIMIT - user_data[user_id].get("requests", 0)
    status = "Безлимит ✨" if is_sub else f"Осталось {remaining}/{FREE_REQUESTS_LIMIT} 🎁"
    
    text = texts['welcome'].format(name=name, status=status, referrals=user_referrals.get(user_id, 0))
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=main_keyboard(user_id))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = update.message.text.strip()
    
    # Проверяем режимы админа
    if context.user_data.get('editing_mode') or context.user_data.get('broadcast_mode'):
        return
    if not query:
        return
    
    # Инициализируем пользователя, если его нет
    if user_id not in user_data:
        user_data[user_id] = {"requests": 0, "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    user_data[user_id]["last_active"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Ежедневный бонус
    bonus_claimed, bonus = await check_daily_bonus(user_id)
    if bonus_claimed:
        await update.message.reply_text(texts['daily_bonus_text'].format(bonus=bonus))
    
    is_sub = await check_sub(user_id, context)
    can, msg = can_use(user_id, is_sub)
    
    if not can:
        remaining = FREE_REQUESTS_LIMIT - user_data[user_id].get("requests", 0)
        await update.message.reply_text(texts['subscribe_prompt'].format(remaining=remaining, limit=FREE_REQUESTS_LIMIT), reply_markup=main_keyboard(user_id))
        return
    
    if not is_sub:
        user_data[user_id]["requests"] = user_data[user_id].get("requests", 0) + 1
    
    # Сохраняем историю (теперь с defaultdict проблем не будет)
    user_history[user_id].insert(0, query)
    user_history[user_id] = user_history[user_id][:10]
    user_stats[query] += 1
    daily_stats[datetime.now().strftime("%Y-%m-%d")] += 1
    
    status_msg = await update.message.reply_text(texts['loading'])
    gif = get_random_gif(query)
    
    if gif:
        last_gifs[user_id] = {"query": query, "gifs": search_gif(query, limit=20)}
        await status_msg.delete()
        await update.message.reply_animation(
            gif["url"],
            caption=f"🎬 {query}\n\n{msg}",
            reply_markup=gif_keyboard(gif["id"], query, user_id)
        )
    else:
        await status_msg.edit_text(texts['not_found'].format(query=query), reply_markup=main_keyboard(user_id))

# ========== КНОПКИ ==========
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    await query.answer()
    
    # ========== ГЛАВНОЕ МЕНЮ ==========
    if data == "menu":
        try:
            await query.edit_message_text(texts['main_menu_text'], reply_markup=main_keyboard(user_id))
        except:
            try:
                await query.delete_message()
                await query.message.reply_text(texts['main_menu_text'], reply_markup=main_keyboard(user_id))
            except:
                await query.message.reply_text(texts['main_menu_text'], reply_markup=main_keyboard(user_id))
        return
    
    if data == "search":
        await query.edit_message_text(texts['search_prompt'], reply_markup=main_keyboard(user_id))
        return
    
    if data == "random_gif":
        gif = get_random_gif()
        if gif:
            await query.message.reply_animation(gif["url"], caption="🎲 Случайная гифка!", reply_markup=gif_keyboard(gif["id"], "random", user_id))
            await query.delete_message()
        else:
            await query.edit_message_text("😕 Не удалось загрузить гифку", reply_markup=main_keyboard(user_id))
        return
    
    if data == "favorites":
        favs = user_favorites.get(user_id, [])
        if favs:
            text = "⭐ **Твои любимые гифки:**\n\n"
            for i, fav in enumerate(favs[:10], 1):
                text += f"{i}. {fav['query']}\n"
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=main_keyboard(user_id))
        else:
            await query.edit_message_text("⭐ У тебя пока нет избранных гифок\n\nДобавляй их кнопкой «В избранное» под гифкой!", reply_markup=main_keyboard(user_id))
        return
    
    if data == "history":
        history = user_history.get(user_id, [])
        if history:
            text = "📜 **Твои последние запросы:**\n\n"
            for i, h in enumerate(history[:10], 1):
                text += f"{i}. {h}\n"
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=main_keyboard(user_id))
        else:
            await query.edit_message_text("📜 История запросов пуста", reply_markup=main_keyboard(user_id))
        return
    
    if data == "referral":
        bot_username = context.bot.username
        text = texts['referral_text'].format(bot_username=bot_username, user_id=user_id, bonus=REFERRAL_BONUS)
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=main_keyboard(user_id))
        return
    
    if data == "daily_bonus":
        claimed, bonus = await check_daily_bonus(user_id)
        if claimed:
            await query.edit_message_text(texts['daily_bonus_text'].format(bonus=bonus), reply_markup=main_keyboard(user_id))
        else:
            await query.edit_message_text(texts['already_claimed'], reply_markup=main_keyboard(user_id))
        return
    
    if data == "top_users":
        top = sorted(user_data.items(), key=lambda x: x[1].get("requests", 0), reverse=True)[:10]
        text = "🏆 **Топ пользователей:**\n\n"
        for i, (uid, data_user) in enumerate(top, 1):
            name = data_user.get("name", str(uid))[:20]
            requests = data_user.get("requests", 0)
            text += f"{i}. {name} — {requests} запросов\n"
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=main_keyboard(user_id))
        return
    
    if data == "check_sub":
        is_sub = await check_sub(user_id, context)
        text = texts['subscribed'] if is_sub else texts['not_subscribed']
        await query.edit_message_text(text, reply_markup=main_keyboard(user_id))
        return
    
    if data == "help":
        await query.edit_message_text(texts['help_text'], parse_mode='Markdown', reply_markup=main_keyboard(user_id))
        return
    
    if data.startswith("fav_"):
        parts = data.split("_")
        gif_id = parts[1]
        gif_query = "_".join(parts[2:])
        fav_item = {"id": gif_id, "query": gif_query}
        if fav_item not in user_favorites.get(user_id, []):
            user_favorites[user_id].append(fav_item)
            save_all_data()
            await query.answer("⭐ Добавлено в избранное!", show_alert=True)
        else:
            await query.answer("Уже в избранном", show_alert=True)
        return
    
    if data.startswith("share_"):
        parts = data.split("_")
        gif_id = parts[1]
        gif_query = "_".join(parts[2:])
        await query.edit_message_text(f"📤 Отправь эту ссылку другу:\n\n`https://t.me/share/url?url=Гифка%20на%20запрос%20{gif_query}`", parse_mode='Markdown', reply_markup=gif_keyboard(gif_id, gif_query, user_id))
        return
    
    if data.startswith("again_"):
        original_query = data.replace("again_", "")
        is_sub = await check_sub(user_id, context)
        can, msg = can_use(user_id, is_sub)
        if not can:
            remaining = FREE_REQUESTS_LIMIT - user_data[user_id].get("requests", 0)
            await query.edit_message_text(texts['subscribe_prompt'].format(remaining=remaining, limit=FREE_REQUESTS_LIMIT), reply_markup=main_keyboard(user_id))
            return
        gif = get_random_gif(original_query)
        if gif:
            media = InputMediaAnimation(media=gif["url"], caption=f"🎬 {original_query}\n\n{msg}")
            await query.edit_message_media(media=media, reply_markup=gif_keyboard(gif["id"], original_query, user_id))
        else:
            await query.edit_message_text(texts['not_found'].format(query=original_query), reply_markup=main_keyboard(user_id))
        return
    
    # ========== АДМИНКА ==========
    if data == "admin":
        if user_id not in ADMIN_IDS:
            await query.answer("⛔ Доступ запрещён", show_alert=True)
            return
        await query.edit_message_text("⚙️ Админ-панель", reply_markup=admin_keyboard())
        return
    
    if data == "admin_save":
        if save_all_data():
            await query.edit_message_text("✅ Данные сохранены!", reply_markup=admin_keyboard())
        else:
            await query.edit_message_text("❌ Ошибка сохранения", reply_markup=admin_keyboard())
        return
    
    if data == "admin_broadcast":
        context.user_data['broadcast_mode'] = True
        await query.edit_message_text("📢 Введите текст для рассылки:\n\nДля отмены напишите /отмена", reply_markup=admin_keyboard())
        return
    
    if data == "admin_stats":
        total_users = len(user_data)
        total_requests = sum(u.get("requests", 0) for u in user_data.values())
        total_favs = sum(len(f) for f in user_favorites.values())
        top = sorted(user_stats.items(), key=lambda x: x[1], reverse=True)[:5]
        top_text = "\n".join([f"{i+1}. {q} — {c}" for i, (q, c) in enumerate(top)]) if top else "Пока нет"
        await query.edit_message_text(
            f"📊 **Статистика**\n\n👥 Пользователей: {total_users}\n📈 Запросов: {total_requests}\n⭐ Избранного: {total_favs}\n\n🏆 **Топ запросов:**\n{top_text}",
            parse_mode='Markdown', reply_markup=admin_keyboard()
        )
        return
    
    if data == "admin_daily_stats":
        today_requests, today_users = get_today_stats()
        await query.edit_message_text(
            f"📅 **Статистика за сегодня**\n\n📊 Запросов: {today_requests}\n👥 Пользователей: {today_users}\n\n📈 **Активность по часам:**\n{generate_hourly_stats()}",
            parse_mode='Markdown', reply_markup=admin_keyboard()
        )
        return
    
    if data == "edit_texts":
        await query.edit_message_text("📝 Выбери текст для редактирования:", reply_markup=texts_edit_keyboard())
        return
    
    if data.startswith("edit_"):
        field = data.replace("edit_", "")
        context.user_data['editing_mode'] = field
        current = texts.get(field, "Текст не найден")
        await query.edit_message_text(f"📝 Редактируем: {field}\n\nТекущий текст:\n`{current}`\n\nОтправь новый текст:\n/отмена - отменить", parse_mode='Markdown', reply_markup=texts_edit_keyboard())
        return

# ========== РАССЫЛКА ==========
async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return
    if not context.user_data.get('broadcast_mode'):
        return
    
    message = update.message.text.strip()
    if message == "/отмена":
        context.user_data['broadcast_mode'] = False
        await update.message.reply_text("❌ Рассылка отменена", reply_markup=admin_keyboard())
        return
    
    await update.message.reply_text("📢 Начинаю рассылку...")
    success = 0
    fail = 0
    for uid in user_data.keys():
        try:
            await context.bot.send_message(uid, f"📢 **Сообщение от админа:**\n\n{message}", parse_mode='Markdown')
            success += 1
            await asyncio.sleep(0.05)
        except:
            fail += 1
    await update.message.reply_text(f"✅ Рассылка завершена!\n\nДоставлено: {success}\nОшибок: {fail}", reply_markup=admin_keyboard())
    context.user_data['broadcast_mode'] = False

# ========== РЕДАКТИРОВАНИЕ ТЕКСТОВ ==========
async def handle_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return
    if not context.user_data.get('editing_mode'):
        return
    
    field = context.user_data['editing_mode']
    new_text = update.message.text.strip()
    
    if new_text == "/отмена":
        context.user_data['editing_mode'] = None
        await update.message.reply_text("❌ Редактирование отменено", reply_markup=admin_keyboard())
        return
    
    texts[field] = new_text
    save_texts()
    context.user_data['editing_mode'] = None
    await update.message.reply_text(f"✅ Текст обновлён!\n\n`{new_text[:200]}`", parse_mode='Markdown', reply_markup=admin_keyboard())

# ========== ЗАПУСК ==========
async def post_init(app: Application):
    app.create_task(auto_save())

def main():
    if TELEGRAM_TOKEN == "ТВОЙ_ТОКЕН_БОТА":
        print("❌ Вставь токен бота!")
        return
    if GIPHY_API_KEY == "ТВОЙ_КЛЮЧ_GIPHY":
        print("❌ Вставь GIPHY ключ!")
        return
    
    load_all_data()
    
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_broadcast))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("=" * 50)
    print("🚀 СУПЕР БОТ НА GIPHY ЗАПУЩЕН!")
    print(f"👑 Админ: {ADMIN_IDS[0]}")
    print("✅ Все улучшения активны!")
    print("=" * 50)
    print("🎁 Функции:")
    print("  • Умный поиск с переводом")
    print("  • Кэширование запросов")
    print("  • История запросов")
    print("  • Избранное")
    print("  • Реферальная система")
    print("  • Ежедневный бонус")
    print("  • Случайная гифка")
    print("  • Топ пользователей")
    print("  • Рассылка для админа")
    print("=" * 50)
    
    app.run_polling()

if __name__ == "__main__":
    main()
