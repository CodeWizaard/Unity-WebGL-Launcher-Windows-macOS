"""Native, single-window UI. No third-party runtime dependencies."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
import sys
from tkinter import filedialog, messagebox, ttk
import webbrowser
import threading
import tempfile
import os

try:
    import qrcode
    from PIL import Image, ImageTk
except ImportError:
    qrcode = None
    Image = None
    ImageTk = None

from .server import Preview


class Launcher:
    def __init__(self, window: tk.Tk):
        self.window = window
        self.preview = Preview()
        window.title("Unity WebGL Launcher")
        assets = Path(__file__).with_name("assets")
        if sys.platform == "win32":
            window.iconbitmap(default=str(assets / "launcher.ico"))
        else:
            self.icon = tk.PhotoImage(file=str(assets / "launcher.png"))
            window.iconphoto(True, self.icon)
        window.geometry("680x550")
        window.minsize(620, 520)
        window.protocol("WM_DELETE_WINDOW", self.close)
        self.path = tk.StringVar()
        self.mode = tk.StringVar(value="local")
        self.address = tk.StringVar()
        self.status = tk.StringVar(value="Выберите WebGL-билд, чтобы начать")
        self.note = tk.StringVar(value="Откроется в вашем обычном браузере. Установка сервера не нужна.")
        frame = ttk.Frame(window, padding=24)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text="Unity WebGL Launcher", font=("", 21, "bold")).grid(row=0, sticky="w")
        ttk.Label(frame, text="Ваш билд — в браузере или на телефоне").grid(row=1, sticky="w", pady=(4, 22))
        self.path_entry = ttk.Entry(frame, textvariable=self.path)
        self.path_entry.grid(row=2, sticky="ew")
        choices = ttk.Frame(frame)
        choices.grid(row=3, sticky="w", pady=(8, 20))
        self.file_button = ttk.Button(choices, text="Выбрать index.html", command=self.choose_file)
        self.file_button.pack(side="left")
        self.folder_button = ttk.Button(choices, text="Выбрать папку", command=self.choose_folder)
        self.folder_button.pack(side="left", padx=8)
        modes = ttk.Frame(frame)
        modes.grid(row=4, sticky="w")
        self.radios = []
        for label, value in [("Только этот компьютер", "local"), ("Телефон по Wi-Fi", "lan")]:
            radio = ttk.Radiobutton(modes, text=label, variable=self.mode, value=value, command=self.mode_changed)
            radio.pack(side="left", padx=(0, 20))
            self.radios.append(radio)
        actions = ttk.Frame(frame)
        actions.grid(row=5, sticky="w", pady=20)
        self.toggle_button = ttk.Button(actions, text="Запустить", command=self.toggle)
        self.toggle_button.pack(side="left")
        self.browser_button = ttk.Button(actions, text="Открыть в браузере", command=self.open_browser, state="disabled")
        self.browser_button.pack(side="left", padx=8)
        ttk.Label(frame, textvariable=self.status).grid(row=6, sticky="w")
        address_row = ttk.Frame(frame)
        address_row.grid(row=7, sticky="ew", pady=(8, 10))
        address_row.columnconfigure(0, weight=1)
        self.address_box = ttk.Combobox(address_row, textvariable=self.address, state="disabled")
        self.address_box.grid(row=0, column=0, sticky="ew")
        self.copy_button = ttk.Button(address_row, text="Копировать", command=self.copy, state="disabled")
        self.copy_button.grid(row=0, column=1, padx=(8, 0))
        
        self.qr_frame = ttk.Frame(frame)
        self.qr_frame.grid(row=8, sticky="w", pady=(8, 10))
        self.qr_code_label = ttk.Label(self.qr_frame, text="QR-код для телефона")
        self.qr_code_label.pack(side="left")
        self.qr_image_label = ttk.Label(self.qr_frame)
        self.qr_image_label.pack(side="left", padx=10)

        self.note_label = ttk.Label(frame, textvariable=self.note, wraplength=605, justify="left")
        self.note_label.grid(row=9, sticky="ew")
        frame.bind("<Configure>", lambda event: self.note_label.configure(wraplength=max(300, event.width - 48)))

    def choose_file(self):
        value = filedialog.askopenfilename(parent=self.window, title="Выберите HTML-файл WebGL-билда", filetypes=[("HTML", "*.html *.htm")])
        if value:
            self.path.set(value)

    def choose_folder(self):
        value = filedialog.askdirectory(parent=self.window, title="Папка с index.html")
        if value:
            self.path.set(value)

    def mode_changed(self):
        self.note.set("Телефон и компьютер должны быть в одной сети. Для телефона используйте Gzip или Decompression Fallback. Многопоточность требует HTTPS. Папка доступна сети до остановки." if self.mode.get() == "lan" else "Откроется в вашем обычном браузере. Установка сервера не нужна.")

    def toggle(self):
        if self.preview.running:
            self.preview.stop()
            self.set_running(False)
            self.status.set("Остановлено")
            self.address.set("")
            self.qr_image_label.config(image="")
            self.mode_changed()
            return
        try:
            self.preview.start(self.path.get(), lan=self.mode.get() == "lan")
        except (OSError, ValueError) as error:
            messagebox.showerror("Не удалось запустить", str(error), parent=self.window)
            return
        self.set_running(True)
        addresses = self.preview.phone_urls if self.mode.get() == "lan" else [self.preview.local_url]
        self.address_box.configure(values=addresses, state="readonly" if addresses else "disabled")
        self.address.set(addresses[0] if addresses else "")
        self.copy_button.configure(state="normal" if addresses else "disabled")
        self.status.set("Работает · адрес для телефона" if self.mode.get() == "lan" else "Работает · адрес на этом компьютере")
        self.mode_changed()
        
        if self.mode.get() == "lan" and not addresses:
            self.status.set("Работает · сетевой адрес не найден")
            self.note.set("Подключитесь к Wi-Fi и запустите снова. На этом компьютере билд уже доступен через кнопку «Открыть в браузере».")
        else:
            if addresses and qrcode and Image:
                url = addresses[0]
                try:
                    qr = qrcode.QRCode(version=1, box_size=1, border=1)
                    qr.add_data(url)
                    qr.make(fit=True)
                    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
                    
                    # Use temporary file to display image if ImageTk is not available
                    if ImageTk:
                        self.qr_image_label.config(image=ImageTk.PhotoImage(img))
                    else:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                            img.save(tmp.name)
                            # We need to keep a reference to the photo
                            self.temp_qr_photo = tk.PhotoImage(file=tmp.name)
                            self.qr_image_label.config(image=self.temp_qr_photo)
                except Exception as e:
                    print(f"Failed to generate QR code: {e}")
            else:
                self.qr_image_label.config(image="")

        self.open_browser()

    def set_running(self, running: bool):
        self.toggle_button.configure(text="Остановить" if running else "Запустить")
        for widget in [self.path_entry, self.file_button, self.folder_button, *self.radios]:
            widget.configure(state="disabled" if running else "normal")
        self.browser_button.configure(state="normal" if running else "disabled")
        if not running:
            self.address_box.configure(state="disabled", values=[])
            self.copy_button.configure(state="disabled")
            self.qr_image_label.config(image="")

    def open_browser(self):
        if self.preview.running:
            try:
                opened = webbrowser.open(self.preview.local_url)
            except webbrowser.Error:
                opened = False
            if not opened:
                messagebox.showinfo("Адрес билда", "Откройте в браузере:\n" + self.preview.local_url, parent=self.window)

    def copy(self):
        if self.address.get():
            self.window.clipboard_clear()
            self.window.clipboard_append(self.address.get())
            self.status.set("Адрес скопирован · сервер работает")

    def close(self):
        self.preview.stop()
        self.window.destroy()


def main():
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("CodeWizaard.UnityWebGLLauncher")
    window = tk.Tk()
    Launcher(window)
    window.mainloop()
