import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import nest_asyncio

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ONLINE")
    def log_message(self, format, *args):
        pass

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), SimpleHandler).serve_forever()
import os
import sys
import threading
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- 1. DEFINIÇÃO DO SERVIDOR HTTP PARA O RENDER ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"SHERIFF BOT ONLINE")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def start_health_check_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# --- 2. INICIA O SERVIDOR HTTP ---
threading.Thread(target=start_health_check_server, daemon=True).start()

# ==========================================
# 📦 SISTEMA DE AUTO-INSTALAÇÃO DE MÓDULOS
# ==========================================
def instalar_modulo(package, pip_name=None):
    if pip_name is None:
        pip_name = package
    try:
        __import__(package)
    except ImportError:
        print(f"🔄 O módulo '{package}' não está instalado. Instalando '{pip_name}' automaticamente...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
            print(f"✅ '{pip_name}' instalado com sucesso!")
        except Exception as e:
            print(f"❌ Erro ao instalar via pip: {str(e)}")

import asyncio
import re
import time
import json
import socket
import nest_asyncio
import aiohttp
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qs
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatMemberStatus
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, ConversationHandler, filters
)
)

# ==========================================
# ⚙️ CONFIGURAÇÃO DO BOT E CONTROLE PRIVADO
# ==========================================
TOKEN = "8621320390:AAEgD-r9t1rMaUOowioEStdhGeiofHrFA-M"
ARQUIVO_BANCO = "lista_dns.txt"
GRUPO_FILE = "grupo.txt"

# 🔗 Link Raw do GitHub configurado corretamente
LINK_LISTA_FIXA = "https://raw.githubusercontent.com/odirleisouzasantos-hue/fantastic-octo-fortnight/main/lista.txt.txt"

ADMIN_IDS = [7033928987,1522809429]
GET_M3U_LINK = 0

DNS_BLACKLIST = [
    "brothersplay.com",
    "www.brothersplay.com"
]

# 🚫 Blacklist de domínios curingas/genéricos que respondem falso positivo
DOMINIOS_CURINGAS = [
    "adultiptv.net",
    "iptvxxx.net",
    "dimaiptv.com"
]

HEADERS = {
    "User-Agent": "VLC",
    "X-User-Agent": "Model: MAG254; Link: Ethernet",
}

consultas_ativas = {}
user_timeout_tasks = {}

# ==========================================
# 💾 PERSISTÊNCIA DE CONFIGURAÇÃO DO GRUPO
# ==========================================
def salvar_grupo_id(chat_id, thread_id=None):
    with open(GRUPO_FILE, "w", encoding="utf-8") as f:
        f.write(f"{chat_id}:{thread_id or ''}")

def obter_grupo_id():
    if os.path.exists(GRUPO_FILE):
        with open(GRUPO_FILE, "r", encoding="utf-8") as f:
            dados = f.read().strip().split(":")
            return int(dados[0]), int(dados[1]) if len(dados) > 1 and dados[1] else None
    return None, None

# ==========================================
# 🔐 SISTEMA DE PERMISSÕES
# ==========================================
async def check_autorizacao(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    user = update.effective_user
    grupo_aut, thread_aut = obter_grupo_id()

    if chat.type in ["group", "supergroup"]:
        if chat.id != grupo_aut: return False
        message_obj = update.message or (update.callback_query.message if update.callback_query else None)
        thread_id = getattr(message_obj, "message_thread_id", None)
        if thread_aut and thread_aut != thread_id: return False
        return True

    if chat.type == "private":
        if user.id in ADMIN_IDS: return True
        try:
            membro = await context.bot.get_chat_member(chat.id, user.id)
            if membro.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]: return True
        except: pass
        return False
    return False

# ==========================================
# 🔄 MOTOR DE SINCRONIZAÇÃO HÍBRIDO (GITHUB + LOCAL)
# ==========================================
async def baixar_lista_automatica(forçar=False):
    if LINK_LISTA_FIXA and "COLE_O_LINK" not in LINK_LISTA_FIXA:
        print("🔄 Baixando banco de dados limpo do servidor remoto (GitHub)...")
        try:
            headers_github = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            async with aiohttp.ClientSession() as session:
                async with session.get(LINK_LISTA_FIXA, headers=headers_github, timeout=15) as response:
                    if response.status == 200:
                        conteudo = await response.text()
                        with open(ARQUIVO_BANCO, "w", encoding="utf-8", errors="ignore") as f:
                            f.write(conteudo)

                        total_extraido = len(extrair_hosts(conteudo))
                        print(f"✅ Banco de dados sincronizado com sucesso! Total: {total_extraido}")
                        return True
        except Exception as e:
            print(f"❌ Falha ao baixar lista remota do GitHub: {str(e)}")

    if os.path.exists(ARQUIVO_BANCO):
        with open(ARQUIVO_BANCO, "r", encoding="utf-8", errors="ignore") as f:
            total_local = len(extrair_hosts(f.read()))
        print(f"🔄 Usando banco de dados local da pasta (`{ARQUIVO_BANCO}`). Total: {total_local}")
        return True
    else:
        print(f"❌ Erro crítico: Nenhum banco de dados local ou remoto encontrado.")
        with open(ARQUIVO_BANCO, "w", encoding="utf-8") as f:
            f.write("")
        return False

def extrair_hosts(texto):
    try:
        linhas = texto.split('\n')
        hosts = []
        for line in linhas:
            linha_limpa = line.replace(",", " ").strip()
            host = re.sub(r'https?://', '', linha_limpa).split('/')[0].split('?')[0].strip().lower()
            if ":" in host: host = host.split(":")[0]
            if "." in host and len(host) > 4:
                if host not in DNS_BLACKLIST and not any(curinga in host for curinga in DOMINIOS_CURINGAS):
                    hosts.append(host)
        return list(set(hosts))
    except:
        return []

# ==========================================
# ⚡ MOTOR DE EXTRAÇÃO E CHECAGEM COM PING (V15.5)
# ==========================================
async def testar_url_completo(session, url_banco, user, password):
    url_base = f"http://{url_banco}/player_api.php?username={user}&password={password}"
    timeout_config = aiohttp.ClientTimeout(total=3.5)
    t_inicio = time.time()
    try:
        async with session.get(url_base, headers=HEADERS, timeout=timeout_config) as response:
            t_fim = time.time()
            ping_ms = round((t_fim - t_inicio) * 1000)

            if response.status not in [200, 301, 302, 403, 406, 429, 503]:
                return {"dns": url_banco, "valido": False, "tv": 0, "ping": 9999}

            texto_resposta = await response.text()
            is_valid = False
            active_cons, max_cons, exp_date = "N/A", "N/A", "N/A"
            total_tv = 0

            try:
                dados_json = json.loads(texto_resposta)
                if "user_info" in dados_json:
                    info = dados_json["user_info"]
                    status_val = str(info.get("status", "")).strip().lower()
                    
                    if status_val in ["active", "1", "true", "ativado", "on"]:
                        is_valid = True
                        active_cons = info.get("active_connections", "0")
                        max_cons = info.get("max_connections", "0")
                        timestamp = info.get("exp_date")
                        if timestamp and str(timestamp).isdigit():
                            exp_date = datetime.fromtimestamp(int(timestamp)).strftime("%d/%m/%Y")
            except:
                texto_lower = texto_resposta.lower()
                if 'username' in texto_lower and ('"active"' in texto_lower or '"status": 1' in texto_lower or 'active' in texto_lower):
                    is_valid = True

            if is_valid:
                try:
                    dados_json = json.loads(texto_resposta)
                    if "categories" in dados_json:
                        cats = dados_json["categories"]
                        total_tv = len(cats.get("live", [])) if isinstance(cats.get("live"), list) else int(cats.get("live", 0))
                except:
                    pass

                try:
                    dados_json = json.loads(texto_resposta)
                    if total_tv == 0 and "live_count" in dados_json: total_tv = int(dados_json.get("live_count", 0))
                except:
                    pass

                if total_tv == 0:
                    url_cats = f"{url_base}&action=get_live_categories"
                    try:
                        async with session.get(url_cats, headers=HEADERS, timeout=timeout_config) as res_cats:
                            if res_cats.status in [200, 301, 302, 403]:
                                texto_cats = await res_cats.text()
                                if "[" in texto_cats and "category_id" in texto_cats:
                                    dados_cats = json.loads(texto_cats)
                                    total_tv = len(dados_cats) if isinstance(dados_cats, list) else 28
                    except:
                        pass

            return {
                "dns": url_banco, "valido": is_valid,
                "conexoes_ativas": active_cons, "conexoes_maximas": max_cons, "vencimento": exp_date,
                "tv": total_tv, "ping": ping_ms
            }
    except:
        return {"dns": url_banco, "valido": False, "tv": 0, "ping": 9999}

# ==========================================
# 📊 AUXILIARES DE FORMATAÇÃO E LAYOUT
# ==========================================
def gerar_barra_progresso(atual, total, tamanho=10):
    porcentagem = (atual / total) * 100 if total > 0 else 0
    preenchido = int(tamanho * (atual / total)) if total > 0 else 0
    vazio = tamanho - preenchido
    barra = "▓" * preenchido + "░" * vazio
    return barra, porcentagem

# ==========================================
# 🤠 PROCESSAMENTO HÍBRIDO E MONTAGEM DA V15.5
# ==========================================
async def processar_sheriff_hibrido(dados_entrada, user_id, context, chat_id):
    inicio = time.time()
    agora_br = datetime.now(timezone.utc) - timedelta(hours=3)
    dt_hr = agora_br.strftime("%d/%m/%Y | %H:%M:%S")
    _, thread_id = obter_grupo_id()

    if not os.path.exists(ARQUIVO_BANCO):
        sucesso = await baixar_lista_automatica(forçar=True)
        if not (sucesso or os.path.exists(ARQUIVO_BANCO)):
            await context.bot.send_message(chat_id=chat_id, text="❌ ERR: O banco de dados de servidores está inacessível.", message_thread_id=thread_id)
            return

    with open(ARQUIVO_BANCO, "r", encoding="utf-8", errors="ignore") as f:
        conteudo_txt = f.read()
    todas_dns_txt = extrair_hosts(conteudo_txt)
    total_banco = len(todas_dns_txt)

    is_link_completo = "username=" in dados_entrada and "password=" in dados_entrada
    
    espelhos_de_ouro = []
    status_dns_alvo = "OFF"
    dados_conta = {"user": "N/A", "pass": "N/A", "ativas": "N/A", "max": "N/A", "vence": "N/A"}
    dados_rede = {"ip": "N/A", "isp": "N/A", "pais": "N/A"}

    if is_link_completo:
        try: dns_alvo = urlparse(dados_entrada).hostname.lower()
        except: dns_alvo = "N/A"
    else:
        dns_alvo = dados_entrada.strip().split('\n')[0]
        dns_alvo = re.sub(r'https?://', '', dns_alvo).split('/')[0].split('?')[0].strip().lower()
        if ":" in dns_alvo: dns_alvo = dns_alvo.split(":")[0]

    try:
        dados_rede["ip"] = socket.gethostbyname(dns_alvo)
        async with aiohttp.ClientSession() as session_geo:
            async with session_geo.get(f"http://ip-api.com/json/{dados_rede['ip']}?fields=isp,country", timeout=2.0) as res_geo:
                if res_geo.status == 200:
                    geo_json = await res_geo.json()
                    dados_rede["isp"] = geo_json.get("isp", "N/A")
                    dados_rede["pais"] = geo_json.get("country", "N/A")
    except:
        pass

    if is_link_completo:
        consultas_ativas[chat_id] = True
        try:
            parsed_url = urlparse(dados_entrada)
            query_params = parse_qs(parsed_url.query)
            usuario = query_params['username'][0]
            senha = query_params['password'][0]
        except:
            await context.bot.send_message(chat_id=chat_id, text="❌ Falha ao quebrar parâmetros da URL M3U.", message_thread_id=thread_id)
            return

        dados_conta["user"] = usuario
        dados_conta["pass"] = senha

        botao_parar = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 PARAR CONSULTA", callback_data="stop_scan")]])
        
        barra_init, pct_init = gerar_barra_progresso(0, total_banco)
       progresso_msg = await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"🤠 *SHERIFF DETECTOR — SCAN EM CURSO...*\n"
                f"──────────────────────────────────\n"
                f"📊 *Status:* `[{barra_init}] {pct_init:.1f}%`\n"
                f"🔍 *Verificados:* `0 / {total_banco:,}`\n".replace(',', '.') +
                f"🎯 *Confirmados:* `0`\n"
                f"──────────────────────────────────\n"
                f"⚡ _Procurando por mídias e instabilidades..._"
            ),
            parse_mode='Markdown',
            reply_markup=botao_parar,
            message_thread_id=thread_id
        )

        verificados = 0
        confirmados = 0
        
        url_base = f"http://{dns_alvo}/get.php?username={usuario}&password={senha}"
        
        for i, url_candidata in enumerate(todas_dns_txt):
            if chat_id in consultas_ativas and not consultas_ativas[chat_id]:
                break 

            try:
                verificados += 1
                
                if verificados % 300 == 0 or verificados == total_banco:
                    barra, pct = gerar_barra_progresso(verificados, total_banco)
                    try:
                        await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=progresso_msg.message_id,
                            text=(
                                f"🤠 *SHERIFF DETECTOR — SCAN EM CURSO...*\n"
                                f"──────────────────────────────────\n"
                                f"📊 *Status:* `[{barra}] {pct:.1f}%`\n"
                                f"🔍 *Verificados:* `{verificados:,} / {total_banco:,}`\n".replace(',', '.') +
                                f"🎯 *Confirmados:* `{confirmados}`\n"
                                f"──────────────────────────────────\n"
                                f"⚡ _Procurando por mídias e instabilidades..._"
                            ),
                            parse_mode='Markdown',
                            reply_markup=botao_parar
                        )
                    except:
                        pass 
            except Exception:
                verificados += 1
                continue
        connector = aiohttp.TCPConnector(limit=60, ttl_dns_cache=300)
        proxima_att = time.time() + 4.0
        servidores_processados = 0

        async with aiohttp.ClientSession(connector=connector) as session:
            teste_alvo = await testar_url_completo(session, dns_alvo, usuario, senha)
            status_dns_alvo = "ON" if teste_alvo["valido"] else "OFF"
            canais_alvo = teste_alvo["tv"]
            
            if teste_alvo["valido"]:
                dados_conta["ativas"] = teste_alvo["conexoes_ativas"]
                dados_conta["max"] = teste_alvo["conexoes_maximas"]
                dados_conta["vence"] = teste_alvo["vencimento"]

            lote_tamanho = 100
            for bloco_idx in range(0, total_banco, lote_tamanho):
                if not consultas_ativas.get(chat_id, True):
                    break

                lote_atual = todas_dns_txt[bloco_idx : bloco_idx + lote_tamanho]
                tarefas = [testar_url_completo(session, url, usuario, senha) for url in lote_atual]
                resultados = await asyncio.gather(*tarefas)
                servidores_processados += len(lote_atual)

                for res in resultados:
                    if res["valido"] and res["dns"] != dns_alvo:
                        if not any(curinga in res["dns"] for curinga in DOMINIOS_CURINGAS):
                            if res["tv"] > 5 and (canais_alvo == 0 or abs(res["tv"] - canais_alvo) <= 15 or res["tv"] >= 20):
                                if not any(e["dns"] == res["dns"] for e in espelhos_de_ouro):
                                    espelhos_de_ouro.append(res)
                                    
                                if status_dns_alvo == "OFF" and dados_conta["vence"] == "N/A" and res.get("vencimento", "N/A") != "N/A":
                                    dados_conta["ativas"] = res.get("conexoes_ativas", "N/A")
                                    dados_conta["max"] = res.get("conexoes_maximas", "N/A")
                                    dados_conta["vence"] = res.get("vencimento", "N/A")

                if time.time() >= proxima_att:
                    barra_loop, pct_loop = gerar_barra_progresso(servidores_processados, total_banco)
                    try:
                        await progresso_msg.edit_text(
                            f"🤠 *SHERIFF DETECTOR — SCAN EM CURSO...*\n"
                            f"──────────────────────────────────\n"
                            f"📊 *Status:* `[{barra_loop}] {pct_loop:.1f}%`\n"
                            f"🔍 *Verificados:* `{servidores_processados:,} / {total_banco:,}`\n".replace(',', '.') +
                            f"🎯 *Confirmados:* `{len(espelhos_de_ouro)}`\n"
                            f"──────────────────────────────────\n"
                            f"⚡ _Procurando por mídias e instabilidades..._",
                            parse_mode='Markdown',
                            reply_markup=botao_parar
                        )
                    except: pass
                    proxima_att = time.time() + 4.0

        try: await progresso_msg.delete()
            
        except: pass
        consultas_ativas.pop(chat_id, None)

        total_confirmados = len(espelhos_de_ouro)
        if status_dns_alvo == "OFF" and total_confirmados > 0:
            status_dns_alvo = "ON"

        latencia = round((time.time() - inicio), 2)
        indicador_status = "(🟢 ONLINE)" if status_dns_alvo == "ON" else "(🔴 OFFLINE)"

        # Ordena os espelhos encontrados por menor latência (Ping)
        espelhos_de_ouro.sort(key=lambda x: x["ping"])

        barra_fim, pct_fim = gerar_barra_progresso(servidores_processados, total_banco)

        relatorio = [
            "🤠 *SHERIFF DETECTOR V15.5 SMART FILTER*",
            "──────────────────────────────────",
            f"👤 *REQUISITANTE:* `{user_id}`",
            f"📅 *DATA/HORA:* `{dt_hr}`",
            f"📊 *STATUS:* `[{barra_fim}] {pct_fim:.1f}%` (`{servidores_processados:,}/{total_banco:,}`)".replace(',', '.'),
            "──────────────────────────────────",
            f"🌐 *DNS ALVO:* `{dns_alvo}` {indicador_status}",
            f"📡 *IP:* `{dados_rede['ip']}`",
            f"🏢 *ISP:* `{dados_rede['isp']}` | 🇨🇦 `{dados_rede['pais']}`",
            "──────────────────────────────────",
            f"🔑 *USUÁRIO:* `{dados_conta['user']}` | 🔒 *SENHA:* `{dados_conta['pass']}`",
            f"⏳ *VENCIMENTO:* `{dados_conta['vence']}`",
            f"📺 *TELA ONLINE:* `{dados_conta['ativas']}/{dados_conta['max']}` conexões",
            "──────────────────────────────────",
            f"⭐ *ESPELHOS DE OURO CONFIRMADOS ({total_confirmados}):*",
            "📌 _Ordenados por menor latência de resposta._",
            "──────────────────────────────────"
        ]

        if total_confirmados > 0:
            for item in espelhos_de_ouro[:40]:
                relatorio.append(f" ⚡ `{item['dns']}` — 🟢 *LIBERADA* (`⚡ {item['ping']}ms`)")
        else:
            relatorio.append(" ⚠️ _Nenhum espelho válido com canais ativos respondeu para este login._")

    else:
        status_dns_alvo = "OFF"
        connector_teste = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector_teste) as session_teste:
            try:
                async with session_teste.get(f"http://{dns_alvo}", headers=HEADERS, timeout=aiohttp.ClientTimeout(total=2.5)) as resp_teste:
                    if resp_teste.status in [200, 301, 302, 403, 406, 429, 503]:
                        status_dns_alvo = "ON"
            except:
                status_dns_alvo = "OFF"

        partes_alvo = dns_alvo.split('.')
        raiz_alvo = re.sub(r'\d+$', '', partes_alvo[0])

        lista_texto = []
        for dns_banco in todas_dns_txt:
            if dns_banco == dns_alvo or dns_banco in DNS_BLACKLIST: continue
            partes_banco = dns_banco.split('.')
            raiz_banco = re.sub(r'\d+$', '', partes_banco[0])
            if raiz_alvo == raiz_banco and len(raiz_alvo) >= 3:
                lista_texto.append(dns_banco)

        total_encontradas = len(lista_texto)
        latencia = round((time.time() - inicio), 2)
        indicador_status = "(🟢 ONLINE)" if status_dns_alvo == "ON" else "(🔴 OFFLINE)"

        relatorio = [
            "🤠 *SHERIFF DETECTOR V15.5 SMART FILTER*",
            "──────────────────────────────────",
            f"🌐 *DNS ALVO:* `{dns_alvo}` {indicador_status}",
            f"📡 *IP:* `{dados_rede['ip']}`",
            f"🏢 *ISP:* `{dados_rede['isp']}` | 🇨🇦 `{dados_rede['pais']}`",
            "──────────────────────────────────"
        ]

        if total_encontradas > 0:
            relatorio.append(f"📌 *PARALELAS POR PROXIMIDADE DE TEXTO ({total_encontradas}):*")
            for dns_item in lista_texto[:40]:
                relatorio.append(f" ⚡ `{dns_item}`")
        else:
            relatorio.append("⚠️ _Nenhuma similaridade de texto encontrada no banco para este prefixo._")

    relatorio.append("──────────────────────────────────")
    relatorio.append(f"⏱ *TEMPO DE VOO:* `{latencia}s` | 📊 *BANCO TOTAL:* `{total_banco:,}` sites".replace(',', '.'))

    texto_final = "\n".join(relatorio)
    await context.bot.send_message(chat_id=chat_id, text=texto_final, parse_mode='Markdown', message_thread_id=thread_id)

# ==========================================
# 🛑 CAPTURADOR DE ERROS GLOBAL (ANTI-CRASH)
# ==========================================
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(f"❌ Ocorreu um erro interno de conexão capturado: {context.error}")

# ==========================================
# 📱 INTERFACE DE COMANDOS DO TELEGRAM
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    thread_id = update.message.message_thread_id if hasattr(update.message, "message_thread_id") else None
    salvar_grupo_id(chat.id, thread_id)
    await update.message.reply_text(
        "🤠 *SHERIFF DETECTOR V15.5 SMART FILTER OPERANTE*\n\n"
        "• Envie um **domínio limpo** para verificar aproximação por texto.\n"
        "• Use o comando `/ping` para checar a resposta e latência do bot.\n"
        "• Use o comando `/dnschecker` para rodar a varredura inteligente que filtra e traz Canais, VODs e Séries unificados.",
        parse_mode="Markdown",
        message_thread_id=thread_id if thread_id else None
    )

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_autorizacao(update, context): return
    thread_id = update.message.message_thread_id if hasattr(update.message, "message_thread_id") else None

    inicio_lat = time.time()
    msg = await update.message.reply_text("⏱ _Calculando latência..._", parse_mode="Markdown", message_thread_id=thread_id)
    fim_lat = time.time()

    bot_ping_ms = round((fim_lat - inicio_lat) * 1000, 2)

    api_start = time.time()
    await context.bot.get_me()
    api_end = time.time()
    telegram_api_ms = round((api_end - api_start) * 1000, 2)

    relatorio_ping = (
        f"🤠 *PONG! (SHERIFF STATUS)*\n"
        f"──────────────────────────────────\n"
        f"⚡ *Latência do Bot:* `{bot_ping_ms} ms`\n"
        f"📡 *API Telegram:* `{telegram_api_ms} ms`\n"
        f"🟢 *Status:* `Operacional`\n"
        f"──────────────────────────────────"
    )

    await msg.edit_text(relatorio_ping, parse_mode="Markdown")

async def autorizar7(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if chat.type not in ["group", "supergroup"]: return
    membro = await context.bot.get_chat_member(chat.id, user.id)
    if membro.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER] and user.id not in ADMIN_IDS: return
    thread_id = update.message.message_thread_id if hasattr(update.message, "message_thread_id") else None
    salvar_grupo_id(chat.id, thread_id)
    await update.message.reply_text(f"✅ Grupo Autorizado com Sucesso!", message_thread_id=thread_id)

async def escutar_texto_direto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_autorizacao(update, context): return
    msg = update.message.text
    if msg and ("." in msg or "http" in msg) and not msg.startswith("/"):
        if "get.php" in msg:
            await update.message.reply_text("⚠️ Para testar listas M3U completas, use primeiro o comando `/dnschecker`.")
            return
        await processar_sheriff_hibrido(msg, update.message.from_user.id, context, update.message.chat_id)

async def dnschecker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_autorizacao(update, context): return ConversationHandler.END
    chat_id = update.effective_chat.id
    _, thread_id = obter_grupo_id()

    await update.message.reply_text(
        "⏳ *Aguardando link M3U ativo para varredura completa...* (Envie em até 10 segundos)",
        parse_mode="Markdown",
        message_thread_id=thread_id
    )

    async def cancelar_timeout():
        await asyncio.sleep(10)
        if chat_id not in consultas_ativas:
            try: await context.bot.send_message(chat_id=chat_id, text="⚠️ Tempo de envio esgotado!", message_thread_id=thread_id)
            except: pass

    user_timeout_tasks[chat_id] = asyncio.create_task(cancelar_timeout())
    return GET_M3U_LINK

async def receber_m3u(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    texto = update.message.text.strip()

    if chat_id in user_timeout_tasks:
        user_timeout_tasks[chat_id].cancel()

    padrao = re.compile(r"http[s]?://.*get\.php\?[^ ]*username=[^&]+&password=[^&]+")
    if not padrao.search(texto):
        await update.message.reply_text("❌ Link M3U Inválido ou sem parâmetros username/password.")
        return GET_M3U_LINK

    asyncio.create_task(processar_sheriff_hibrido(texto, update.message.from_user.id, context, chat_id))
    return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_autorizacao(update, context): return
    chat_id = update.effective_chat.id
    _, thread_id = obter_grupo_id()
    if chat_id in consultas_ativas:
        consultas_ativas[chat_id] = False
        await update.message.reply_text("🛑 Comando de parada enviado ao motor.", message_thread_id=thread_id)
    else:
        await update.message.reply_text("Nenhuma varredura ativa encontrada para parar.", message_thread_id=thread_id)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id

    if query.data == "stop_scan":
        if chat_id in consultas_ativas:
            consultas_ativas[chat_id] = False
            await query.edit_message_text("🛑 Varredura interrompida. Aguardando finalização do lote...")

async def gerenciar_atualizacao_documento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_autorizacao(update, context): return
    _, thread_id = obter_grupo_id()
    if update.message.document:
        await (await update.message.document.get_file()).download_to_drive(ARQUIVO_BANCO)
        with open(ARQUIVO_BANCO, "r", encoding="utf-8", errors="ignore") as f:
            total = len(extrair_hosts(f.read()))
        await update.message.reply_text(f"📁 **Banco Atualizado Manualmente!**\n📊 {total:,} domínios salvos em cache.".replace(',', '.'), parse_mode="Markdown", message_thread_id=thread_id)

import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import os

# Servidor HTTP embutido para manter a porta do Render satisfeita 24h
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"SHERIFF BOT WEB SERVICE ONLINE")
    def log_message(self, format, *args):
        pass # Silencia os logs de ping para não poluir o painel

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

def main():
    nest_asyncio.apply()
    
    # 1. Inicia o servidor web primeiro para abrir a porta do Render
    threading.Thread(target=run_web_server, daemon=True).start()
    print("🌐 Servidor Web interno rodando em segundo plano e porta aberta!")

    # 2. Configura o loop de eventos de forma segura
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # 3. Baixa a lista automática
    loop.run_until_complete(baixar_lista_automatica(forçar=True))

    # 4. Constrói a aplicação do bot
    app = ApplicationBuilder().token(TOKEN).build()

    # 5. Configura a conversa do dnschecker
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("dnschecker", dnschecker)],
        states={GET_M3U_LINK: [MessageHandler(filters.TEXT & (~filters.COMMAND), receber_m3u)]},
        fallbacks=[CommandHandler("cancelar", cancelar)]
    )

    # 6. Registra todos os comandos e handlers do bot
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("cancelar", cancelar))
    app.add_handler(CommandHandler("autorizar7", autorizar7))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, gerenciar_atualizacao_documento))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), escutar_texto_direto))
    app.add_error_handler(error_handler)

    print("🤠 SHERIFF DETECTOR V15.5 SMART FILTER ONLINE")

    # 7. Inicia o bot mantendo o loop ativo
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
