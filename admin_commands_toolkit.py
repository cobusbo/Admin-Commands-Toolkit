import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import pyautogui as pg
import win32gui, win32con, win32process
import psutil, time, json, sys, webbrowser
from pathlib import Path
from PIL import Image, ImageTk

# ───────── Config ─────────
GAME_EXE_NAME = "SCUM.exe"
BUTTON_FONT   = ("Segoe UI", 10, "bold")
TYPE_INTERVAL = 0.01
ENTER_DELAY   = 0.05
GRID_ROWS, GRID_COLS = 5, 5                   # 5 × 5 grid (vertical first)

BASE_DIR   = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
DATA_DIR   = BASE_DIR / "data"; DATA_DIR.mkdir(exist_ok=True)
PROFILES_FILE = DATA_DIR / "profiles.json"

DEFAULT_PROFILE  = "Admin Cmds"
DEFAULT_COMMANDS = [
    {"label": "Admin Commands on",
     "cmd": "#SetGodMode true\n#SetImmortality true\n#SetInfiniteAmmo true\n"
            "#ShowArmedNPCsLocation true\n#SetMalfunctionProbability None\n#SetInfiniteStamina true",
     "bgimg": None, "hotkey": ""},
    {"label": "Show Players",
     "cmd": "#ListPlayers\n#ShowNameplates true\n#ShowOtherPlayerLocations true\n#ShowOtherPlayerInfo true",
     "bgimg": None, "hotkey": ""},
    {"label": "Admin off",
     "cmd": "#SetGodMode false\n#SetImmortality false\n#SetInfiniteAmmo false\n"
            "#ShowArmedNPCsLocation false\n#SetInfiniteStamina false",
     "bgimg": None, "hotkey": ""}
]

def _ensure_default_profiles():
    if not PROFILES_FILE.exists():
        PROFILES_FILE.write_text(
            json.dumps({DEFAULT_PROFILE: DEFAULT_COMMANDS}, indent=2),
            encoding="utf-8"
        )
# ───────── SCUM helpers ─────────
def _find_scum_window():
    tgt = None
    def _enum(hwnd, _):
        nonlocal tgt
        if win32gui.IsWindowVisible(hwnd) and win32gui.IsWindowEnabled(hwnd):
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                if psutil.Process(pid).name().lower() == GAME_EXE_NAME.lower():
                    tgt = hwnd; return False
            except psutil.Error:
                pass
        return True
    win32gui.EnumWindows(_enum, None); return tgt

def bring_game_to_front() -> bool:
    h = _find_scum_window()
    if not h: return False
    win32gui.ShowWindow(h, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(h)
    return True

def send_command(block: str):
    if not bring_game_to_front():
        messagebox.showerror("Error", "SCUM window not found."); return
    time.sleep(0.2); pg.press("t"); time.sleep(0.1)
    for line in filter(None, (l.strip() for l in block.splitlines())):
        pg.typewrite(line, interval=TYPE_INTERVAL); pg.press("enter"); time.sleep(ENTER_DELAY)
    pg.press("escape")

# ───────── Main app ─────────
class AdminCommandsToolkit(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Admin Commands Toolkit"); self.minsize(560, 450)

        # State / data
        self.dark   = tk.BooleanVar(value=False)
        self.on_top = tk.BooleanVar(value=False)
        self.alpha  = tk.DoubleVar(value=1.0)                 # transparency
        self.profiles = {}; self.current_profile = DEFAULT_PROFILE
        self._load_profiles()

        self.icon_cache, self.button_widgets = [], []
        self.drag = {"widget": None, "start": None, "moved": False}
        self.bound_hotkeys = []

        # ttk style
        self.style = ttk.Style(self); self.style.theme_use("clam")
        self._apply_light()

        # Build UI
        self._build_ui()
        self._render_buttons()
        self._bind_hotkeys()

    # ─── recursive recolor ───
    def _apply_theme_to_widget(self, widget, dark: bool):
        bg_dark = "#000000"; fg_dark = "white"
        for child in widget.winfo_children():
            self._apply_theme_to_widget(child, dark)
            if isinstance(child, (tk.Entry, tk.Text)):
                child.configure(bg=bg_dark if dark else "white",
                                fg=fg_dark if dark else "black",
                                insertbackground=fg_dark if dark else "black")
            elif isinstance(child, tk.Listbox):
                child.configure(bg=bg_dark if dark else "white",
                                fg=fg_dark if dark else "black",
                                selectbackground="#5a5a5a" if dark else "#cccccc")
            elif isinstance(child, tk.Canvas):
                child.configure(bg=bg_dark if dark else "white")

    # ─── Themes ───
    def _apply_light(self):
        self.configure(bg="white")
        self.style.configure(".", background="white", foreground="black", font=BUTTON_FONT)
        self.style.configure("Command.TButton", background="white", foreground="black",
                             wraplength=120, justify="center", padding=(6, 8))
        self.style.map("Command.TButton", background=[("active", "#dddddd")])
        if hasattr(self, "canvas"):
            self.canvas.configure(bg="white"); self.inner.configure(bg="white")
        self._apply_theme_to_widget(self, dark=False)

    def _apply_dark(self):
        self.configure(bg="#2b2b2b")
        self.style.configure(".", background="#2b2b2b", foreground="white", font=BUTTON_FONT)
        self.style.configure("Command.TButton", background="#444444", foreground="white",
                             wraplength=120, justify="center", padding=(6, 8))
        self.style.map("Command.TButton", background=[("active", "#666666")])
        if hasattr(self, "canvas"):
            self.canvas.configure(bg="#2b2b2b"); self.inner.configure(bg="#000000")
        self._apply_theme_to_widget(self, dark=True)

    def _toggle_theme(self):
        (self._apply_dark if self.dark.get() else self._apply_light)()
        self._render_buttons()

    # ─── UI build ───
    def _build_ui(self):
        # Profile tabs
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="x", padx=6, pady=(6, 2))
        self.tabs.bind("<<NotebookTabChanged>>", lambda _=None: self._tab_changed())

        # Settings + add button
        topbar = ttk.Frame(self); topbar.pack(fill="x", padx=6)
        ttk.Button(topbar, text="＋", width=3,
                   command=lambda: self._open_settings(None, "commands"))\
            .pack(side="right", padx=(0, 2))
        ttk.Button(topbar, text="⚙️ Settings",
                   command=self._open_settings).pack(side="right")

        # Scrollable grid
        body = ttk.Frame(self); body.pack(fill="both", expand=True, padx=8, pady=8)
        self.canvas = tk.Canvas(body, bg="white", bd=0, highlightthickness=0)
        vbar = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=vbar.set)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.pack(side="left", fill="both", expand=True); vbar.pack(side="right", fill="y")

        # footer
        link = tk.Label(self, text="Developed by cobusbo", font=("Segoe UI", 9, "italic"),
                        fg="blue", cursor="hand2", bg=self["bg"])
        link.pack(side="bottom", pady=4)
        link.bind("<Button-1>", lambda e: webbrowser.open_new("https://coff.ee/cobusbo"))

        self._refresh_tabs()

    def _refresh_tabs(self):
        for tab_id in self.tabs.tabs():               # clear safely
            self.tabs.forget(tab_id)
        for name in self.profiles:
            self.tabs.add(ttk.Frame(self.tabs), text=name)
        if self.current_profile not in self.profiles:
            self.current_profile = next(iter(self.profiles))
        self.tabs.select(list(self.profiles).index(self.current_profile))

    def _tab_changed(self):
        self.current_profile = list(self.profiles)[self.tabs.index(self.tabs.select())]
        self._render_buttons(); self._bind_hotkeys()

    # ─── Button grid ───
    def _render_buttons(self):
        for w in self.inner.winfo_children(): w.destroy()
        self.button_widgets.clear(); self.icon_cache.clear()
        cmds = self.profiles[self.current_profile][:GRID_ROWS*GRID_COLS]

        for i, cmd in enumerate(cmds):
            col, row = divmod(i, GRID_ROWS)
            txt = cmd["label"] + (f"\n[{cmd['hotkey']}]" if cmd.get("hotkey") else "")
            btn = ttk.Button(self.inner, text=txt, style="Command.TButton",
                             command=lambda c=cmd["cmd"]: send_command(c))
            btn.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
            btn.bind("<Button-3>", lambda e, idx=i: self._menu(idx, e))
            btn.bind("<ButtonPress-1>", self._drag_start)
            btn.bind("<B1-Motion>", self._drag_move)
            btn.bind("<ButtonRelease-1>", self._drag_drop)
            self.button_widgets.append(btn)

            if cmd.get("bgimg"):
                p = (BASE_DIR / cmd["bgimg"]).resolve()
                if p.is_file():
                    try:
                        img = Image.open(p).resize((120, 80), Image.ANTIALIAS)
                        ph = ImageTk.PhotoImage(img)
                        btn.configure(image=ph, compound="center")
                        self.icon_cache[str(p)] = ph
                    except Exception:
                        pass

        for r in range(GRID_ROWS): self.inner.rowconfigure(r, weight=1)
        for c in range(GRID_COLS): self.inner.columnconfigure(c, weight=1)
    # Context menu
    def _menu(self, idx, e):
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="Edit", command=lambda: self._open_settings(idx, "commands"))
        m.add_command(label="Delete", command=lambda: self._delete(idx))
        m.tk_popup(e.x_root, e.y_root)

    def _delete(self, idx):
        if messagebox.askyesno("Delete", "Delete command?", parent=self):
            self.profiles[self.current_profile].pop(idx)
            self._save(); self._render_buttons(); self._bind_hotkeys()

    # drag‑n‑drop helpers
    def _drag_start(self, e):
        if e.widget in self.button_widgets:
            self.drag = {"widget": e.widget, "start": self.button_widgets.index(e.widget),
                         "x": e.x, "y": e.y, "moved": False}
    def _drag_move(self, e):
        w = self.drag["widget"]
        if w:
            dx, dy = e.x - self.drag["x"], e.y - self.drag["y"]
            if abs(dx) > 3 or abs(dy) > 3: self.drag["moved"] = True
            if self.drag["moved"]:
                w.place(in_=self.inner,
                        x=w.winfo_x() - self.drag["x"] + e.x,
                        y=w.winfo_y() - self.drag["y"] + e.y)
    def _drag_drop(self, e):
        w, start = self.drag["widget"], self.drag["start"]
        if not w: return
        if not self.drag["moved"]:
            w.place_forget(); self.drag = {"widget": None, "start": None}; return
        closest, dist = None, 1e9
        for i, b in enumerate(self.button_widgets):
            if b is w: continue
            cx, cy = b.winfo_rootx()+b.winfo_width()//2, b.winfo_rooty()+b.winfo_height()//2
            d = (cx - e.x_root)**2 + (cy - e.y_root)**2
            if d < dist: closest, dist = i, d
        if closest is not None and closest != start:
            cmds = self.profiles[self.current_profile]
            cmds.insert(closest, cmds.pop(start)); self._save()
        w.place_forget(); self.drag = {"widget": None, "start": None}
        self._render_buttons(); self._bind_hotkeys()

    # Hotkeys
    def _bind_hotkeys(self):
        for hk in self.bound_hotkeys: self.unbind_all(hk)
        self.bound_hotkeys.clear()
        for cmd in self.profiles[self.current_profile]:
            hk = cmd.get("hotkey", "").strip()
            if hk:
                try:
                    self.bind_all(f"<{hk}>",
                                  lambda e, c=cmd["cmd"]: (send_command(c), "break"))
                    self.bound_hotkeys.append(f"<{hk}>")
                except Exception:
                    pass

    # persistence
    def _load_profiles(self):
        _ensure_default_profiles()
        try: self.profiles = json.loads(PROFILES_FILE.read_text("utf-8"))
        except Exception: self.profiles = {DEFAULT_PROFILE: DEFAULT_COMMANDS}
    def _save(self):
        PROFILES_FILE.write_text(json.dumps(self.profiles, indent=2), encoding="utf-8")

    # settings
    def _open_settings(self, idx=None, tab="general"):
        SettingsWindow(self, idx, tab)

# ─────────────────────────────────────────────
class SettingsWindow(tk.Toplevel):
    def __init__(self, master: AdminCommandsToolkit, edit_idx=None, tab="general"):
        super().__init__(master)
        self.master = master; self.edit_idx = edit_idx
        self.title("Settings"); self.geometry("700x600")
        self.transient(master); self.grab_set()

        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True, padx=8, pady=8)
        self._build_general_tab(nb)
        self._build_profiles_tab(nb)
        self._build_commands_tab(nb)
        nb.select({"profiles": 1, "commands": 2}.get(tab, 0))
        if edit_idx is not None:
            self.cmd_list.selection_set(edit_idx); self._load_cmd()

        master._apply_theme_to_widget(self, master.dark.get())

    # ─ General tab (with transparency slider) ─
    def _build_general_tab(self, nb):
        g = ttk.Frame(nb); nb.add(g, text="General")
        ttk.Checkbutton(g, text="Dark Mode", variable=self.master.dark,
                        command=self.master._toggle_theme)\
            .pack(anchor="w", padx=8, pady=6)
        ttk.Checkbutton(g, text="Always on top", variable=self.master.on_top,
                        command=lambda: self.master.attributes("-topmost", self.master.on_top.get()))\
            .pack(anchor="w", padx=8, pady=6)

        row = ttk.Frame(g); row.pack(anchor="w", padx=8, pady=10, fill="x")
        ttk.Label(row, text="Transparency").pack(side="left")
        ttk.Scale(row, from_=0.1, to=1.0, orient="horizontal",
                  variable=self.master.alpha,
                  command=self._update_alpha)\
            .pack(side="left", fill="x", expand=True, padx=(6, 0))

    def _update_alpha(self, _=None):
        val = float(self.master.alpha.get())
        self.master.attributes("-alpha", val)
        self.attributes("-alpha", val)            # settings window too

    # ─ Profiles tab ─
    def _build_profiles_tab(self, nb):
        f = ttk.Frame(nb); nb.add(f, text="Profiles")
        self.pro_list = tk.Listbox(f, exportselection=False)
        self.pro_list.pack(side="left", fill="both", expand=True, padx=(0, 5), pady=5)
        self.pro_list.bind("<<ListboxSelect>>", lambda _: self._sel_profile())
        side = ttk.Frame(f); side.pack(side="right", fill="y", pady=5)
        for t, c in (("New", self._new_p), ("Rename", self._ren_p),
                     ("Delete", self._del_p), ("Import", self._imp), ("Export", self._exp)):
            ttk.Button(side, text=t, command=c).pack(fill="x", pady=2)
        self._refresh_profiles()

    # profile helpers (unchanged) …
    #  ▼ ▼ ▼  KEEP THE SAME IMPLEMENTATION YOU ALREADY HAVE  ▼ ▼ ▼
    # (Refresh, select, new, rename, delete, import, export)
    # -----------------------------------------------------------

    def _refresh_profiles(self):
        self.pro_list.delete(0, tk.END)
        for p in self.master.profiles: self.pro_list.insert(tk.END, p)
        self.pro_list.select_set(list(self.master.profiles).index(self.master.current_profile))

    def _sel_profile(self):
        sel = self.pro_list.curselection()
        if sel:
            self.master.current_profile = list(self.master.profiles)[sel[0]]
            self.master._refresh_tabs(); self._refresh_cmds()
            self.master._render_buttons(); self.master._bind_hotkeys()

    def _new_p(self):
        n = simpledialog.askstring("New Profile", "Name:", parent=self)
        if n and n not in self.master.profiles:
            self.master.profiles[n] = []; self.master.current_profile = n
            self.master._refresh_tabs(); self._refresh_profiles(); self.master._save()

    def _ren_p(self):
        cur = self.master.current_profile
        n = simpledialog.askstring("Rename", "New name:", initialvalue=cur, parent=self)
        if n and n not in self.master.profiles:
            self.master.profiles[n] = self.master.profiles.pop(cur)
            self.master.current_profile = n
            self.master._refresh_tabs(); self._refresh_profiles(); self.master._save()

    def _del_p(self):
        if len(self.master.profiles) == 1:
            messagebox.showwarning("Protected", "At least one profile required.", parent=self); return
        if messagebox.askyesno("Delete", f"Delete '{self.master.current_profile}'?", parent=self):
            self.master.profiles.pop(self.master.current_profile)
            self.master.current_profile = next(iter(self.master.profiles))
            self.master._refresh_tabs(); self._refresh_profiles(); self._refresh_cmds()
            self.master._save(); self.master._render_buttons(); self.master._bind_hotkeys()

    def _imp(self):
        f = filedialog.askopenfilename(filetypes=[("JSON", "*.json")], parent=self)
        if f:
            try: data = json.load(open(f, "r", encoding="utf-8"))
            except Exception as e: messagebox.showerror("Error", e, parent=self); return
            if isinstance(data, dict): self.master.profiles.update(data)
            self.master._refresh_tabs(); self._refresh_profiles(); self.master._save()

    def _exp(self):
        f = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")], parent=self)
        if f: json.dump(self.master.profiles, open(f, "w", encoding="utf-8"), indent=2)

    # ─ Commands tab (unchanged except using tk.Entry for dark bg) ─
    def _build_commands_tab(self, nb):
        f = ttk.Frame(nb); nb.add(f, text="Commands")
        self.cmd_list = tk.Listbox(f, exportselection=False)
        self.cmd_list.pack(side="left", fill="both", expand=True, padx=(0, 5), pady=5)
        self.cmd_list.bind("<<ListboxSelect>>", lambda _: self._load_cmd())

        ed = ttk.Frame(f); ed.pack(side="right", fill="both", expand=False, padx=5, pady=5)
        ttk.Label(ed, text="Label").pack(anchor="w")
        self.e_lbl = tk.Entry(ed); self.e_lbl.pack(fill="x")

        ttk.Label(ed, text="Command(s)").pack(anchor="w")
        self.e_cmd = tk.Text(ed, height=6, wrap="word"); self.e_cmd.pack(fill="both", expand=True)

        ttk.Label(ed, text="Background Image").pack(anchor="w")
        row = ttk.Frame(ed); row.pack(fill="x")
        self.e_bg = tk.Entry(row); self.e_bg.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="…", width=3, command=lambda: self._browse(self.e_bg))\
            .pack(side="left", padx=2)

        ttk.Label(ed, text="Hotkey (click & press)").pack(anchor="w")
        self.e_hot = tk.Entry(ed); self.e_hot.pack(fill="x")
        self.e_hot.bind("<FocusIn>", lambda _: self._hk_reset())
        self.e_hot.bind("<Key>", self._hk_capture); self._hk_parts = set()

        foot = ttk.Frame(ed); foot.pack(fill="x", pady=6)
        self.b_save = ttk.Button(foot, text="Add", command=self._save_cmd)
        self.b_save.pack(side="left", fill="x", expand=True, padx=2)
        ttk.Button(foot, text="Clear", command=self._clear)\
            .pack(side="left", fill="x", expand=True, padx=2)

        self._refresh_cmds()
        self.master._apply_theme_to_widget(f, self.master.dark.get())

    # command helpers (same as before) …
    def _refresh_cmds(self):
        self.cmd_list.delete(0, tk.END)
        for c in self.master.profiles[self.master.current_profile]:
            hk = f" [{c['hotkey']}]" if c.get("hotkey") else ""
            self.cmd_list.insert(tk.END, c["label"] + hk)

    def _load_cmd(self):
        sel = self.cmd_list.curselection()
        if not sel: return
        i = sel[0]; self.edit_idx = i
        cmd = self.master.profiles[self.master.current_profile][i]
        self.e_lbl.delete(0, tk.END); self.e_lbl.insert(0, cmd["label"])
        self.e_cmd.delete("1.0", tk.END); self.e_cmd.insert("1.0", cmd["cmd"])
        self.e_bg.delete(0, tk.END); self.e_bg.insert(0, cmd.get("bgimg", "") or "")
        self.e_hot.delete(0, tk.END); self.e_hot.insert(0, cmd.get("hotkey", ""))
        self.b_save.config(text="Save")

    def _clear(self):
        self.edit_idx = None; self.b_save.config(text="Add")
        for w in (self.e_lbl, self.e_bg, self.e_hot): w.delete(0, tk.END)
        self.e_cmd.delete("1.0", tk.END); self._hk_reset()
        self.cmd_list.selection_clear(0, tk.END)

    def _save_cmd(self):
        lbl = self.e_lbl.get().strip(); txt = self.e_cmd.get("1.0", tk.END).strip()
        bg = self.e_bg.get().strip() or None; hk = self.e_hot.get().strip()
        if not lbl or not txt:
            messagebox.showwarning("Input", "Label & command required", parent=self); return
        lst = self.master.profiles[self.master.current_profile]
        new = {"label": lbl, "cmd": txt, "bgimg": bg, "hotkey": hk}
        if self.edit_idx is None: lst.append(new)
        else: lst[self.edit_idx] = new
        self.master._save(); self._refresh_cmds()
        self.master._render_buttons(); self.master._bind_hotkeys(); self._clear()

    # hotkey capture
    def _hk_reset(self): self._hk_parts.clear(); self.e_hot.delete(0, tk.END)
    def _hk_capture(self, e):
        k = e.keysym
        if k in ("Shift_L","Shift_R"):   self._hk_parts.add("Shift")
        elif k in ("Control_L","Control_R"): self._hk_parts.add("Control")
        elif k in ("Alt_L","Alt_R","Meta_L","Meta_R"): self._hk_parts.add("Alt")
        elif k == "BackSpace": self._hk_reset(); return "break"
        else:
            self._hk_parts.add(k.capitalize())
            order=[m for m in ("Control","Alt","Shift") if m in self._hk_parts]
            other=[p for p in self._hk_parts if p not in ("Control","Alt","Shift")]
            if other: order.append(other[-1])
            self.e_hot.delete(0, tk.END); self.e_hot.insert(0, "-".join(order))
            self._hk_parts.clear()
        return "break"

    def _browse(self, entry):
        f = filedialog.askopenfilename(
            filetypes=[("Images","*.png;*.jpg;*.gif;*.bmp"), ("All","*.*")], parent=self)
        if f:
            try: rel = Path(f).relative_to(BASE_DIR)
            except ValueError: rel = Path(f)
            entry.delete(0, tk.END); entry.insert(0, str(rel).replace("\\","/"))

# ─ Entry point ─
if __name__ == "__main__":
    _ensure_default_profiles()
    AdminCommandsToolkit().mainloop()
