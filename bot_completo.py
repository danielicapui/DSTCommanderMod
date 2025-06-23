import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv
import datetime

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
# Se você quiser restringir comandos a um guild, pode usar GUILD_ID, mas para bot global não é obrigatório.
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", "1386342343036371016"))

# --------------------------------------------------
# Ajuste de diretório de trabalho: a pasta Master do servidor dedicado
# --------------------------------------------------
# Modifique este caminho conforme a localização exata do seu shard Master:
MASTER_FOLDER = r"C:\Users\danie\OneDrive\Documentos\Klei\DoNotStarveTogether\brasil_together_s\Master"
try:
    os.chdir(MASTER_FOLDER)
    print(f"[*] Diretório de trabalho alterado para: {MASTER_FOLDER}")
except Exception as e:
    print(f"[ERRO] Falha ao mudar cwd para Master: {e}")
    # Opcionalmente: exit(1)

# Configurações dos arquivos na pasta Master
COMMAND_FILE_PATH = "dst_command_queue.txt"      # bot → jogo
DISCORD_MSG_FILE   = "dst_server_to_discord.txt" # jogo → bot
DST_CHAT_LOG       = "server_chat_log.txt"      # se você usa leitura do chat log
LOG_FILE           = "bot_log.txt"

# IDs de canais do Discord
CHANNEL_IDS = [1386342343036371016, 1386465206296903944]  # canais onde o bot escuta mensagens para repassar ao jogo
CHANNEL_ID_TO_SEND = 1386342343036371016                 # canal onde o bot envia mensagens vindas do jogo

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

last_chat_pos = 0

def log(msg: str):
    ts = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{ts} {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def write_command(cmd: str) -> bool:
    """
    Acrescenta uma linha ao arquivo dst_command_queue.txt.
    O mod DST irá ler e limpar esse arquivo periodicamente.
    """
    try:
        # Como estamos em MASTER_FOLDER, COMMAND_FILE_PATH é somente o nome
        with open(COMMAND_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(cmd + "\n")
        log(f"→ Comando escrito: {cmd}")
        return True
    except Exception as e:
        log(f"[ERRO write_command] {e}")
        return False

@bot.event
async def on_ready():
    try:
        # Se quiser sincronizar comandos slash por guild: await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        await bot.tree.sync()  # ou por guild: bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        log(f"✅ Bot online como {bot.user} e comandos slash sincronizados")
    except Exception as e:
        log(f"[ERRO] Falha ao sincronizar comandos: {e}")
    ler_server_to_discord.start()
    escutar_chat_log.start()

@bot.event
async def on_message(message):
    # Evita ecoar bots
    if message.author.bot:
        return

    # Se estiver em um canal permitido e não for comando (não começa com prefixo):
    if message.channel.id in CHANNEL_IDS and not message.content.startswith(bot.command_prefix):
        texto = message.content.strip()
        if texto:
            # Envia mensagem do Discord para o jogo via TheNet:SystemMessage
            # O mod DST receberá essa linha e publicará no jogo
            cmd = f'TheNet:SystemMessage("[DISCORD] {message.author.display_name}: {texto}")'
            sucesso = write_command(cmd)
            if sucesso:
                await message.channel.send("✅ Mensagem enviada ao jogo!")
                log(f"Mensagem enviada ao jogo: {texto}")
            else:
                await message.channel.send("❌ Erro ao enviar mensagem.")
                log(f"Falha ao enviar mensagem: {texto}")

    await bot.process_commands(message)

# Comandos de texto
@bot.command()
async def rollback(ctx, dias: int = 1):
    if dias < 1:
        return await ctx.send("⚠️ Dias inválidos.")
    cmd = f"c_rollback({dias})"
    if write_command(cmd):
        await ctx.send(f"⏪ Mundo revertido {dias} dia(s).")
    else:
        await ctx.send("❌ Falha no rollback.")

@bot.command()
async def regenerate(ctx):
    cmd = "c_regenerateworld()"
    if write_command(cmd):
        await ctx.send("🌍 Mundo regenerado.")
    else:
        await ctx.send("❌ Falha ao regenerar.")

@bot.command()
async def revive(ctx, jogador: str = None):
    if not jogador:
        return await ctx.send("⚠️ Use `!revive <nome|todos>`.")
    cmd = "c_reviveallplayers()" if jogador.lower() == "todos" else f'c_reviveplayer("{jogador}")'
    if write_command(cmd):
        await ctx.send(f"❤️ Revive: {jogador}")
    else:
        await ctx.send("❌ Falha no revive.")

@bot.command()
async def kill(ctx, jogador: str = None):
    if not jogador:
        return await ctx.send("⚠️ Use `!kill <nome|todos>`.")
    cmd = "c_killallplayers()" if jogador.lower() == "todos" else f'c_killplayer("{jogador}")'
    if write_command(cmd):
        await ctx.send(f"☠️ Kill: {jogador}")
    else:
        await ctx.send("❌ Falha no kill.")

# Slash commands (global ou por guild)
@bot.tree.command(name="rollback", description="Reverter mundo X dias")
@app_commands.describe(dias="Quantidade de dias para rollback")
async def slash_rollback(interaction: discord.Interaction, dias: int):
    if dias < 1:
        return await interaction.response.send_message("⚠️ Dias inválidos.", ephemeral=True)
    cmd = f"c_rollback({dias})"
    sucesso = write_command(cmd)
    texto = f"⏪ Mundo revertido {dias} dia(s)." if sucesso else "❌ Falha no rollback."
    await interaction.response.send_message(texto, ephemeral=True)

@bot.tree.command(name="regenerate", description="Regenerar o mundo")
async def slash_regenerate(interaction: discord.Interaction):
    cmd = "c_regenerateworld()"
    sucesso = write_command(cmd)
    texto = "🌍 Mundo regenerado." if sucesso else "❌ Falha ao regenerar."
    await interaction.response.send_message(texto, ephemeral=True)

@bot.tree.command(name="revive", description="Reviver jogador ou todos")
@app_commands.describe(jogador="Nome do jogador ou todos")
async def slash_revive(interaction: discord.Interaction, jogador: str):
    cmd = "c_reviveallplayers()" if jogador.lower() == "todos" else f'c_reviveplayer("{jogador}")'
    sucesso = write_command(cmd)
    texto = f"❤️ Revive: {jogador}" if sucesso else "❌ Falha no revive."
    await interaction.response.send_message(texto, ephemeral=True)

@bot.tree.command(name="kill", description="Matar jogador ou todos")
@app_commands.describe(jogador="Nome do jogador ou todos")
async def slash_kill(interaction: discord.Interaction, jogador: str):
    cmd = "c_killallplayers()" if jogador.lower() == "todos" else f'c_killplayer("{jogador}")'
    sucesso = write_command(cmd)
    texto = f"☠️ Kill: {jogador}" if sucesso else "❌ Falha no kill."
    await interaction.response.send_message(texto, ephemeral=True)

# Tarefa periódica: ler mensagens que o mod escreveu em dst_server_to_discord.txt
@tasks.loop(seconds=5)
async def ler_server_to_discord():
    linhas = []
    if not os.path.exists(DISCORD_MSG_FILE):
        return log("⚠️ Arquivo de mensagens do jogo não encontrado.")
    try:
        with open(DISCORD_MSG_FILE, "r", encoding="utf-8") as f:
            linhas = [l.strip() for l in f if l.strip()]
        # Após ler, zera o arquivo
        open(DISCORD_MSG_FILE, "w", encoding="utf-8").close()
    except Exception as e:
        return log(f"[ERRO ler_server_to_discord] {e}")

    if linhas:
        canal = bot.get_channel(CHANNEL_ID_TO_SEND)
        if canal:
            for l in linhas:
                await canal.send(f"🎮 {l}")
                log(f"→ (DST → Discord): {l}")

# Tarefa opcional: ler chat log do DST, se desejar repassar chat do servidor
@tasks.loop(seconds=5)
async def escutar_chat_log():
    global last_chat_pos
    if not os.path.exists(DST_CHAT_LOG):
        return log("⚠️ Arquivo de chat DST não encontrado.")
    try:
        with open(DST_CHAT_LOG, "r", encoding="utf-8") as f:
            f.seek(last_chat_pos)
            novas = f.readlines()
            last_chat_pos = f.tell()
    except Exception as e:
        return log(f"[ERRO escutar_chat_log] {e}")

    canal = bot.get_channel(CHANNEL_ID_TO_SEND)
    if canal and novas:
        for l in novas:
            # Ajuste conforme o formato do seu server_chat_log.txt
            if "[Say]" in l and "[DISCORD]" not in l:
                partes = l.strip().split("]:", 1)
                if len(partes) != 2:
                    continue
                nome = partes[0].split("Say")[-1].strip(" []")
                texto = partes[1].strip()
                await canal.send(f"💬 **{nome}**: {texto}")
                log(f"→ (Chat DST → Discord): {nome}: {texto}")

@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

# Inicia o bot
bot.run(TOKEN)
