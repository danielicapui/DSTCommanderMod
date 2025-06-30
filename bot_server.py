import os
import re
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
import traceback
import getpass
from collections import deque
import hashlib
import json
# === Carrega variáveis do .env ===
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
DISABLE_LOGS = os.getenv("DISABLE_LOGS", "false").lower() == "true"

DST_SERVER_EXE = os.getenv("DST_SERVER_EXE")
DST_SERVER_CWD = os.getenv("DST_SERVER_CWD")
DST_CLUSTER_NAME = os.getenv("DST_CLUSTER_NAME")
CHANNEL_ID_TO_SEND = int(os.getenv("CHANNEL_ID_TO_SEND", "0"))

usuario = getpass.getuser()
# Primeiro tenta OneDrive, se não existir tenta o padrão "Documents"
base_paths = [
    f"C:/Users/{usuario}/OneDrive/Documentos/Klei/DoNotStarveTogether/{DST_CLUSTER_NAME}",
    f"C:/Users/{usuario}/Documents/Klei/DoNotStarveTogether/{DST_CLUSTER_NAME}",
]

for path in base_paths:
    if os.path.exists(path):
        CLUSTER_PATH = path
        break
else:
    print("[ERRO] Nenhum caminho válido para o cluster foi encontrado!")
    exit(1)

print(f"[DEBUG] Pasta usada para o cluster: {CLUSTER_PATH}")


if not all([TOKEN, DST_SERVER_EXE, DST_SERVER_CWD, DST_CLUSTER_NAME, CHANNEL_ID_TO_SEND]):
    print("[ERRO] Verifique variáveis de ambiente obrigatórias.")
    exit(1)

# === Setup Discord ===
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

dst_process_master = None
dst_processes = {}
confirma_envio_discord = False

async def manter_console_ativo(process, shard_name):
    """Envia ENTER periodicamente ao processo para manter o console ativo"""
    while True:
        try:
            if process.stdin:
                process.stdin.write(b"\n")
                await process.stdin.drain()
            await asyncio.sleep(15)  # pode ajustar para 5~30s se quiser
        except Exception as e:
            print(f"[WARN] Falha ao manter console ativo ({shard_name}): {e}")
            break


# Controle de mensagens para evitar repetição
mensagens_recentes = deque(maxlen=100)
mensagens_jogadores = set()
ultimo_texto_jogadores = None

async def safe_send(channel, msg):
    """Envia mensagem para canal Discord de forma segura, capturando erros."""
    try:
        await channel.send(msg)
    except Exception as e:
        print(f"[WARN] Falha ao enviar mensagem Discord: {e}")

async def read_server_stdout(process, shard_name):
    global ultimo_texto_jogadores
    reader = process.stdout
    while True:
        try:
            line = await reader.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="ignore").strip()

            if not DISABLE_LOGS:
                await asyncio.to_thread(print, f"[{shard_name}_LOG] {text}")

            if "[DISCORD]" in text:
                continue

            canal = bot.get_channel(CHANNEL_ID_TO_SEND)
            if not canal:
                continue

            # Jogadores online
            if 'Jogadores online:' in text:
                lista_jogadores = text.split("Jogadores online:", 1)[-1].strip()
                if lista_jogadores != ultimo_texto_jogadores:
                    ultimo_texto_jogadores = lista_jogadores
                    if lista_jogadores:
                        await safe_send(canal, f"\U0001F465 Jogadores online: {lista_jogadores}")
                    else:
                        await safe_send(canal, "\U0001F465 Nenhum jogador online.")
                continue

            # Chat DST
            if "[DST_CHAT]" in text:
                match = re.search(r"\[DST_CHAT]\[(.+?)] (.+?): (.+)", text)
                if match:
                    _, nome, msg = match.groups()
                    conteudo = f"DST_CHAT:{nome}:{msg}"
                    h = hashlib.sha1(conteudo.encode()).hexdigest()
                    if h not in mensagens_recentes:
                        mensagens_recentes.append(h)
                        await safe_send(canal, f"\U0001F4AC [{shard_name}] {nome}: {msg}")
                continue

            # Mensagens do sistema
            if 'TheNet:SystemMessage("' in text:
                match = re.search(r'TheNet:SystemMessage\("(.+?)"\)', text)
                if match:
                    conteudo = f"SYS:{match.group(1)}"
                    h = hashlib.sha1(conteudo.encode()).hexdigest()
                    if h not in mensagens_recentes:
                        mensagens_recentes.append(h)
                        await safe_send(canal, f"\U0001F4F2 {match.group(1)}")
                continue

            # [Say] - aceite qualquer nome de jogador
            if "[Say]" in text:
                match = re.search(r'\[Say\]\s+\(.+?\)\s+(.+?):\s+(.+)', text)
                if match:
                    nome, msg = match.groups()
                    conteudo = f"SAY:{nome}:{msg}"
                    h = hashlib.sha1(conteudo.encode()).hexdigest()
                    if h not in mensagens_recentes:
                        mensagens_recentes.append(h)
                        await safe_send(canal, f"\U0001F4AC [{shard_name}] {nome}: {msg}")
                continue

            # Anúncios
            if any(x in text for x in ["[Announcement]", "[ANNOUNCE]", "[Join Announcement]", "[Leave Announcement]", "[Announce]"]):
                match = re.search(r'\[.+?Announcement.*?\]\s*(.+)', text)
                if match:
                    conteudo = match.group(1).strip()
                    h = hashlib.sha1(("ANNOUNCE:" + conteudo).encode()).hexdigest()
                    if h not in mensagens_recentes:
                        mensagens_recentes.append(h)
                        await safe_send(canal, f"\U0001F4E2 {conteudo}")
                continue

            # Mudança de dia
            if "TheWorld:OnNewCycle()" in text or re.search(r"\[.*\]\s*Day\s+\d+", text):
                match = re.search(r"Day\s+(\d+)", text)
                if match:
                    dia = match.group(1)
                    h = hashlib.sha1(f"DIA:{dia}".encode()).hexdigest()
                    if h not in mensagens_recentes:
                        mensagens_recentes.append(h)
                        await safe_send(canal, f"\U0001F4C5 Novo dia no mundo: **Dia {dia}**")
                continue

            # Eventos críticos
            eventos_criticos = [
                ("Regenerating world", "\u267B\ufe0f O mundo está sendo regenerado!"),
                ("rolled back", "\u23EA O mundo foi revertido."),
                ("All players are dead", "\u2620\ufe0f Todos os jogadores morreram."),
                ("c_regenerateworld", "\U0001F501 Comando de regeneração foi usado.")
            ]
            for chave, mensagem in eventos_criticos:
                if chave in text:
                    h = hashlib.sha1(f"EVENTO:{mensagem}".encode()).hexdigest()
                    if h not in mensagens_recentes:
                        mensagens_recentes.append(h)
                        await safe_send(canal, mensagem)
                    break

            # Derrota de boss
            match_boss = re.search(r"(\w+) has been defeated", text)
            if match_boss:
                boss = match_boss.group(1)
                h = hashlib.sha1(f"BOSS:{boss}".encode()).hexdigest()
                if h not in mensagens_recentes:
                    mensagens_recentes.append(h)
                    await safe_send(canal, f"\U0001F451 **{boss}** foi derrotado!")
                continue

            # Mudança de estação
            if "TheWorld:PushEvent(\"seasontick\"" in text or "seasontick" in text:
                h = hashlib.sha1(f"SEASON:{text}".encode()).hexdigest()
                if h not in mensagens_recentes:
                    mensagens_recentes.append(h)
                    await safe_send(canal, "\U0001F4C6 Uma nova estação começou!")
                continue

            # Morte de jogador - corrigido unicode da caveira
            match_death = re.search(r'(.+?) was killed by (.+)', text)
            if match_death:
                player, killer = match_death.groups()
                h = hashlib.sha1(f"DEATH:{player}:{killer}".encode()).hexdigest()
                if h not in mensagens_recentes:
                    mensagens_recentes.append(h)
                    await safe_send(canal, f"\U0001F480 **{player}** foi morto por **{killer}**.")
                continue

        except Exception as e:
            print(f"[ERRO] Falha ao processar linha do servidor ({shard_name}): {e}")
            traceback.print_exc()

async def start_shard(shard, port, is_master):
    args = [
        DST_SERVER_EXE,
        "-cluster", DST_CLUSTER_NAME,
        "-shard", shard,
        "-console_enabled", "true"
    ]
    print(f"[Iniciando {shard}] Args: {args}")
    env = os.environ.copy()
    env["USERPROFILE"] = os.path.expanduser("~")
    env["HOME"] = os.path.expanduser("~")

    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=DST_SERVER_CWD,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        stdin=asyncio.subprocess.PIPE
    )

    dst_processes[shard] = process
    global dst_process_master
    if is_master:
        dst_process_master = process

    asyncio.create_task(read_server_stdout(process, shard))
    asyncio.create_task(manter_console_ativo(process, shard))


async def start_server():
    print("[Iniciando servidores DST...]")
    await start_shard("Master", 11000, True)
    await asyncio.sleep(15)
    await start_shard("Caves", 11002, False)

    await asyncio.sleep(15)

    canal = bot.get_channel(CHANNEL_ID_TO_SEND)
    if canal:
        await canal.send("🟢 O servidor Brasil Together SS está online!")
    else:
        print("[ERRO] Canal do Discord não encontrado para enviar mensagem de status.")

# async def send_command_to_dst(cmd: str):
#     if dst_process_master is None or dst_process_master.stdin is None:
#         print("[ERRO] Processo DST Master não iniciado ou stdin não disponível")
#         return False
#     try:
#         dst_process_master.stdin.write((cmd + "\n").encode("utf-8"))
#         await dst_process_master.stdin.drain()
#         return True
#     except Exception as e:
#         print(f"[ERRO] Falha ao enviar comando: {e}")
#         return False

async def send_command_to_all_shards(cmd: str):
    sucesso = False
    for shard, proc in dst_processes.items():
        if proc and proc.stdin:
            try:
                proc.stdin.write((cmd + "\n").encode("utf-8"))
                await proc.stdin.drain()
                sucesso = True
            except Exception as e:
                print(f"[ERRO] Falha ao enviar comando para {shard}: {e}")
    return sucesso

@bot.event
async def on_ready():
    print(f"[Bot] Online como {bot.user}")
    await start_server()

@bot.event
async def on_message(message):
    if message.author.bot or message.channel.id != CHANNEL_ID_TO_SEND:
        return

    texto = message.content.strip()
    if texto:
        texto_escapado = texto.replace('"', '\\"')
        nome_escapado = message.author.display_name.replace('"', '\\"')
        cmd = f'TheNet:SystemMessage("[DISCORD] {nome_escapado}: {texto_escapado}")'
        enviado = False
        if dst_process_master and dst_process_master.stdin:
            try:
                dst_process_master.stdin.write((cmd + "\n").encode("utf-8"))
                await dst_process_master.stdin.drain()
                enviado = True
            except Exception as e:
                print(f"[ERRO] Falha ao enviar mensagem Discord para shard Master: {e}")

        if confirma_envio_discord:
            await message.channel.send("✅ Enviado ao jogo." if enviado else "❌ Falha ao enviar.")

    await bot.process_commands(message)

@bot.command()
@commands.has_permissions(administrator=True)
async def confirmar(ctx, modo: str = None):
    global confirma_envio_discord
    if modo is None:
        status = "ativado ✅" if confirma_envio_discord else "desativado ❌"
        return await ctx.send(f"📣 Confirmação atual: {status}\nUse `!confirmar on` ou `!confirmar off`.")

    if modo.lower() == "on":
        confirma_envio_discord = True
        await ctx.send("✅ Confirmação de envio ativada.")
    elif modo.lower() == "off":
        confirma_envio_discord = False
        await ctx.send("❌ Confirmação de envio desativada.")
    else:
        await ctx.send("⚠️ Use `!confirmar on` ou `!confirmar off`.")

@bot.command()
async def players(ctx):
    lua_code = 'local names = {}; for i, v in ipairs(AllPlayers) do if v:GetDisplayName() and v.userid ~= "CHARLIE" then table.insert(names, v:GetDisplayName()) end end; TheNet:SystemMessage("Jogadores online: " .. table.concat(names, ","))'
    if await send_command_to_all_shards(lua_code):
        await ctx.send("👥 Consultando jogadores no servidor...")
    else:
        await ctx.send("❌ Não foi possível consultar os jogadores.")

@bot.command()
@commands.has_permissions(administrator=True)
async def regenerate(ctx):
    if await send_command_to_all_shards("c_regenerateworld()"):
        await ctx.send("🌍 Mundo regenerado.")
    else:
        await ctx.send("❌ Falha ao regenerar.")

@bot.command()
@commands.has_permissions(administrator=True)
async def rollback(ctx, dias: int = 1):
    if dias < 1:
        return await ctx.send("⚠️ Dias inválidos.")
    if await send_command_to_all_shards(f"c_rollback({dias})"):
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
        f'for i,v in ipairs(AllPlayers) do if v:GetDisplayName() == "{jogador}" then v.components.health:Kill() end end'
    )
    if await send_command_to_all_shards(cmd):
        await ctx.send(f"☠️ Kill: {jogador}")
    else:
        await ctx.send("❌ Falha ao matar jogador.")

@bot.command()
@commands.has_permissions(administrator=True)
async def fogueira(ctx, *, jogador: str = None):
    if not jogador:
        return await ctx.send("Use `!revive <nome|todos>`")
    jogador = jogador.replace('"', '\\"')
    cmd = "c_reviveallplayers()" if jogador.lower() == "todos" else (
        f'for i,v in ipairs(AllPlayers) do if v:GetDisplayName() == "{jogador}" then v:PushEvent("respawnfromghost") end end'
    )
    if await send_command_to_all_shards(cmd):
        await ctx.send(f"❤️ Revive: {jogador}")
    else:
        await ctx.send("❌ Falha ao reviver jogador.")

@bot.command(name="lua")
@commands.has_permissions(administrator=True)
async def lua(ctx, *, codigo: str = None):
    if not codigo:
        return await ctx.send("❌ Use `!lua <código Lua>`")

    import re
    # Remove markdown code blocks, se houver
    codigo = re.sub(r"^```lua\s*", "", codigo, flags=re.I)
    codigo = re.sub(r"```$", "", codigo)

    # Monta o código para enviar (com indentação simples)
    comando = f"""
TheWorld:DoTaskInTime(0, function()
{codigo}
end)
""".strip()

    sucesso = await send_command_to_all_shards(comando)

    if sucesso:
        await ctx.send("✅ Código Lua enviado com sucesso ao servidor.")
    else:
        await ctx.send("❌ Falha ao enviar o código Lua.")

@bot.command()
@commands.has_permissions(administrator=True)
async def love(ctx, alvo: str = None, valor: int = 0):
    if not alvo or valor <= 0:
        return await ctx.send("❌ Uso: `!love <nome/id/discord_id> <quantidade>`")

    bountydata_path = os.path.join(CLUSTER_PATH, "Master", "bountydata")
    if not os.path.exists(bountydata_path):
        return await ctx.send("❌ Pasta 'bountydata' não encontrada.")

    aplicou = False
    for file in os.listdir(bountydata_path):
        if file.endswith("_bounty"):
            path = os.path.join(bountydata_path, file)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                nome_arquivo = os.path.basename(file).split("_")[0]
                discord_id = str(data.get("discord_id", ""))
                userid = nome_arquivo

                if alvo.lower() in [nome_arquivo.lower(), userid, discord_id]:
                    data["love"] = data.get("love", 0) + valor
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=4)

                    await ctx.send(
                        f"💖 LOVE adicionado com sucesso!\n"
                        f"Jogador: `{nome_arquivo}`\n"
                        f"+{valor} LOVE (Total: {data['love']})"
                    )
                    aplicou = True
                    break
            except Exception as e:
                print(f"[ERRO] Ao processar {path}: {e}")

    if not aplicou:
        await ctx.send(f"⚠️ Nenhum jogador encontrado com nome/ID: `{alvo}`.")

@bot.command()
async def verificar(ctx, discordid: str):
    bountydata_path = os.path.join(CLUSTER_PATH, "Master", "bountydata")
    achou = False
    for file in os.listdir(bountydata_path):
        if file.endswith("_bounty"):
            path = os.path.join(bountydata_path, file)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if str(data.get("discord_id", "")) == discordid:
                await ctx.send(f"✅ O Discord ID `{discordid}` está vinculado ao jogador `{file.split('_')[0]}`.")
                achou = True
                break
    if not achou:
        await ctx.send(f"❌ Discord ID `{discordid}` não encontrado.")

bot.run(TOKEN)