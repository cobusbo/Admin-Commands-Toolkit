import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import pyautogui as pg
import win32gui, win32con, win32process
import psutil, time, json, os, sys, webbrowser
from pathlib import Path
from PIL import Image, ImageTk

# ───────── Config ─────────
GAME_EXE_NAME           = "SCUM.exe"
BUTTON_FONT             = ("Segoe UI", 10, "bold")
TYPE_INTERVAL           = 0.01
ENTER_DELAY             = 0.05
MAX_BUTTON_ROWS         = 5
MAX_BUTTON_COLS         = 5

BASE_DIR  = Path(sys.executable).parent if getattr(sys,"frozen",False) else Path(__file__).parent
DATA_DIR  = BASE_DIR / "data"; DATA_DIR.mkdir(exist_ok=True)
PROFILES_FILE = DATA_DIR / "profiles.json"

DEFAULT_PROFILE  = "Default"
DEFAULT_COMMANDS = [
    {
        "label": "Admin Commands on",
        "cmd": "#SetGodMode true\n#SetImmortality true\n#SetInfiniteAmmo true\n#ShowArmedNPCsLocation true\n#SetMalfunctionProbability None\n#SetInfiniteStamina true",
        "icon": "⏳"
    },
    {
        "label": "Show Players",
        "cmd": "#ListPlayers\n#ShowNameplates true\n#ShowOtherPlayerLocations true\n#ShowOtherPlayerInfo true",
        "icon": ""
    },
    {
        "label": "Admin off",
        "cmd": "#SetGodeMode false\n#SetImmortality false\n#SetInfiniteAmmo false\n#ShowArmedNPCsLocation false\n#SetInfiniteStamina false",
        "icon": "📜"
    }
]


def _ensure_default_data():
    if not PROFILES_FILE.exists():
        default_data = {DEFAULT_PROFILE: DEFAULT_COMMANDS}
        PROFILES_FILE.write_text(json.dumps(default_data, indent=2), encoding="utf-8")

def _find_scum_window():
    tgt=None
    def _enum(hwnd,_):
        nonlocal tgt
        if win32gui.IsWindowVisible(hwnd) and win32gui.IsWindowEnabled(hwnd):
            _,pid=win32process.GetWindowThreadProcessId(hwnd)
            try:
                if psutil.Process(pid).name().lower()==GAME_EXE_NAME.lower():
                    tgt=hwnd; return False
            except psutil.Error: pass
        return True
    win32gui.EnumWindows(_enum,None); return tgt

def bring_game_to_front()->bool:
    h=_find_scum_window()
    if not h: return False
    win32gui.ShowWindow(h,win32con.SW_RESTORE); win32gui.SetForegroundWindow(h); return True

def send_command(block:str):
    if not bring_game_to_front():
        messagebox.showerror("Error","SCUM window not found."); return
    time.sleep(0.2); pg.press("t"); time.sleep(0.1)
    for ln in (l.strip() for l in block.splitlines()):
        if ln:
            pg.typewrite(ln,interval=TYPE_INTERVAL); pg.press("enter"); time.sleep(ENTER_DELAY)
    pg.press("escape")

class AdminCommandsToolkit(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Admin Commands Toolkit")
        self.minsize(520,420)

        # Data
        self.profiles={}; self.current_profile=DEFAULT_PROFILE; self._load_profiles()

        # State
        self.dark_mode=tk.BooleanVar(value=False)
        self.always_on_top=tk.BooleanVar(value=False)
        self.icon_cache={}; self.button_widgets=[]; self.drag={"widget":None,"start":None}
        self.bound_hotkeys=[]

        # Style
        self.style=ttk.Style(self); self.style.theme_use("clam"); self._apply_light()

        # Build UI
        self._build_ui(); self._render_buttons(); self._bind_hotkeys()
    def _apply_light(self):
        self.configure(bg="white")
        self.style.configure(".",background="white",foreground="black",font=BUTTON_FONT)
        self.style.configure("Command.TButton",background="white",foreground="black",
                             wraplength=120,justify="center",padding=(6,8))
        self.style.map("Command.TButton",background=[("active","#dddddd")])
        if hasattr(self,"canvas"):
            self.canvas.configure(bg="white"); self.inner.configure(style="Inner.TFrame")
            self.style.configure("Inner.TFrame",background="white")

    def _apply_dark(self):
        self.configure(bg="#2b2b2b")
        self.style.configure(".",background="#2b2b2b",foreground="white",font=BUTTON_FONT)
        self.style.configure("Command.TButton",background="#444444",foreground="white",
                             wraplength=120,justify="center",padding=(6,8))
        self.style.map("Command.TButton",background=[("active","#666666")])
        if hasattr(self,"canvas"):
            self.canvas.configure(bg="#2b2b2b"); self.inner.configure(style="InnerDark.TFrame")
            self.style.configure("InnerDark.TFrame",background="#2b2b2b")

    def _toggle_theme(self): (self._apply_dark if self.dark_mode.get() else self._apply_light)(); self._render_buttons()

    def _build_ui(self):
        bar=ttk.Frame(self); bar.pack(fill="x",padx=6,pady=6)
        ttk.Checkbutton(bar,text="Dark Mode",variable=self.dark_mode,command=self._toggle_theme).pack(side="left",padx=8)
        ttk.Checkbutton(bar,text="Always on top",variable=self.always_on_top,
                        command=lambda:self.attributes("-topmost",self.always_on_top.get())
                       ).pack(side="left",padx=8)
        ttk.Button(bar,text="⚙️",width=3,command=self._open_settings).pack(side="right")

        body=ttk.Frame(self); body.pack(fill="both",expand=True,padx=8,pady=8)
        self.canvas=tk.Canvas(body,bg="white",bd=0,highlightthickness=0)
        vs=ttk.Scrollbar(body,orient="vertical",command=self.canvas.yview)
        self.inner=ttk.Frame(self.canvas,style="Inner.TFrame")
        self.canvas.create_window((0,0),window=self.inner,anchor="nw")
        self.canvas.configure(yscrollcommand=vs.set)
        self.inner.bind("<Configure>",lambda e:self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.pack(side="left",fill="both",expand=True); vs.pack(side="right",fill="y")

        # Clickable link to your coffee page
        link = tk.Label(self, text="Developed by cobusbo", font=("Segoe UI", 9, "italic"),
                        fg="blue", cursor="hand2", bg=self["bg"])
        link.pack(side="bottom", pady=5)
        link.bind("<Button-1>", lambda e: webbrowser.open_new("https://coff.ee/cobusbo"))

    def _render_buttons(self):
        for w in self.inner.winfo_children(): w.destroy()
        self.button_widgets.clear(); self.icon_cache.clear()
        commands=self.profiles[self.current_profile][:MAX_BUTTON_ROWS*MAX_BUTTON_COLS]

        for i, cmd in enumerate(commands):
            col,row = divmod(i, MAX_BUTTON_ROWS)
            txt = cmd["label"] + (f"\n[{cmd['hotkey']}]" if cmd.get("hotkey") else "")
            btn = ttk.Button(self.inner, text=txt, style="Command.TButton",
                             command=lambda c=cmd["cmd"]: send_command(c))
            btn.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
            btn.bind("<Button-3>", lambda e, idx=i: self._context(idx, e))
            btn.bind("<ButtonPress-1>", self._drag_start)
            btn.bind("<B1-Motion>", self._drag_move)
            btn.bind("<ButtonRelease-1>", self._drag_drop)
            self.button_widgets.append(btn)

            if cmd.get("bgimg"):
                img_path = (BASE_DIR / cmd["bgimg"]).resolve()
                if img_path.is_file():
                    try:
                        img = Image.open(img_path).resize((120, 80), Image.ANTIALIAS)
                        ph = ImageTk.PhotoImage(img)
                        btn.configure(image=ph, compound="center")
                        self.icon_cache[f"ph{i}"] = ph
                    except Exception:
                        pass

        for r in range(MAX_BUTTON_ROWS): self.inner.rowconfigure(r, weight=1)
        for c in range(MAX_BUTTON_COLS): self.inner.columnconfigure(c, weight=1)
    # ── Context‑menu & drag / drop ──
    def _context(self, idx, e):
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="Edit", command=lambda: self._open_settings(idx, "commands"))
        m.add_command(label="Delete", command=lambda: self._del_cmd(idx))
        m.add_separator()
        m.add_command(label="Move Up", command=lambda: self._move(idx, -1))
        m.add_command(label="Move Down", command=lambda: self._move(idx, 1))
        m.tk_popup(e.x_root, e.y_root)

    def _del_cmd(self, idx):
        if messagebox.askyesno("Delete", "Delete command?", parent=self):
            self.profiles[self.current_profile].pop(idx)
            self._save(); self._render_buttons(); self._bind_hotkeys()

    def _move(self, idx, delta):
        cmds = self.profiles[self.current_profile]
        new = idx + delta
        if 0 <= new < len(cmds):
            cmds[idx], cmds[new] = cmds[new], cmds[idx]
            self._save(); self._render_buttons(); self._bind_hotkeys()

    # drag helpers
    # ───────── 1. replace _drag_start ─────────
    def _drag_start(self, e):
        if e.widget in self.button_widgets:
            self.drag = {
                "widget": e.widget,
                "start": self.button_widgets.index(e.widget),
                "x": e.x,
                "y": e.y,
                "moved": False           # ← NEW flag
            }

# ───────── 2. replace _drag_move ─────────
    def _drag_move(self, e):
        w = self.drag.get("widget")
        if w:
            dx, dy = e.x - self.drag["x"], e.y - self.drag["y"]
            # treat as drag only if pointer moved ≥3 px
            if abs(dx) > 3 or abs(dy) > 3:
                self.drag["moved"] = True
                w.place(in_=self.inner,
                        x=w.winfo_x() - self.drag["x"] + e.x,
                        y=w.winfo_y() - self.drag["y"] + e.y)

# ───────── 3. replace _drag_drop ─────────
    def _drag_drop(self, e):
        w, start = self.drag.get("widget"), self.drag.get("start")
        if not w: return

        # If it was just a click (no motion) – do nothing and let the button fire
        if not self.drag.get("moved"):
            self.drag = {"widget": None, "start": None}
            w.place_forget()  # ensure no stray place() residue
            return

        # real drag ‑ find closest target
        closest, dist = None, 1e9
        for i, b in enumerate(self.button_widgets):
            if b is w: continue
            cx, cy = b.winfo_rootx()+b.winfo_width()//2, b.winfo_rooty()+b.winfo_height()//2
            d = (cx - e.x_root)**2 + (cy - e.y_root)**2
            if d < dist: dist, closest = d, i

        if closest is not None and closest != start:
            cmds = self.profiles[self.current_profile]
            cmds.insert(closest, cmds.pop(start))
            self._save()

        w.place_forget()
        self.drag = {"widget": None, "start": None}
        self._render_buttons()
        self._bind_hotkeys()


    # ── Hotkeys & profiles persistence ──
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

    def _load_profiles(self):
        if PROFILES_FILE.exists():
            try: self.profiles = json.loads(PROFILES_FILE.read_text("utf-8"))
            except Exception: self.profiles = {}
        if DEFAULT_PROFILE not in self.profiles:
            self.profiles[DEFAULT_PROFILE] = DEFAULT_COMMANDS.copy()

    def _save(self):
        PROFILES_FILE.write_text(json.dumps(self.profiles, indent=2), encoding="utf-8")

    def _open_settings(self, idx=None, tab="profiles"):
        SettingsWindow(self, idx, tab)


# ────────────────────────────────────────────────────────────
# Settings Window
# ────────────────────────────────────────────────────────────
class SettingsWindow(tk.Toplevel):
    def __init__(self, master: AdminCommandsToolkit, edit_idx=None, tab="profiles"):
        super().__init__(master)
        self.master = master
        self.edit_idx = edit_idx
        self.title("Settings")
        self.geometry("660x540")
        self.transient(master)
        self.grab_set()

        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True, padx=8, pady=8)
        self._build_profiles_tab(nb)
        self._build_commands_tab(nb)
        nb.select(1 if tab == "commands" else 0)
        if edit_idx is not None:
            self.cmd_list.selection_set(edit_idx); self._load_cmd()

    # ── Profiles Tab ──
    def _build_profiles_tab(self, nb):
        f = ttk.Frame(nb); nb.add(f, text="Profiles")

        self.pro_list = tk.Listbox(f, exportselection=False)
        self.pro_list.pack(side="left", fill="both", expand=True, padx=(0, 5), pady=5)
        self.pro_list.bind("<<ListboxSelect>>", lambda _: self._sel_profile())

        pb = ttk.Frame(f); pb.pack(side="right", fill="y", pady=5)
        for txt, cmd in (("New", self._new_p), ("Rename", self._ren_p),
                         ("Delete", self._del_p), ("Import", self._imp),
                         ("Export", self._exp)):
            ttk.Button(pb, text=txt, command=cmd).pack(fill="x", pady=2)

        self._refresh_profiles()

    # profile tab helpers
    def _refresh_profiles(self):
        self.pro_list.delete(0, tk.END)
        for p in self.master.profiles: self.pro_list.insert(tk.END, p)
        idx = list(self.master.profiles).index(self.master.current_profile)
        self.pro_list.select_set(idx)

    def _sel_profile(self):
        sel = self.pro_list.curselection()
        if sel:
            self.master.current_profile = list(self.master.profiles)[sel[0]]
            self._refresh_cmds(); self.master._render_buttons(); self.master._bind_hotkeys()

    def _new_p(self):
        n = simpledialog.askstring("New Profile", "Name:", parent=self)
        if n and n not in self.master.profiles:
            self.master.profiles[n] = []; self.master.current_profile = n
            self._refresh_profiles(); self._refresh_cmds(); self.master._save()

    def _ren_p(self):
        cur = self.master.current_profile
        n = simpledialog.askstring("Rename", "New name:", initialvalue=cur, parent=self)
        if n and n not in self.master.profiles:
            self.master.profiles[n] = self.master.profiles.pop(cur)
            self.master.current_profile = n
            self._refresh_profiles(); self.master._save()

    def _del_p(self):
        if self.master.current_profile == DEFAULT_PROFILE:
            messagebox.showwarning("Protected", "Cannot delete default.", parent=self); return
        if messagebox.askyesno("Delete", f"Delete '{self.master.current_profile}'?", parent=self):
            self.master.profiles.pop(self.master.current_profile)
            self.master.current_profile = list(self.master.profiles)[0]
            self._refresh_profiles(); self._refresh_cmds(); self.master._save()
            self.master._render_buttons(); self.master._bind_hotkeys()

    # import / export
    def _imp(self):
        f = filedialog.askopenfilename(filetypes=[("JSON", "*.json")], parent=self)
        if f:
            try: data = json.load(open(f, "r", encoding="utf-8"))
            except Exception as e: messagebox.showerror("Error", e, parent=self); return
            if isinstance(data, dict): self.master.profiles.update(data)
            self._refresh_profiles(); self.master._save()

    def _exp(self):
        f = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")], parent=self)
        if f: json.dump(self.master.profiles, open(f, "w", encoding="utf-8"), indent=2)

    # ── Commands Tab ──
    def _build_commands_tab(self, nb):
        f = ttk.Frame(nb); nb.add(f, text="Commands")

        self.cmd_list = tk.Listbox(f, exportselection=False)
        self.cmd_list.pack(side="left", fill="both", expand=True, padx=(0, 5), pady=5)
        self.cmd_list.bind("<<ListboxSelect>>", lambda _: self._load_cmd())

        ed = ttk.Frame(f); ed.pack(side="right", fill="both", expand=False, padx=5, pady=5)
        ttk.Label(ed, text="Label").pack(anchor="w")
        self.e_lbl = ttk.Entry(ed); self.e_lbl.pack(fill="x")

        ttk.Label(ed, text="Command(s)").pack(anchor="w")
        self.e_cmd = tk.Text(ed, height=5, wrap="word"); self.e_cmd.pack(fill="both", expand=True)

        ttk.Label(ed, text="Background Image").pack(anchor="w")
        row = ttk.Frame(ed); row.pack(fill="x")
        self.e_bg = ttk.Entry(row); self.e_bg.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="…", width=3, command=lambda: self._browse(self.e_bg)).pack(side="left", padx=2)

        ttk.Label(ed, text="Hotkey (click & press)").pack(anchor="w")
        self.e_hot = ttk.Entry(ed); self.e_hot.pack(fill="x")
        self.e_hot.bind("<FocusIn>", lambda _: self._hk_reset())
        self.e_hot.bind("<Key>", self._hk_capture)
        self._hk_parts = set()

        foot = ttk.Frame(ed); foot.pack(fill="x", pady=6)
        self.b_save = ttk.Button(foot, text="Add", command=self._save_cmd)
        self.b_save.pack(side="left", fill="x", expand=True, padx=2)
        ttk.Button(foot, text="Clear", command=self._clear).pack(side="left", fill="x", expand=True, padx=2)

        self._refresh_cmds()

    # commands-tab helpers
    def _refresh_cmds(self):
        self.cmd_list.delete(0, tk.END)
        for c in self.master.profiles[self.master.current_profile]:
            hk = f" [{c['hotkey']}]" if c.get("hotkey") else ""
            self.cmd_list.insert(tk.END, c["label"] + hk)

    def _load_cmd(self):
        sel = self.cmd_list.curselection()
        if not sel: return
        idx = sel[0]; self.edit_idx = idx
        cmd = self.master.profiles[self.master.current_profile][idx]
        self.e_lbl.delete(0, tk.END); self.e_lbl.insert(0, cmd.get("label", ""))
        self.e_cmd.delete("1.0", tk.END); self.e_cmd.insert(tk.END, cmd.get("cmd", ""))
        self.e_bg.delete(0, tk.END); self.e_bg.insert(0, cmd.get("bgimg", "") or "")
        self.e_hot.delete(0, tk.END); self.e_hot.insert(0, cmd.get("hotkey", ""))
        self.b_save.config(text="Save")

    def _clear(self):
        self.edit_idx = None
        for w in (self.e_lbl, self.e_bg, self.e_hot): w.delete(0, tk.END)
        self.e_cmd.delete("1.0", tk.END)
        self._hk_reset(); self.b_save.config(text="Add"); self.cmd_list.selection_clear(0, tk.END)

    def _save_cmd(self):
        label = self.e_lbl.get().strip(); cmdtxt = self.e_cmd.get("1.0", tk.END).strip()
        bg = self.e_bg.get().strip() or None; hk = self.e_hot.get().strip()
        if not label or not cmdtxt:
            messagebox.showwarning("Input", "Label & command required", parent=self); return
        lst = self.master.profiles[self.master.current_profile]
        new = {"label": label, "cmd": cmdtxt, "bgimg": bg, "hotkey": hk}
        if self.edit_idx is None: lst.append(new)
        else: lst[self.edit_idx] = new
        self.master._save(); self._refresh_cmds()
        self.master._render_buttons(); self.master._bind_hotkeys(); self._clear()

    # hotkey capture helpers
    def _hk_reset(self): self._hk_parts.clear(); self.e_hot.delete(0, tk.END)

    def _hk_capture(self, event):
        k = event.keysym
        if k in ("Shift_L", "Shift_R"): self._hk_parts.add("Shift")
        elif k in ("Control_L", "Control_R"): self._hk_parts.add("Control")
        elif k in ("Alt_L", "Alt_R", "Meta_L", "Meta_R"): self._hk_parts.add("Alt")
        elif k == "BackSpace": self._hk_reset(); return "break"
        else:
            self._hk_parts.add(k.capitalize())
            order = [m for m in ("Control", "Alt", "Shift") if m in self._hk_parts]
            others = [p for p in self._hk_parts if p not in ("Control", "Alt", "Shift")]
            if others: order.append(others[-1])
            self.e_hot.delete(0, tk.END); self.e_hot.insert(0, "-".join(order)); self._hk_parts.clear()
        return "break"

    # browse for bg image
    def _browse(self, entry):
        f = filedialog.askopenfilename(filetypes=[("Images", "*.png;*.jpg;*.gif;*.bmp"), ("All", "*.*")], parent=self)
        if f:
            try:
                p = Path(f)
                try: rel = p.relative_to(BASE_DIR)
                except ValueError: rel = p
                entry.delete(0, tk.END); entry.insert(0, str(rel).replace("\\", "/"))
            except Exception:
                entry.delete(0, tk.END); entry.insert(0, f)

# ── Entry point ──
if __name__ == "__main__":
    _ensure_default_data()
    app = AdminCommandsToolkit()
    app.mainloop()
