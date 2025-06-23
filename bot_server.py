import os
import re
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Carrega variáveis do .env
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
DISABLE_LOGS = os.getenv("DISABLE_LOGS", "false").lower() == "true"

DST_SERVER_EXE = os.getenv("DST_SERVER_EXE")
DST_SERVER_CWD = os.getenv("DST_SERVER_CWD")
DST_CLUSTER_NAME = os.getenv("DST_CLUSTER_NAME")
CHANNEL_IDS = [int(x) for x in os.getenv("CHANNEL_IDS", "").split(",") if x.strip()]
CHANNEL_ID_TO_SEND = int(os.getenv("CHANNEL_ID_TO_SEND", "0"))

if not all([TOKEN, DST_SERVER_EXE, DST_SERVER_CWD, DST_CLUSTER_NAME]):
    
    print("[ERRO] Verifique variáveis de ambiente obrigatórias.")
    exit(1)

# Configuração do bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

dst_process = None

async def read_server_stdout():
    global dst_process
    reader = dst_process.stdout
    while True:
        line = await reader.readline()
        if not line:
            break
        try:
            text = line.decode("utf-8", errors="ignore").strip()
        except:
            continue
        if not DISABLE_LOGS:
            print(f"[DST_LOG] {text}")

        if "[DISCORD]" in text:
            continue  # evita loop de mensagens

        # Captura mensagens formatadas pelo mod: [DST_CHAT][Shard] Nome: Mensagem
        match = re.search(r"\[DST_CHAT\]\[(.+?)] (.+?): (.+)", text)
        if match:
            shard, nome, msg = match.groups()
            canal = bot.get_channel(CHANNEL_ID_TO_SEND)
            if canal:
                await canal.send(f"💬 [{shard}] {nome}: {msg}")
            continue

        # Captura fallback caso o mod não funcione: [Say] (KU_xxxx) Nome: Mensagem
        match = re.search(r"\[Say\] \(\w+\) ([^:]+): (.+)", text)
        if match:
            nome, msg = match.groups()
            canal = bot.get_channel(CHANNEL_ID_TO_SEND)
            if canal:
                await canal.send(f"💬 {nome}: {msg}")
async def start_server():
    global dst_process
    shards = ["Master", "Caves"]
    for shard in shards:
        args = [
            DST_SERVER_EXE,
            "-cluster", DST_CLUSTER_NAME,
            "-shard", shard,
            "-console_enabled", "true"
        ]
        if not DISABLE_LOGS:
            print(f"[Iniciando {shard}] {args} em {DST_SERVER_CWD}")
        process = await asyncio.create_subprocess_exec(
            *args,
            cwd=DST_SERVER_CWD,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            stdin=asyncio.subprocess.PIPE
        )
        if shard == "Master":
            dst_process = process
            asyncio.create_task(read_server_stdout())
        await asyncio.sleep(3)

async def send_command_to_dst(cmd: str):
    global dst_process
    if dst_process is None or dst_process.stdin is None:
        if not DISABLE_LOGS: 
            print("[ERRO] Processo DST não iniciado ou stdin não disponível")
        return False
    try:
        dst_process.stdin.write((cmd + "\n").encode("utf-8"))
        await dst_process.stdin.drain()
        return True
    except Exception as e:
        print(f"[ERRO] Falha ao enviar comando: {e}")
        return False

@bot.event
async def on_ready():
    print(f"[Bot] Online como {bot.user}")
    await start_server()

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    ctx = await bot.get_context(message)

    # Se for um comando (!comando), só executa o comando
    if ctx.valid:
        await bot.process_commands(message)
        return

    # Se for uma mensagem comum em canal monitorado, envia ao jogo
    if message.channel.id in CHANNEL_IDS and message.channel.id != CHANNEL_ID_TO_SEND:
        texto = message.content.strip()
        if texto:
            cmd = f'TheNet:SystemMessage("[DISCORD] {message.author.display_name}: {texto}")'
            if await send_command_to_dst(cmd):
                await message.channel.send("✅ Enviado ao jogo.")
            else:
                await message.channel.send("❌ Falha ao enviar.")

# Comandos administrativos
@bot.command()
@commands.has_permissions(administrator=True)
async def regenerate(ctx):
    if await send_command_to_dst("c_regenerateworld()"):
        await ctx.send("🌍 Mundo regenerado.")
    else:
        await ctx.send("❌ Falha ao regenerar.")

@bot.command()
@commands.has_permissions(administrator=True)
async def rollback(ctx, dias: int = 1):
    if dias < 1:
        return await ctx.send("⚠️ Dias inválidos.")
    if await send_command_to_dst(f"c_rollback({dias})"):
        await ctx.send(f"⏪ Revertido {dias} dia(s).")
    else:
        await ctx.send("❌ Falha ao reverter.")

@bot.command()
@commands.has_permissions(administrator=True)
async def kill(ctx, *, jogador: str = None):
    if not jogador:
        return await ctx.send("Use `!kill <nome|todos>`")
    jogador = jogador.replace('"', '\\"')
    cmd = "c_killallplayers()" if jogador.lower() == "todos" else (
        f'for i,v in ipairs(AllPlayers) do '
        f'if v:GetDisplayName() == "{jogador}" then '
        f'v.components.health:Kill() end end'
    )
    if await send_command_to_dst(cmd):
        await ctx.send(f"☠️ Kill: {jogador}")
    else:
        await ctx.send("❌ Falha ao matar jogador.")

@bot.command()
@commands.has_permissions(administrator=True)
async def revive(ctx, *, jogador: str = None):
    if not jogador:
        return await ctx.send("Use `!revive <nome|todos>`")
    jogador = jogador.replace('"', '\\"')
    cmd = "c_reviveallplayers()" if jogador.lower() == "todos" else (
        f'for i,v in ipairs(AllPlayers) do '
        f'if v:GetDisplayName() == "{jogador}" then '
        f'v:PushEvent("respawnfromghost") end end'
    )
    if await send_command_to_dst(cmd):
        await ctx.send(f"❤️ Revive: {jogador}")
    else:
        await ctx.send("❌ Falha ao reviver jogador.")
@bot.command()
async def players(ctx):
    lua_code = (
        'local names={}\n'
        'for i, v in ipairs(AllPlayers) do\n'
        '   table.insert(names,v:GetDisplayName())\n'
        'end\n'
        'local msg="Jogadores online: ".. table.concat(names, ", ")\n'
        'TheNet:SystemMessage(msg)'
    )
    if await send_command_to_dst(lua_code):
        await ctx.send("👥 Solicitando lista de jogadores...")
    else:
        await ctx.send("❌ Não foi possível consultar os jogadores.")
bot.run(TOKEN)
