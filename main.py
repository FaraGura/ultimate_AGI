# main.py
import tkinter as tk
from tkinter import scrolledtext
import time
import threading
from echo_core.config import SYSTEM_VERSION
from echo_core.echo_core import EchoCore

class AssistantGUI:
    def __init__(self, root):
        self.core = EchoCore()
        self.root = root
        self.root.title(f"{SYSTEM_VERSION} — Эхо")
        self.root.geometry("900x700")
        self.root.minsize(640, 480)
        self.root.configure(bg="#1a1a1a")

        chat_frame = tk.Frame(root, bg="#333333", padx=1, pady=1)
        chat_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.chat_area = scrolledtext.ScrolledText(chat_frame, wrap=tk.WORD, font=("Consolas", 11),
                                                   bg="#121212", fg="#d4d4d4", bd=0)
        self.chat_area.pack(fill=tk.BOTH, expand=True)

        bottom_frame = tk.Frame(root, bg="#1a1a1a")
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(0, 10))

        self.crystal_button = tk.Button(bottom_frame, text="Обработать папку знаний (knowledge_input)",
                                        command=self.start_file_learning,
                                        bg="#2d2d2d", fg="#ffffff", bd=0, relief=tk.FLAT, pady=6)
        self.crystal_button.pack(fill=tk.X, pady=(0, 4))

        self.send_button = tk.Button(bottom_frame, text="Отправить сигнал",
                                     font=("Arial", 10, "bold"),
                                     command=self.send_message,
                                     bg="#2d2d2d", fg="#ffffff", bd=0, relief=tk.FLAT, padx=15, pady=6)
        self.send_button.pack(fill=tk.X, pady=(0, 8))

        entry_frame = tk.Frame(root, bg="#333333", padx=1, pady=1)
        entry_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(0, 6))
        self.entry = tk.Text(entry_frame, font=("Consolas", 12), height=4, wrap=tk.WORD,
                             bg="#1a1a1a", fg="#ffffff", insertbackground="white", bd=0)
        self.entry.pack(fill=tk.BOTH, expand=True)
        self.entry.bind("<Return>", self.handle_enter)
        self.entry.bind("<Shift-Return>", self.insert_newline)

        self.setup_clipboard(self.entry, allow_paste=True, allow_cut=True)
        self.setup_clipboard(self.chat_area, allow_paste=False, allow_cut=False)
        self.setup_context_menu(self.entry, allow_paste=True, allow_cut=True)
        self.setup_context_menu(self.chat_area, allow_paste=False, allow_cut=False)

        status_text = "АКТИВЕН (Nomic Embed автономно) 🧠" if self.core.embedder.model else "ОТКЛЮЧЕН (поиск по словам) ⚠️"
        ethics_on = "включены" if self.core.safety.ethics.get("enabled", True) else "отключены"
        qwen_status = "LLM-free (речь через SubjectiveSpeechEngine)"
        self.chat_area.insert(tk.END,
            f"[Ядро] {SYSTEM_VERSION} успешно развернуто.\n"
            f"[Эмбеддинги]: {status_text}\n"
            f"[Режим]: {self.core.state.cognitive.mode}\n"
            f"[Ограничения]: {ethics_on}\n"
            f"[Qwen]: {qwen_status}\n\n")

        self.check_proactive_queue()

    def check_proactive_queue(self):
        msg = self.core.process_proactive_queue()
        if msg:
            self.chat_area.insert(tk.END, f"Эхо: {msg}\n\n")
            self.chat_area.see(tk.END)
        self.root.after(30000, self.check_proactive_queue)

    def setup_clipboard(self, widget, allow_paste=True, allow_cut=True):
        def copy_text(event=None):
            try: widget.event_generate("<<Copy>>")
            except tk.TclError: pass
            return "break"
        def paste_text(event=None):
            if not allow_paste: return "break"
            try: widget.event_generate("<<Paste>>")
            except tk.TclError: pass
            return "break"
        def cut_text(event=None):
            if not allow_cut: return "break"
            try: widget.event_generate("<<Cut>>")
            except tk.TclError: pass
            return "break"
        def select_all(event=None):
            try: widget.event_generate("<<SelectAll>>")
            except tk.TclError: pass
            return "break"

        # Английские буквы
        for seq in ("<Control-c>", "<Control-C>", "<Control-Key-c>", "<Control-Key-C>"):
            widget.bind(seq, copy_text)
        for seq in ("<Control-v>", "<Control-V>", "<Control-Key-v>", "<Control-Key-V>"):
            widget.bind(seq, paste_text)
        for seq in ("<Control-x>", "<Control-X>", "<Control-Key-x>", "<Control-Key-X>"):
            widget.bind(seq, cut_text)
        for seq in ("<Control-a>", "<Control-A>", "<Control-Key-a>", "<Control-Key-A>"):
            widget.bind(seq, select_all)

        # Русские буквы через Cyrillic keysyms
        for seq in ("<Control-Cyrillic_es>", "<Control-Cyrillic_ES>"):
            widget.bind(seq, copy_text)
        for seq in ("<Control-Cyrillic_em>", "<Control-Cyrillic_EM>"):
            widget.bind(seq, paste_text)
        for seq in ("<Control-Cyrillic_che>", "<Control-Cyrillic_CHE>"):
            widget.bind(seq, cut_text)
        for seq in ("<Control-Cyrillic_ef>", "<Control-Cyrillic_EF>"):
            widget.bind(seq, select_all)

        # Универсальные системные сочетания
        widget.bind("<Control-Insert>", copy_text)
        if allow_paste:
            widget.bind("<Shift-Insert>", paste_text)
        if allow_cut:
            widget.bind("<Shift-Delete>", cut_text)

    def setup_context_menu(self, widget, allow_paste=True, allow_cut=True):
        menu = tk.Menu(widget, tearoff=0, bg="#2d2d2d", fg="#ffffff")
        def popup(event):
            try: menu.tk_popup(event.x_root, event.y_root)
            finally: menu.grab_release()
        menu.add_command(label="Копировать", command=lambda: widget.event_generate("<<Copy>>"))
        if allow_cut:
            menu.add_command(label="Вырезать", command=lambda: widget.event_generate("<<Cut>>"))
        if allow_paste:
            menu.add_command(label="Вставить", command=lambda: widget.event_generate("<<Paste>>"))
        menu.add_command(label="Выделить всё", command=lambda: widget.event_generate("<<SelectAll>>"))
        widget.bind("<Button-3>", popup)

    def start_file_learning(self):
        self.append_chat("💤 [Система] Эхо переходит в Фазу Сна...\n")
        self.crystal_button.config(state=tk.DISABLED, text="💤 Эхо спит...")
        def run():
            start = time.time()
            try:
                count = self.core.process_knowledge_inbox()
                duration = round(time.time() - start, 1)
                self.append_chat(f"✨ [ЭХО ПРОСНУЛАСЬ]: Фаза Сна завершена за {duration} сек.\n"
                                 f"🧠 Обработано блоков: {count}.\n\n")
            except Exception as e:
                self.append_chat(f"❌ [Система] Ошибка Фазы Сна: {e}\n\n")
            finally:
                self.crystal_button.config(state=tk.NORMAL, text="Обработать папку знаний (knowledge_input)")
        threading.Thread(target=run, daemon=True).start()

    def append_chat(self, text):
        self.root.after(0, lambda: self.chat_area.insert(tk.END, text))
        self.root.after(0, lambda: self.chat_area.see(tk.END))

    def handle_enter(self, event):
        self.send_message()
        return "break"

    def insert_newline(self, event):
        self.entry.insert(tk.INSERT, "\n")
        return "break"

    def send_message(self, event=None):
        user_text = self.entry.get("1.0", tk.END).strip()
        if not user_text:
            return
        self.chat_area.insert(tk.END, f"Вы: {user_text}\n")
        self.entry.delete("1.0", tk.END)
        self.chat_area.see(tk.END)
        try:
            response = self.core.generate_response(user_text)
        except Exception as e:
            response = f"[Ошибка]: {e}"
        self.chat_area.insert(tk.END, f"Эхо: {response}\n\n")
        self.chat_area.see(tk.END)


if __name__ == "__main__":
    root = tk.Tk()
    app = AssistantGUI(root)
    root.mainloop()