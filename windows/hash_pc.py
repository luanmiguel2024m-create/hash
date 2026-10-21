#!/usr/bin/env python3
"""HASH PC Bridge: volume, media keys and controlled app/site launching."""
import ctypes, secrets, socket, json, os, subprocess, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, quote

try:
    from comtypes import CLSCTX_ALL, CoInitialize, CoUninitialize, cast, POINTER
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
except ImportError:
    print("Instale as dependências: py -m pip install pycaw comtypes")
    input("Pressione Enter para sair...")
    raise SystemExit(1)

TOKEN = secrets.token_urlsafe(18)
PORT = 8765
MEDIA = {"next": 0xB0, "previous": 0xB1, "play-pause": 0xB3}

def audio():
    speakers = AudioUtilities.GetSpeakers()
    return cast(speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None), POINTER(IAudioEndpointVolume))

def key(code):
    ctypes.windll.user32.keybd_event(code, 0, 0, 0)
    ctypes.windll.user32.keybd_event(code, 0, 2, 0)

def launch(target, value=""):
    if target == "youtube":
        webbrowser.open("https://www.youtube.com")
    elif target == "steam":
        # Steam URI opens the installed client if available.
        os.startfile("steam://open/main")
    elif target == "url":
        if not (value.startswith("https://") or value.startswith("http://")):
            raise ValueError("O endereço deve começar com http:// ou https://")
        webbrowser.open(value)
    elif target == "program":
        # Restrict to known apps/commands; never execute arbitrary shell text.
        allowed = {
            "notepad": ["notepad.exe"],
            "bloco de notas": ["notepad.exe"],
            "calculadora": ["calc.exe"],
            "calculator": ["calc.exe"],
            "paint": ["mspaint.exe"],
            "explorador": ["explorer.exe"],
            "explorer": ["explorer.exe"],
            "steam": ["cmd", "/c", "start", "", "steam://open/main"],
        }
        keyname = value.strip().lower()
        if keyname not in allowed:
            raise ValueError("Programa não permitido. Use: Notepad, Calculadora, Paint, Explorador ou Steam.")
        subprocess.Popen(allowed[keyname], shell=False)
    else:
        raise ValueError("Atalho desconhecido")

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): print("[HASH]", fmt % args)
    def reply(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)
    def auth(self):
        path = urlparse(self.path).path.strip("/").split("/")
        if len(path) < 2 or not secrets.compare_digest(path[0], TOKEN):
            self.reply(403, {"ok": False, "error": "PIN inválido"})
            return None
        return "/" + "/".join(path[1:])
    def do_OPTIONS(self): self.reply(204, {})
    def do_GET(self):
        p = self.auth()
        if p == "/health": self.reply(200, {"ok": True, "app": "HASH PC Bridge"})
        elif p is not None: self.reply(404, {"ok": False, "error": "Rota não encontrada"})
    def do_POST(self):
        p = self.auth()
        if p is None: return
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        try:
            if p == "/volume":
                n = int(query.get("level", ["50"])[0])
                CoInitialize()
                try: audio().SetMasterVolumeLevelScalar(max(0, min(100, n))/100, None)
                finally: CoUninitialize()
            elif p == "/mute":
                CoInitialize()
                try:
                    a = audio()
                    a.SetMute(0 if a.GetMute() else 1, None)
                finally: CoUninitialize()
            elif p in ("/volume-up", "/volume-down"):
                CoInitialize()
                try:
                    a = audio()
                    delta = 0.05 if p == "/volume-up" else -0.05
                    a.SetMasterVolumeLevelScalar(max(0, min(1, a.GetMasterVolumeLevelScalar()+delta)), None)
                finally: CoUninitialize()
            elif p in ("/next", "/previous", "/play-pause"):
                key(MEDIA[p[1:]])
            elif p == "/open":
                launch(query.get("target", [""])[0], query.get("value", [""])[0])
            else:
                self.reply(404, {"ok": False, "error": "Comando desconhecido"}); return
            self.reply(200, {"ok": True})
        except Exception as e:
            self.reply(400, {"ok": False, "error": str(e)})

def local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try: s.connect(("192.0.2.1", 80)); return s.getsockname()[0]
    except OSError: return "IP_DO_PC"
    finally: s.close()

if __name__ == "__main__":
    print("\\nHASH PC Bridge — mantenha esta janela aberta")
    print("Endereço para o campo de conexão do app:")
    print(f"  {local_ip()}:{PORT}/{TOKEN}")
    print("Celular e PC devem estar no mesmo Wi-Fi. Permita rede privada no Firewall.")
    print("Não compartilhe o endereço/PIN nem encaminhe a porta à internet.")
    print("Programas permitidos por nome: Notepad, Calculadora, Paint e Explorador.")
    print("Ctrl+C encerra o programa.\\n")
    try: ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    except KeyboardInterrupt: print("\\nEncerrado.")
