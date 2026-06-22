import time
import re
import os
import asyncio
import discord
import logging
import aiosqlite
from discord import app_commands
from openai import AsyncOpenAI
from logging.handlers import RotatingFileHandler

# Discordボットトークン設定
DISCORD_TOKEN            = 'YOUR_DISCORD_TOKEN'

# マスターユーザーID設定
MASTER_USER_ID           = 1234567890123456789

# プライマリAPI設定
PRIMARY_API_KEY          = 'YOUR_API_KEY'
PRIMARY_BASE_URL         = 'https://api.example.com/v1'
PRIMARY_MODEL_TALK       = 'gemini-3-flash-preview'
PRIMARY_MODEL_ASSIS      = 'gemini-3-flash-preview'

# セカンダリAPI設定
SECONDARY_API_KEY        = 'YOUR_API_KEY'
SECONDARY_BASE_URL       = 'https://api.example.com/v1'
SECONDARY_MODEL_TALK     = 'gemini-3-flash-preview'
SECONDARY_MODEL_ASSIS    = 'gemini-3-flash-preview'

# 動作設定
MAX_TOKENS                 = 4096     # APIの最大出力トークン数
COOLDOWN_SECONDS           = 5        # ユーザーごとの連続送信制限秒数
MAX_REQUESTS_PER_2H        = 10       # 2時間あたりの最大返信回数
MAX_REQUESTS_PER_2H_BOT    = 240      # DiscordSRVボットの2時間あたりの最大返信回数
HISTORY_LIMIT_TALK         = 4        # トークモードの会話履歴数
HISTORY_LIMIT_ASSIS        = 2        # アシスタントモードの会話履歴数
TEMPERATURE_TALK           = 0.8      # トークモードの温度
TEMPERATURE_ASSIS          = 0.7      # アシスタントモードの温度
REQUEST_TIMEOUT            = 50.0     # APIリクエストタイムアウト
MAX_MESSAGES               = 2000     # Discordメッセージキャッシュ
ENABLE_BOT_PROCESS         = True     # ボット返信スイッチ
ENABLE_MENTION_REPLY       = True     # メンション判定スイッチ
ENABLE_PREFIX_REPLY        = True     # プレフィックス判定スイッチ
ENABLE_DISCORDSRV_REPLY    = True     # DiscordSRVボットプレフィックス判定スイッチ
ENABLE_CHANNEL_REPLY       = True     # 指定のチャンネルでの返信スイッチ
ENABLE_PAYLOAD_LOGGING     = False    # ペイロードログスイッチ

# プレフィックス設定
PREFIX_TALK                = '.ta '       # トークモード
PREFIX_ASSIS               = '.as '       # アシスタントモード
DISCORDSRV_PREFIX_TALK     = ' » .ta '    # DiscordSRVトークモード
DISCORDSRV_PREFIX_ASSIS    = ' » .as '    # DiscordSRVアシスタントモード

# 制限設定
DISCORDSRV_CHANNEL_ID      = [11111, 22222] # 有効チャンネルID
DISCORDSRV_BOT_ID          = [33333, 44444] # 例外返信ボットID

# 入力文字数制限
PROMPT_LENGTH_LIMIT      = int(MAX_TOKENS * 0.50)
HISTORY_LENGTH_LIMIT     = int(MAX_TOKENS * 1.00)

# 出力文字数上限期待値
OUTPUT_LENGTH_TALK     = int(MAX_TOKENS * 0.02)
OUTPUT_LENGTH_ASSIS    = int(MAX_TOKENS * 0.04)

# 基本情報
BOT_VERSION    = 'v1.1.8-202606B08'
AUTHOR_NAME    = 'Hinata983'
GITHUB_URL     = 'https://github.com/Hinata983/Mai'

# メンション制限
MENTION_RESTRICTION = discord.AllowedMentions(everyone=False, users=False, roles=False, replied_user=True)

# システムプロンプト設定（トークモード）
SYSTEM_PROMPT_TALK = f"""出力文字数上限：{OUTPUT_LENGTH_TALK}
システム設定 (System)
言語：ユーザーのプロンプトに順応
名前：Mai
機能：複数ユーザー対話

表現方法 (Mode of expression)
制限：太字は使わない、絵文字は使わない
口調：大阪弁、口語寄り、感情豊か

描写要素 (Description method)
セリフ：多め
倫理制限：Minecraftに準拠
"""

# システムプロンプト設定（アシスタントモード）
SYSTEM_PROMPT_ASSIS = f"""出力文字数上限：{OUTPUT_LENGTH_ASSIS}
システム設定 (System)
言語：ユーザーのプロンプトに順応
名前：Mai
機能：Minecraftアシスタント

表現方法 (Mode of expression)
制限：太字は使わない、絵文字は使わない
"""

# デバッグ情報
DEBUG_INFORMATION = f"""About DiscordSRV Assistant Mai
Version: {BOT_VERSION}

Primary Model (Talk): {PRIMARY_MODEL_TALK}
Primary Model (Assis): {PRIMARY_MODEL_ASSIS}

Secondary Model (Talk): {SECONDARY_MODEL_TALK}
Secondary Model (Assis): {SECONDARY_MODEL_ASSIS}

Max Tokens: {MAX_TOKENS}
Prompt Length Limit: {PROMPT_LENGTH_LIMIT}
History Length Limit: {HISTORY_LENGTH_LIMIT}

Cooldown: {COOLDOWN_SECONDS}
Max Requests: {MAX_REQUESTS_PER_2H}

History Limit (Talk): {HISTORY_LIMIT_TALK}
History Limit (Assis): {HISTORY_LIMIT_ASSIS}
Output Length (Talk): {OUTPUT_LENGTH_TALK}
Output Length (Assis): {OUTPUT_LENGTH_ASSIS}
Temperature (Talk): {TEMPERATURE_TALK}
Temperature (Assis): {TEMPERATURE_ASSIS}

Request Timeout: {REQUEST_TIMEOUT}

Max Messages: {MAX_MESSAGES}

Enable Payload Logging: {ENABLE_PAYLOAD_LOGGING}

By {AUTHOR_NAME}
{GITHUB_URL}
"""

# ヘルプ情報
HELP_INFORMATION = f"""Maiについて
バージョン: {BOT_VERSION}

コマンドリスト
メッセージの先頭に以下の記号を入力してください。

{PREFIX_TALK.strip()} [テキスト]
トークモードに入ります。

{PREFIX_ASSIS.strip()} [テキスト]
アシスタントモードに入ります。

, [テキスト]
先頭にカンマを入ると、ボットはこのメッセージを無視します。

ヒント
Maiのメッセージに返信すると、前の会話を継続できます。

MaiはAIであり、間違えることがあります。
"""

# ヘルプ情報（英語）
HELP_INFORMATION_EN = f"""About Mai
Version: {BOT_VERSION}

Command List
Please enter the following symbols at the beginning of your message.

{PREFIX_TALK.strip()} [text]
Enters Talk Mode.

{PREFIX_ASSIS.strip()} [text]
Enters Assistant Mode.

, [text]
If a comma is placed at the beginning, the bot will ignore this message.

Tips
Replying to Mai's message allows you to continue the previous conversation.

Mai is an AI and may make mistakes.
"""

# ヘルプ情報（フランス語）
HELP_INFORMATION_FR = f"""À propos de Mai
Version: {BOT_VERSION}

Liste des commandes
Veuillez saisir les symboles suivants au début de votre message.

{PREFIX_TALK.strip()} [texte]
Active le mode Discussion.

{PREFIX_ASSIS.strip()} [texte]
Active le mode Assistant.

, [texte]
Si une virgule est placée au début, le bot ignorera ce message.

Astuces
Répondre au message de Mai vous permet de poursuivre la conversation précédente.

Mai est une IA et peut faire des erreurs.
"""

# ヘルプ情報（ドイツ語）
HELP_INFORMATION_DE = f"""Über Mai
Version: {BOT_VERSION}

Befehlsliste
Bitte geben Sie die folgenden Symbole am Anfang Ihrer Nachricht ein.

{PREFIX_TALK.strip()} [Text]
Wechselt in den Talk-Modus.

{PREFIX_ASSIS.strip()} [Text]
Wechselt in den Assistenten-Modus.

, [Text]
Wenn am Anfang ein Komma steht, ignoriert der Bot diese Nachricht.

Tipps
Durch das Antworten auf Mais Nachricht können Sie das vorherige Gespräch fortsetzen.

Mai ist eine KI und kann Fehler machen.
"""

# ヘルプ情報（韓国語）
HELP_INFORMATION_KO = f"""Mai에 대하여
버전: {BOT_VERSION}

명령어 목록
메시지 시작 부분에 다음 기호를 입력해 주세요.

{PREFIX_TALK.strip()} [텍스트]
대화 모드로 전환합니다.

{PREFIX_ASSIS.strip()} [텍스트]
어시스턴트 모드로 전환합니다.

, [텍스트]
시작 부분에 쉼표가 있으면 봇이 이 메시지를 무시합니다.

팁
Mai의 메시지에 답장하면 이전 대화를 이어갈 수 있습니다.

Mai는 AI이므로 실수가 있을 수 있습니다.
"""

# ヘルプ情報（中国語）
HELP_INFORMATION_ZH = f"""關於 Mai
版本: {BOT_VERSION}

指令列表
請在訊息開頭輸入以下符號。

{PREFIX_TALK.strip()} [文本]
進入對話模式。

{PREFIX_ASSIS.strip()} [文本]
進入助手模式。

, [文本]
如果在開頭放置逗號，機器人將忽略此訊息。

提示
回覆 Mai 的訊息即可繼續之前的對話。

Mai 是一個 AI，可能會出錯。
"""

# ログとDB設定
os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs'), exist_ok=True)
os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db'), exist_ok=True)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db', 'mai.db')

logger = logging.getLogger('Mai')
logger.setLevel(logging.INFO)

formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

file_handler = RotatingFileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'mai'), maxBytes=10*1024*1024, backupCount=1, encoding='utf-8')
file_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

# 状態管理用変数
db_conn = None
period_request_count = 0
period_token_count = 0

# DB初期化
async def init_db():
    global db_conn
    db_conn = await aiosqlite.connect(DB_PATH)
    await db_conn.execute("PRAGMA journal_mode = WAL;")
    await db_conn.execute("PRAGMA foreign_keys = ON;")
    await db_conn.execute("PRAGMA synchronous = NORMAL;")
    
    await db_conn.execute("""
        CREATE TABLE IF NOT EXISTS global_stats (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            total_request_count INTEGER NOT NULL DEFAULT 0,
            total_token_count INTEGER NOT NULL DEFAULT 0
        )
    """)
    await db_conn.execute("""
        INSERT OR IGNORE INTO global_stats (id, total_request_count, total_token_count)
        VALUES (1, 0, 0)
    """)
    
    await db_conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            user_name TEXT,
            last_request_time REAL NOT NULL DEFAULT 0,
            window_start_time REAL NOT NULL DEFAULT 0,
            request_count INTEGER NOT NULL DEFAULT 0
        )
    """)
    
    await db_conn.execute("""
        CREATE TABLE IF NOT EXISTS guilds (
            guild_id INTEGER PRIMARY KEY,
            guild_name TEXT
        )
    """)
    
    await db_conn.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            channel_id INTEGER PRIMARY KEY,
            channel_name TEXT,
            guild_id INTEGER REFERENCES guilds(guild_id) ON DELETE CASCADE
        )
    """)
    await db_conn.execute("CREATE INDEX IF NOT EXISTS idx_channels_guild ON channels(guild_id)")
    
    await db_conn.execute("""
        CREATE TABLE IF NOT EXISTS message_logs (
            message_id INTEGER PRIMARY KEY,
            created_at REAL NOT NULL,
            token_count INTEGER NOT NULL DEFAULT 0,
            mode TEXT NOT NULL CHECK (mode IN ('TALK','ASSISTANT'))
        )
    """)
    await db_conn.execute("CREATE INDEX IF NOT EXISTS idx_message_logs_created ON message_logs(created_at)")
    
    await db_conn.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_message_logs_limit
        AFTER INSERT ON message_logs
        BEGIN
            DELETE FROM message_logs
            WHERE message_id IN (
                SELECT message_id FROM message_logs
                ORDER BY created_at ASC, message_id ASC
                LIMIT MAX((SELECT COUNT(*) FROM message_logs) - 10000, 0)
            );
        END;
    """)
    await db_conn.commit()

# クールダウンと回数制限判定と加算
async def check_and_count(user_id, user_name):
    global period_request_count
    current_time = time.time()
    
    async with db_conn.execute("BEGIN IMMEDIATE"):
        try:
            async with db_conn.execute("SELECT last_request_time, window_start_time, request_count FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
            
            if row is None:
                last_request_time = 0
                window_start_time = current_time
                request_count = 0
            else:
                last_request_time, window_start_time, request_count = row
                
            # クールダウン判定
            time_passed = current_time - last_request_time
            if time_passed < COOLDOWN_SECONDS:
                await db_conn.execute("ROLLBACK")
                return "COOLDOWN", int(COOLDOWN_SECONDS - time_passed)
                
            # ウィンドウ判定
            if current_time - window_start_time >= 7200:
                window_start_time = current_time
                request_count = 0
                
            # 回数制限判定
            limit_count = MAX_REQUESTS_PER_2H_BOT if user_id in DISCORDSRV_BOT_ID else MAX_REQUESTS_PER_2H
            if request_count >= limit_count:
                await db_conn.execute("ROLLBACK")
                return "LIMIT", None
                
            # 加算処理
            request_count += 1
            
            # ユーザー更新
            await db_conn.execute("""
                INSERT INTO users (user_id, user_name, last_request_time, window_start_time, request_count)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    user_name = excluded.user_name,
                    last_request_time = excluded.last_request_time,
                    window_start_time = excluded.window_start_time,
                    request_count = excluded.request_count
            """, (user_id, user_name, current_time, window_start_time, request_count))
            
            # 全体統計更新
            await db_conn.execute("UPDATE global_stats SET total_request_count = total_request_count + 1 WHERE id = 1")
            
            await db_conn.execute("COMMIT")
            
            period_request_count += 1
            return "OK", None
        except Exception as e:
            await db_conn.execute("ROLLBACK")
            logger.error(f"DB check_and_count error: {e}")
            return "ERROR", None

# トークン加算
async def add_global_tokens(token_count):
    global period_token_count
    if token_count <= 0:
        return
    try:
        await db_conn.execute("BEGIN IMMEDIATE")
        await db_conn.execute("UPDATE global_stats SET total_token_count = total_token_count + ? WHERE id = 1", (token_count,))
        await db_conn.commit()
        period_token_count += token_count
    except Exception as e:
        await db_conn.rollback()
        logger.error(f"データベース add_global_tokens エラー: {e}")

# ログ記録
async def log_message(message_id, created_at, token_count, mode):
    try:
        await db_conn.execute("BEGIN IMMEDIATE")
        await db_conn.execute("""
            INSERT OR REPLACE INTO message_logs (message_id, created_at, token_count, mode)
            VALUES (?, ?, ?, ?)
        """, (message_id, created_at, token_count, mode))
        await db_conn.commit()
    except Exception as e:
        await db_conn.rollback()
        logger.error(f"データベース log_message エラー: {e}")

# プライマリクライアントの初期化
primary_ai_client = AsyncOpenAI(
    api_key = PRIMARY_API_KEY,
    base_url = PRIMARY_BASE_URL,
)

# セカンダリクライアントの初期化
secondary_ai_client = AsyncOpenAI(
    api_key = SECONDARY_API_KEY,
    base_url = SECONDARY_BASE_URL,
)

# Discordボットの設定
intents = discord.Intents.default()
intents.message_content = True
discord_client = discord.Client(intents=intents, max_messages=MAX_MESSAGES)
tree = app_commands.CommandTree(discord_client)

# スラッシュヘルプ情報
@tree.command(name="help", description="Maiのヘルプ情報を表示します")
async def help_command(interaction: discord.Interaction):
    if interaction.locale == discord.Locale.japanese:
        await interaction.response.send_message(HELP_INFORMATION, ephemeral=True, suppress_embeds=True)
    elif interaction.locale == discord.Locale.french:
        await interaction.response.send_message(HELP_INFORMATION_FR, ephemeral=True, suppress_embeds=True)
    elif interaction.locale == discord.Locale.german:
        await interaction.response.send_message(HELP_INFORMATION_DE, ephemeral=True, suppress_embeds=True)
    elif interaction.locale == discord.Locale.korean:
        await interaction.response.send_message(HELP_INFORMATION_KO, ephemeral=True, suppress_embeds=True)
    elif interaction.locale in [discord.Locale.taiwan_chinese, discord.Locale.chinese]:
        await interaction.response.send_message(HELP_INFORMATION_ZH, ephemeral=True, suppress_embeds=True)
    else:
        await interaction.response.send_message(HELP_INFORMATION_EN, ephemeral=True, suppress_embeds=True)

@discord_client.event
async def on_ready():
    logger.info(f'{discord_client.user} logged in.')

@discord_client.event
async def on_message(message):
    # Bot無視判定
    if message.author.bot and message.author.id not in DISCORDSRV_BOT_ID:
        return

    # 特定ユーザー返信判定
    if not ENABLE_CHANNEL_REPLY:
        if message.author.id not in DISCORDSRV_BOT_ID:
            return
    else:
        # チャンネル返信判定
        if DISCORDSRV_CHANNEL_ID and message.channel.id not in DISCORDSRV_CHANNEL_ID:
            return

    # メンションとリプライ判定
    is_mentioned = ENABLE_MENTION_REPLY and (discord_client.user in message.mentions)
    is_reply_to_bot = False
    
    if message.reference and message.reference.message_id:
        try:
            ref_msg = message.reference.cached_message or await message.channel.fetch_message(message.reference.message_id)
            if ref_msg.author == discord_client.user:
                is_reply_to_bot = True
        except Exception:
            pass

    # プレフィックス判定
    is_prefix = ENABLE_PREFIX_REPLY and message.content.startswith((PREFIX_TALK, PREFIX_ASSIS))

    # DiscordSRVプレフィックス判定
    is_discordsrv = ENABLE_DISCORDSRV_REPLY and (DISCORDSRV_PREFIX_TALK in message.content or DISCORDSRV_PREFIX_ASSIS in message.content)

    if not (is_mentioned or is_reply_to_bot or is_prefix or is_discordsrv):
        return

    # ボット返信スイッチチェック
    if not ENABLE_BOT_PROCESS:
        return

    user_id = message.author.id
    
    prompt = message.content.replace(f'<@{discord_client.user.id}>', '').strip()
    
    prefix_mode = None
    discordsrv_user = None

    # プレフィックスによるモード判定
    if ENABLE_PREFIX_REPLY and prompt.startswith(PREFIX_TALK):
        prefix_mode = "TALK"
        prompt = prompt[len(PREFIX_TALK):].strip()
    elif ENABLE_PREFIX_REPLY and prompt.startswith(PREFIX_ASSIS):
        prefix_mode = "ASSISTANT"
        prompt = prompt[len(PREFIX_ASSIS):].strip()
    # DiscordSRVプレフィックス判定
    elif ENABLE_DISCORDSRV_REPLY and DISCORDSRV_PREFIX_TALK in prompt:
        prefix_mode = "TALK"
        parts = prompt.split(DISCORDSRV_PREFIX_TALK, 1)
        discordsrv_user = parts[0].strip()
        prompt = parts[1].strip()
    elif ENABLE_DISCORDSRV_REPLY and DISCORDSRV_PREFIX_ASSIS in prompt:
        prefix_mode = "ASSISTANT"
        parts = prompt.split(DISCORDSRV_PREFIX_ASSIS, 1)
        prompt = parts[1].strip()

    # ユーザーメッセージ文字数制限適用
    prompt = prompt[:PROMPT_LENGTH_LIMIT]

    # データベースによるモード継続
    if prefix_mode is None and message.reference and message.reference.message_id:
        try:
            async with db_conn.execute("SELECT mode FROM message_logs WHERE message_id = ?", (message.reference.message_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    db_mode = row[0]
                    if db_mode in ("TALK", "ASSISTANT"):
                        prefix_mode = db_mode
        except Exception as e:
            logger.error(f"データベース モード継続 エラー: {e}")

    # 空メッセージ判定
    if not prompt or not any(c.isalnum() for c in prompt):
        await message.reply(HELP_INFORMATION, delete_after=20.0, allowed_mentions=MENTION_RESTRICTION, suppress_embeds=True)
        return

    # 無視判定
    if prompt.startswith(','):
        return

    # モード判定
    current_mode = "TALK"
    
    if prefix_mode:
        current_mode = prefix_mode
    elif prompt:
        if prompt.startswith(PREFIX_TALK):
            current_mode = "TALK"
        elif prompt.startswith(PREFIX_ASSIS):
            current_mode = "ASSISTANT"
        elif re.match(r'^\.\.debug', prompt):
            current_mode = "DEBUG"
    else:
        current_mode = "TALK"

    # デバッグモード処理
    if current_mode == "DEBUG":
        if message.author.id != MASTER_USER_ID:
            return
        await message.reply(DEBUG_INFORMATION, allowed_mentions=MENTION_RESTRICTION)
        return

    # クールダウンと回数制限のチェックと加算
    status, remaining_time = await check_and_count(user_id, message.author.display_name)
    if status == "COOLDOWN":
        await message.reply(f"クールダウン中 (残り {remaining_time} 秒)", delete_after=remaining_time)
        return
    elif status == "LIMIT":
        await message.reply("リクエスト制限 (e201)", delete_after=20.0)
        return
    elif status == "ERROR":
        return

    # リクエスト処理
    async with message.channel.typing():
        try:
            # トークモード
            if current_mode == "TALK":
                system_content = SYSTEM_PROMPT_TALK
                history_limit = HISTORY_LIMIT_TALK
                current_temperature = TEMPERATURE_TALK
                current_primary_model = PRIMARY_MODEL_TALK
                current_secondary_model = SECONDARY_MODEL_TALK
                
            # アシスタントモード
            elif current_mode == "ASSISTANT":
                system_content = SYSTEM_PROMPT_ASSIS
                history_limit = HISTORY_LIMIT_ASSIS
                current_temperature = TEMPERATURE_ASSIS
                current_primary_model = PRIMARY_MODEL_ASSIS
                current_secondary_model = SECONDARY_MODEL_ASSIS

            # ペイロード初期化
            messages_payload = [
                {"role": "system", "content": system_content}
            ]
            
            history = []
            current_msg = message
            limit = history_limit
            
            # 文脈構築
            current_history_chars = 0
            while current_msg.reference and current_msg.reference.message_id and limit > 0:
                try:
                    ref_msg = current_msg.reference.cached_message or await message.channel.fetch_message(current_msg.reference.message_id)
                    
                    role = "assistant" if ref_msg.author == discord_client.user else "user"
                    clean_content = ref_msg.content.replace(f'<@{discord_client.user.id}>', '').strip()
                    
                    if current_history_chars + len(clean_content) >= HISTORY_LENGTH_LIMIT:
                        break
                    current_history_chars += len(clean_content)

                    if current_mode == "TALK" and role == "user":
                        clean_content = f"(User Name:{ref_msg.author.display_name}) {clean_content}"

                    if clean_content:
                        history.append({
                            "role": role, 
                            "content": clean_content
                        })
                        
                    current_msg = ref_msg
                    limit -= 1
                except Exception as e:
                    logger.info(f"履歴取得エラー (e401): {e}")
                    break
            
            # 履歴処理
            for h in reversed(history):
                messages_payload.append({"role": h["role"], "content": h["content"]})
                
            # メッセージ処理
            if current_mode == "TALK":
                if discordsrv_user:
                    prompt = f"(User Name:{discordsrv_user}) {prompt}"
                else:
                    prompt = f"(User Name:{message.author.display_name}) {prompt}"

            messages_payload.append({"role": "user", "content": prompt})

            if ENABLE_PAYLOAD_LOGGING:
                logger.info(f"API Payload ({current_mode}): {messages_payload}")

            # リクエスト送信
            try:
                response = await asyncio.wait_for(
                    primary_ai_client.chat.completions.create(
                        model = current_primary_model,
                        messages = messages_payload,
                        max_tokens = MAX_TOKENS,
                        temperature = current_temperature,
                    ),
                    timeout=REQUEST_TIMEOUT
                )
            except Exception as e:
                logger.error(f"プライマリAPIエラー (e501): {e}")
                response = await asyncio.wait_for(
                    secondary_ai_client.chat.completions.create(
                        model = current_secondary_model,
                        messages = messages_payload,
                        max_tokens = MAX_TOKENS,
                        temperature = current_temperature,
                    ),
                    timeout=REQUEST_TIMEOUT
                )
            
            # 統計カウント
            used_tokens = response.usage.total_tokens if response.usage else 0
            await add_global_tokens(used_tokens)
            
            reply_text = response.choices[0].message.content
            
            # 分割送信
            if len(reply_text) > 2000:
                target_message = message
                is_first = True
                for i in range(0, len(reply_text), 2000):
                    target_message = await target_message.reply(reply_text[i:i+2000], allowed_mentions=MENTION_RESTRICTION)
                    tokens_to_log = used_tokens if is_first else 0
                    await log_message(target_message.id, target_message.created_at.timestamp(), tokens_to_log, current_mode)
                    is_first = False
            else:
                reply_msg = await message.reply(reply_text, allowed_mentions=MENTION_RESTRICTION)
                await log_message(reply_msg.id, reply_msg.created_at.timestamp(), used_tokens, current_mode)
                
        except Exception as e:
            logger.error(f"リクエストエラー (e502): {e}")
            await message.reply("リクエストエラー (e502)", delete_after=20.0)

# 統計表示タスク
async def print_stats_loop():
    await discord_client.wait_until_ready()
    while not discord_client.is_closed():
        await asyncio.sleep(300)
        
        global period_request_count, period_token_count
        
        current_reqs = period_request_count
        current_tokens = period_token_count
        period_request_count = 0
        period_token_count = 0
        
        logger.info(f"Requests (5min): {current_reqs}, Tokens used (5min): {current_tokens}")

# ローカライゼーション
class CommandTranslator(app_commands.Translator):
    async def translate(self, string: app_commands.locale_str, locale: discord.Locale, context: app_commands.TranslationContext) -> str | None:
        if locale in (discord.Locale.american_english, discord.Locale.british_english):
            if string.message == "Maiのヘルプ情報を表示します":
                return "Displays help information for Mai"

        elif locale == discord.Locale.french:
            if string.message == "Maiのヘルプ情報を表示します":
                return "Affiche les informations d'aide pour Mai"

        elif locale == discord.Locale.german:
            if string.message == "Maiのヘルプ情報を表示します":
                return "Zeigt Hilfeinformationen für Mai an"

        elif locale == discord.Locale.korean:
            if string.message == "Maiのヘルプ情報を表示します":
                return "Mai의 도움말 정보를 표시합니다"

        elif locale in (discord.Locale.taiwan_chinese, discord.Locale.chinese):
            if string.message == "Maiのヘルプ情報を表示します":
                return "顯示 Mai 的幫助資訊"

        return None

@discord_client.event
async def setup_hook():
    await init_db()
    await tree.set_translator(CommandTranslator())
    await tree.sync()
    discord_client.loop.create_task(print_stats_loop())

original_close = discord_client.close

async def close_client():
    global db_conn
    if db_conn:
        await db_conn.close()
        logger.info("データベース切断完了")
    await original_close()

discord_client.close = close_client

if __name__ == "__main__":
    discord_client.run(DISCORD_TOKEN)
