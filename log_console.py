import json
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import tkinter as tk
from tkinter import messagebox


HOST = "127.0.0.1"
PORT = 3000


class LogHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/log":
            self.send_response(404)
            self.end_headers()
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            data = json.loads(raw.decode("utf-8"))

            message = str(data.get("message", ""))
            log_type = str(data.get("type", "Unknown"))
            timestamp = data.get("timestamp")

            root.after(0, add_log, message, log_type, timestamp)

            self.send_response(204)
            self.end_headers()
        except Exception as exc:
            print("POST /log error:", exc)
            self.send_response(400)
            self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            body = b'{"ok":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *_):
        pass


def normalize_type(value):
    value = str(value)
    if "Warning" in value:
        return "WARN"
    if "Error" in value:
        return "ERROR"
    if "Output" in value:
        return "OUTPUT"
    return value.upper()


def add_log(message, log_type, timestamp=None):
    global log_count
    log_count += 1

    if timestamp:
        try:
            ts = float(timestamp)
            time_text = datetime.fromtimestamp(ts / 1000).strftime("%H:%M:%S")
        except Exception:
            time_text = datetime.now().strftime("%H:%M:%S")
    else:
        time_text = datetime.now().strftime("%H:%M:%S")

    typ = normalize_type(log_type)

    text.configure(state="normal")
    text.insert("end", f"[{time_text}] ", "time")
    text.insert("end", f"{typ:<8} ", "type_" + typ.lower())
    text.insert("end", message + "\n", "message")
    text.configure(state="disabled")
    text.see("end")

    count_label.config(text=f"{log_count} log{'s' if log_count != 1 else ''}")
    status_label.config(text="●  recebendo logs", fg="#48d597")


def clear_logs():
    global log_count
    log_count = 0
    text.configure(state="normal")
    text.delete("1.0", "end")
    text.configure(state="disabled")
    count_label.config(text="0 logs")


def copy_logs():
    content = text.get("1.0", "end-1c")
    root.clipboard_clear()
    root.clipboard_append(content)
    root.update()


def start_server():
    try:
        server = ThreadingHTTPServer((HOST, PORT), LogHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        status_label.config(text=f"●  localhost:{PORT} ativo", fg="#48d597")
    except OSError as exc:
        status_label.config(text=f"●  porta {PORT} ocupada", fg="#ef6b73")
        messagebox.showerror(
            "Erro",
            f"Não foi possível iniciar localhost:{PORT}.\n\n{exc}"
        )


root = tk.Tk()
root.title("Roblox Log Console")
root.geometry("1100x700")
root.minsize(750, 450)
root.configure(bg="#0b0d10")

log_count = 0

header = tk.Frame(root, bg="#101318", height=76)
header.pack(fill="x")
header.pack_propagate(False)

left = tk.Frame(header, bg="#101318")
left.pack(side="left", padx=18, pady=12)

title = tk.Label(
    left,
    text="Roblox Log Console",
    bg="#101318",
    fg="#ffffff",
    font=("Segoe UI", 16, "bold")
)
title.pack(anchor="w")

status_label = tk.Label(
    left,
    text="●  iniciando localhost...",
    bg="#101318",
    fg="#89919c",
    font=("Segoe UI", 9)
)
status_label.pack(anchor="w")

buttons = tk.Frame(header, bg="#101318")
buttons.pack(side="right", padx=18)

clear_button = tk.Button(
    buttons,
    text="Limpar",
    command=clear_logs,
    bg="#181c22",
    fg="#cbd1d9",
    activebackground="#222832",
    activeforeground="#ffffff",
    relief="flat",
    padx=14,
    pady=7
)
clear_button.pack(side="left", padx=4)

copy_button = tk.Button(
    buttons,
    text="Copiar",
    command=copy_logs,
    bg="#181c22",
    fg="#cbd1d9",
    activebackground="#222832",
    activeforeground="#ffffff",
    relief="flat",
    padx=14,
    pady=7
)
copy_button.pack(side="left", padx=4)

body = tk.Frame(root, bg="#0b0d10")
body.pack(fill="both", expand=True)

scroll = tk.Scrollbar(body)
scroll.pack(side="right", fill="y")

text = tk.Text(
    body,
    bg="#0b0d10",
    fg="#d7dce2",
    insertbackground="#ffffff",
    selectbackground="#29313c",
    relief="flat",
    borderwidth=0,
    font=("Consolas", 10),
    padx=14,
    pady=10,
    wrap="word",
    yscrollcommand=scroll.set
)
text.pack(fill="both", expand=True)
scroll.config(command=text.yview)

text.tag_configure("time", foreground="#59616c")
text.tag_configure("type_output", foreground="#8fa1b5")
text.tag_configure("type_warn", foreground="#e8c56b")
text.tag_configure("type_error", foreground="#f07878")
text.tag_configure("type_unknown", foreground="#8fa1b5")
text.tag_configure("message", foreground="#d7dce2")

text.configure(state="disabled")

footer = tk.Frame(root, bg="#101318", height=30)
footer.pack(fill="x")
footer.pack_propagate(False)

count_label = tk.Label(
    footer,
    text="0 logs",
    bg="#101318",
    fg="#68717d",
    font=("Segoe UI", 8)
)
count_label.pack(side="left", padx=12)

endpoint_label = tk.Label(
    footer,
    text=f"POST http://{HOST}:{PORT}/log",
    bg="#101318",
    fg="#68717d",
    font=("Segoe UI", 8)
)
endpoint_label.pack(side="right", padx=12)

root.after(100, start_server)
root.mainloop()
