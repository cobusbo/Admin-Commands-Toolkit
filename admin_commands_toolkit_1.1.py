import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import pyautogui as pg
import win32gui, win32con, win32process
import psutil, time, json, sys, webbrowser
from pathlib import Path
from PIL import Image, ImageTk

# ───────── Paths & defaults ─────────
BASE_DIR   = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
DATA_DIR   = BASE_DIR / "data"; DATA_DIR.mkdir(exist_ok=True)
PROFILES_FILE = DATA_DIR / "profiles.json"
CONFIG_FILE   = DATA_DIR / "config.json"

DEFAULT_CONFIG = {
    "BUTTON_FONT": ["Segoe UI", 10, "bold"],
    "TYPE_INTERVAL": 0.01,
    "ENTER_DELAY": 0.05,
    "GRID_ROWS": 5,
    "GRID_COLS": 5,
    "WINDOW_ALPHA": 1.0,
    "DARK_MODE": False,
    "ON_TOP": False
}

DEFAULT_PROFILE = "Admin Cmds"
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
        PROFILES_FILE.write_text(json.dumps({DEFAULT_PROFILE: DEFAULT_COMMANDS}, indent=2), encoding="utf-8")

def _ensure_default_config():
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")

def _load_config():
    _ensure_default_config()
    try:
        return json.loads(CONFIG_FILE.read_text("utf-8"))
    except Exception:
        return DEFAULT_CONFIG.copy()

def _save_config(cfg): CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

# ───────── SCUM helpers ─────────
def _find_scum_window(exe="SCUM.exe"):
    tgt = None
    def _enum(hwnd, _):
        nonlocal tgt
        if win32gui.IsWindowVisible(hwnd) and win32gui.IsWindowEnabled(hwnd):
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                if psutil.Process(pid).name().lower() == exe.lower():
                    tgt = hwnd; return False
            except psutil.Error:
                pass
        return True
    win32gui.EnumWindows(_enum, None); return tgt

def _bring_game():  # returns True if window found
    h = _find_scum_window()
    if not h: return False
    win32gui.ShowWindow(h, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(h); return True

def send_command(block: str, t_interval=0.01, e_delay=0.05):
    if not _bring_game():
        messagebox.showerror("Error", "SCUM window not found."); return
    time.sleep(0.2); pg.press("t"); time.sleep(0.1)
    for line in filter(None, (l.strip() for l in block.splitlines())):
        pg.typewrite(line, interval=t_interval); pg.press("enter"); time.sleep(e_delay)
    pg.press("escape")

# ───────── Main App ─────────
class AdminCommandsToolkit(tk.Tk):
    def __init__(self):
        super().__init__()
        self.config_data = _load_config()
        self.title("Admin Commands Toolkit")
        self.minsize(560, 450)

        # Tk variables linked to config
        self.dark   = tk.BooleanVar(value=self.config_data["DARK_MODE"])
        self.on_top = tk.BooleanVar(value=self.config_data["ON_TOP"])
        self.alpha  = tk.DoubleVar(value=self.config_data["WINDOW_ALPHA"])

        # Profiles
        _ensure_default_profiles()
        try:
            self.profiles = json.loads(PROFILES_FILE.read_text("utf-8"))
        except Exception:
            self.profiles = {DEFAULT_PROFILE: DEFAULT_COMMANDS}
        self.current_profile = next(iter(self.profiles))

        # Style / theme
        self.style = ttk.Style(self); self.style.theme_use("clam")

        # Internal state
        self.icon_cache, self.button_widgets = {}, []
        self.drag = {"widget": None, "start": None, "moved": False}
        self.bound_hotkeys = []

        # Build UI
        self._build_ui()
        (self._apply_dark if self.dark.get() else self._apply_light)()
        self._render_buttons(); self._bind_hotkeys()

        # live variable traces
        self.dark.trace_add("write", self._on_dark_change)
        self.on_top.trace_add("write", self._on_top_change)
        self.alpha.trace_add("write", self._on_alpha_change)

        self.attributes("-alpha", self.alpha.get())
        self.attributes("-topmost", self.on_top.get())
    # ─── UI build ───
    def _build_ui(self):
        # Top bar: settings + add-command
        top = ttk.Frame(self); top.pack(fill="x", padx=6, pady=(6,2))
        ttk.Button(top, text="＋", width=3,
                   command=lambda: self._open_settings(None, "commands")
                   ).pack(side="right", padx=(0,2))
        ttk.Button(top, text="⚙️ Settings", command=self._open_settings
                   ).pack(side="right")

        # Profile tabs
        self.tabs = ttk.Notebook(self); self.tabs.pack(fill="x", padx=6, pady=(0,4))
        self.tabs.bind("<<NotebookTabChanged>>", lambda *_: self._tab_changed())
        self._refresh_tabs()

        # Scrollable grid
        body = ttk.Frame(self); body.pack(fill="both", expand=True, padx=8, pady=8)
        self.canvas = tk.Canvas(body, bg="white", highlightthickness=0)
        vbar = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg="white")              # TK frame → bg can change
        self.canvas.create_window((0,0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=vbar.set)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.pack(side="left", fill="both", expand=True); vbar.pack(side="right", fill="y")

        # Footer link
        link = tk.Label(self, text="Developed by cobusbo", font=("Segoe UI",9,"italic"),
                        fg="blue", cursor="hand2", bg=self["bg"])
        link.pack(side="bottom", pady=4)
        link.bind("<Button-1>", lambda e: webbrowser.open_new("https://coff.ee/cobusbo"))

    # ─── Theme helpers ───
    def _button_font(self): f=self.config_data["BUTTON_FONT"]; return (f[0], int(f[1]), f[2])

    def _apply_theme_to_widget(self, w, dark):
        bg_d, fg_d, bg_l, fg_l = "#1e1e1e","white","white","black"
        for c in w.winfo_children():
            self._apply_theme_to_widget(c, dark)
        cls=w.__class__.__name__
        if cls in ("Entry","Text","Listbox","Canvas"):
            if cls=="Entry":
                w.configure(bg=bg_d if dark else bg_l, fg=fg_d if dark else fg_l,
                            insertbackground=fg_d if dark else fg_l)
            elif cls=="Text":
                w.configure(bg=bg_d if dark else bg_l, fg=fg_d if dark else fg_l,
                            insertbackground=fg_d if dark else fg_l)
            elif cls=="Listbox":
                w.configure(bg=bg_d if dark else bg_l, fg=fg_d if dark else fg_l,
                            selectbackground="#5a5a5a" if dark else "#cccccc")
            elif cls=="Canvas":
                w.configure(bg=bg_d if dark else bg_l)

    def _apply_light(self):
        self.configure(bg="white")
        self.style.configure(".", background="white", foreground="black", font=self._button_font())
        self.style.configure("Command.TButton", background="white", foreground="black",
                             wraplength=120, justify="center", padding=(6,8))
        if hasattr(self,"inner"): self.inner.configure(bg="white"); self.canvas.configure(bg="white")
        self._apply_theme_to_widget(self,False)

    def _apply_dark(self):
        self.configure(bg="#2b2b2b")
        self.style.configure(".", background="#2b2b2b", foreground="white", font=self._button_font())
        self.style.configure("Command.TButton", background="#444444", foreground="white",
                             wraplength=120, justify="center", padding=(6,8))
        if hasattr(self,"inner"): self.inner.configure(bg="#1e1e1e"); self.canvas.configure(bg="#2b2b2b")
        self._apply_theme_to_widget(self,True)

    # ─── Tabs & buttons ───
    def _refresh_tabs(self):
        for t in self.tabs.tabs(): self.tabs.forget(t)
        for name in self.profiles: self.tabs.add(ttk.Frame(self.tabs), text=name)
        self.tabs.select(list(self.profiles).index(self.current_profile))

    def _tab_changed(self):
        self.current_profile = list(self.profiles)[self.tabs.index(self.tabs.select())]
        self._render_buttons(); self._bind_hotkeys()

    def _render_buttons(self):
        for w in self.inner.winfo_children(): w.destroy()
        self.button_widgets.clear(); self.icon_cache.clear()
        rows=self.config_data["GRID_ROWS"]; cols=self.config_data["GRID_COLS"]
        cmds=self.profiles[self.current_profile][:rows*cols]
        for i,cmd in enumerate(cmds):
            col,row=divmod(i,rows)
            txt=cmd["label"]+(f"\n[{cmd['hotkey']}]" if cmd.get("hotkey") else "")
            btn=ttk.Button(self.inner,text=txt,style="Command.TButton",
                command=lambda c=cmd["cmd"]: send_command(c,
                        self.config_data["TYPE_INTERVAL"], self.config_data["ENTER_DELAY"]))
            btn.grid(row=row,column=col,padx=4,pady=4,sticky="nsew")
            btn.bind("<Button-3>",lambda e,idx=i:self._menu(idx,e))
            btn.bind("<ButtonPress-1>",self._drag_start)
            btn.bind("<B1-Motion>",self._drag_move)
            btn.bind("<ButtonRelease-1>",self._drag_drop)
            self.button_widgets.append(btn)
            if cmd.get("bgimg"):
                p=(BASE_DIR/cmd["bgimg"]).resolve()
                if p.is_file():
                    try:
                        ph=ImageTk.PhotoImage(Image.open(p).resize((120,80),Image.ANTIALIAS))
                        btn.configure(image=ph,compound="center"); self.icon_cache[str(p)]=ph
                    except: pass
        for r in range(rows): self.inner.rowconfigure(r,weight=1)
        for c in range(cols): self.inner.columnconfigure(c,weight=1)

    # Context & drag-n-drop
    def _menu(self,idx,e):
        m=tk.Menu(self,tearoff=0)
        m.add_command(label="Edit",command=lambda: self._open_settings(idx,"commands"))
        m.add_command(label="Delete",command=lambda: self._del_cmd(idx))
        m.tk_popup(e.x_root,e.y_root)

    def _del_cmd(self,idx):
        if messagebox.askyesno("Delete","Delete command?",parent=self):
            self.profiles[self.current_profile].pop(idx); self._save_profiles()
            self._render_buttons(); self._bind_hotkeys()

    def _drag_start(self,e):
        if e.widget in self.button_widgets:
            self.drag={"widget":e.widget,"start":self.button_widgets.index(e.widget),"x":e.x,"y":e.y,"moved":False}
    def _drag_move(self,e):
        w=self.drag["widget"]
        if w:
            dx,dy=e.x-self.drag["x"], e.y-self.drag["y"]
            if abs(dx)>3 or abs(dy)>3: self.drag["moved"]=True
            if self.drag["moved"]:
                w.place(in_=self.inner,x=w.winfo_x()-self.drag["x"]+e.x,
                        y=w.winfo_y()-self.drag["y"]+e.y)
    def _drag_drop(self,e):
        w,start=self.drag["widget"],self.drag["start"]; 
        if not w: return
        if not self.drag["moved"]:
            w.place_forget(); self.drag={"widget":None,"start":None}; return
        closest,dist=None,1e9
        for i,b in enumerate(self.button_widgets):
            if b is w: continue
            cx,cy=b.winfo_rootx()+b.winfo_width()//2, b.winfo_rooty()+b.winfo_height()//2
            d=(cx-e.x_root)**2+(cy-e.y_root)**2
            if d<dist: closest,dist=i,d
        if closest is not None and closest!=start:
            cmds=self.profiles[self.current_profile]
            cmds.insert(closest,cmds.pop(start)); self._save_profiles()
        w.place_forget(); self.drag={"widget":None,"start":None}
        self._render_buttons(); self._bind_hotkeys()

    # Hotkeys
    def _bind_hotkeys(self):
        for hk in self.bound_hotkeys: self.unbind_all(hk)
        self.bound_hotkeys.clear()
        for cmd in self.profiles[self.current_profile]:
            hk=cmd.get("hotkey","").strip()
            if hk:
                try:
                    self.bind_all(f"<{hk}>",
                        lambda e,c=cmd["cmd"]: (send_command(c,
                            self.config_data["TYPE_INTERVAL"], self.config_data["ENTER_DELAY"]), "break"))
                    self.bound_hotkeys.append(f"<{hk}>")
                except: pass

    # Save profiles
    def _save_profiles(self): PROFILES_FILE.write_text(json.dumps(self.profiles,indent=2),encoding="utf-8")

    # Settings window
    def _open_settings(self,idx=None,tab="general"): SettingsWindow(self,idx,tab)

    # Config var callbacks
    def _on_dark_change(self,*a):
        self.config_data["DARK_MODE"]=self.dark.get(); self._apply_dark() if self.dark.get() else self._apply_light()
        self._render_buttons(); _save_config(self.config_data)
    def _on_top_change(self,*a):
        val=self.on_top.get(); self.config_data["ON_TOP"]=val; self.attributes("-topmost",val); _save_config(self.config_data)
    def _on_alpha_change(self,*a):
        val=self.alpha.get(); self.config_data["WINDOW_ALPHA"]=val; self.attributes("-alpha",val); _save_config(self.config_data)
class SettingsWindow(tk.Toplevel):
    FONT_FAMILIES = ["Segoe UI","Arial","Calibri","Tahoma","Verdana",
                     "Times New Roman","Courier New"]
    FONT_WEIGHTS  = ["normal","bold"]

    def __init__(self, master: AdminCommandsToolkit, edit_idx=None, tab="general"):
        super().__init__(master)
        self.master=master; self.edit_idx=edit_idx
        self.title("Settings"); self.geometry("700x650"); self.transient(master); self.grab_set()

        self.entries={}
        nb=ttk.Notebook(self); nb.pack(fill="both",expand=True,padx=8,pady=8)
        self._build_general_tab(nb); self._build_profiles_tab(nb); self._build_commands_tab(nb)
        nb.select({"general":0,"profiles":1,"commands":2}[tab])

        self.master._apply_theme_to_widget(self, self.master.dark.get())
        if edit_idx is not None: self.cmd_list.selection_set(edit_idx); self._load_cmd()

    # ─── General tab ───
    def _build_general_tab(self,nb):
        f=ttk.Frame(nb); nb.add(f,text="General"); f.columnconfigure(1,weight=1)
        cd=self.master.config_data
        # Font family dropdown
        ttk.Label(f,text="Button Font Family:").grid(row=0,column=0,sticky="w",pady=3)
        fam=ttk.Combobox(f,values=self.FONT_FAMILIES,state="readonly")
        fam.set(cd["BUTTON_FONT"][0]); fam.grid(row=0,column=1,sticky="ew",pady=3)
        self.entries["BUTTON_FONT_family"]=fam
        # Font size
        ttk.Label(f,text="Button Font Size:").grid(row=1,column=0,sticky="w",pady=3)
        fs=tk.Entry(f); fs.insert(0,cd["BUTTON_FONT"][1]); fs.grid(row=1,column=1,sticky="ew",pady=3)
        self.entries["BUTTON_FONT_size"]=fs
        # Font weight dropdown
        ttk.Label(f,text="Button Font Weight:").grid(row=2,column=0,sticky="w",pady=3)
        fw=ttk.Combobox(f,values=self.FONT_WEIGHTS,state="readonly")
        fw.set(cd["BUTTON_FONT"][2]); fw.grid(row=2,column=1,sticky="ew",pady=3)
        self.entries["BUTTON_FONT_weight"]=fw
        # Type / Enter
        for idx,key,label in [(3,"TYPE_INTERVAL","Typing Interval (sec):"),
                              (4,"ENTER_DELAY","Enter Delay (sec):"),
                              (5,"GRID_ROWS","Grid Rows:"),
                              (6,"GRID_COLS","Grid Columns:")]:
            ttk.Label(f,text=label).grid(row=idx,column=0,sticky="w",pady=3)
            e=tk.Entry(f); e.insert(0,str(cd[key])); e.grid(row=idx,column=1,sticky="ew",pady=3)
            self.entries[key]=e
        # Dark & on-top checkboxes
        ttk.Checkbutton(f,text="Dark Mode",variable=self.master.dark).grid(row=7,column=0,sticky="w",pady=3)
        ttk.Checkbutton(f,text="Always on Top",variable=self.master.on_top).grid(row=7,column=1,sticky="w",pady=3)
        # Transparency slider
        ttk.Label(f,text="Window Transparency:").grid(row=8,column=0,sticky="w",pady=3)
        self.alpha_scale=ttk.Scale(f,from_=0.1,to=1.0,orient="horizontal")
        self.alpha_scale.set(cd["WINDOW_ALPHA"]); self.alpha_scale.grid(row=8,column=1,sticky="ew",pady=3)
        self.alpha_scale.bind("<Motion>",self._alpha_move); self.alpha_scale.bind("<ButtonRelease-1>",self._alpha_move)
        # Save
        ttk.Button(f,text="Save Settings",command=self._save_general).grid(row=9,column=0,columnspan=2,sticky="ew",pady=10)

    def _alpha_move(self,e=None):
        val=self.alpha_scale.get(); self.master.alpha.set(val)

    def _save_general(self):
        cd=self.master.config_data
        try:
            cd["BUTTON_FONT"]=[ self.entries["BUTTON_FONT_family"].get(),
                                int(self.entries["BUTTON_FONT_size"].get()),
                                self.entries["BUTTON_FONT_weight"].get() ]
            cd["TYPE_INTERVAL"]=float(self.entries["TYPE_INTERVAL"].get())
            cd["ENTER_DELAY"]=float(self.entries["ENTER_DELAY"].get())
            cd["GRID_ROWS"]=int(self.entries["GRID_ROWS"].get())
            cd["GRID_COLS"]=int(self.entries["GRID_COLS"].get())
        except Exception as e:
            messagebox.showerror("Error","Invalid input: "+str(e),parent=self); return
        _save_config(cd); self.master._render_buttons(); messagebox.showinfo("Saved","Settings saved.",parent=self)

    # ─── Profiles tab ───
    def _build_profiles_tab(self,nb):
        f=ttk.Frame(nb); nb.add(f,text="Profiles")
        self.pro_list=tk.Listbox(f,exportselection=False,height=10)
        self.pro_list.pack(fill="both",expand=True,padx=8,pady=8)
        self._refresh_profiles()
        tf=ttk.Frame(f); tf.pack(fill="x",pady=4)
        for label,cmd in [("Add",self._add_prof),("Rename",self._ren_prof),("Delete",self._del_prof)]:
            ttk.Button(tf,text=label,command=cmd).pack(side="left",padx=4)
    def _refresh_profiles(self):
        self.pro_list.delete(0,"end")
        for p in self.master.profiles: self.pro_list.insert("end",p)
        try: self.pro_list.select_set(list(self.master.profiles).index(self.master.current_profile))
        except: pass
    def _add_prof(self):
        n=simpledialog.askstring("New Profile","Name:",parent=self)
        if n and n not in self.master.profiles:
            self.master.profiles[n]=[]; self.master.current_profile=n
            self.master._save_profiles(); self._refresh_profiles(); self.master._refresh_tabs()
    def _ren_prof(self):
        sel=self.pro_list.curselection(); 
        if not sel: return
        cur=self.pro_list.get(sel[0])
        n=simpledialog.askstring("Rename","New name:",initialvalue=cur,parent=self)
        if n and n not in self.master.profiles:
            self.master.profiles[n]=self.master.profiles.pop(cur)
            self.master.current_profile=n
            self.master._save_profiles(); self._refresh_profiles(); self.master._refresh_tabs()
    def _del_prof(self):
        if len(self.master.profiles)==1: messagebox.showwarning("Protected","At least one profile required.",parent=self); return
        sel=self.pro_list.curselection(); 
        if not sel: return
        cur=self.pro_list.get(sel[0])
        if messagebox.askyesno("Delete",f"Delete '{cur}'?",parent=self):
            self.master.profiles.pop(cur)
            self.master.current_profile=next(iter(self.master.profiles))
            self.master._save_profiles(); self._refresh_profiles(); self.master._refresh_tabs()
    # ─── Commands tab ───
    def _build_commands_tab(self,nb):
        f=ttk.Frame(nb); nb.add(f,text="Commands")
        self.cmd_list=tk.Listbox(f,height=12); self.cmd_list.pack(side="left",fill="both",expand=True,padx=(8,4),pady=8)
        self.cmd_list.bind("<<ListboxSelect>>",lambda *_: self._load_cmd())
        btns=ttk.Frame(f); btns.pack(side="right",fill="y",padx=4,pady=8)
        for lab,cmd in [("Add",self._add_cmd),("Delete",self._del_cmd),("Save",self._save_cmd)]:
            ttk.Button(btns,text=lab,command=cmd,width=10).pack(pady=2)
        # Edit pane
        edit=ttk.Frame(f); edit.pack(fill="both",expand=True,padx=8,pady=8)
        ttk.Label(edit,text="Label:").grid(row=0,column=0,sticky="w")
        self.e_lbl=tk.Entry(edit); self.e_lbl.grid(row=0,column=1,sticky="ew")
        ttk.Label(edit,text="Command Text:").grid(row=1,column=0,sticky="nw")
        self.e_cmd=tk.Text(edit,height=6,wrap="word"); self.e_cmd.grid(row=1,column=1,sticky="ew")
        ttk.Label(edit,text="Hotkey:").grid(row=2,column=0,sticky="w")
        self.e_hot=tk.Entry(edit); self.e_hot.grid(row=2,column=1,sticky="w")
        edit.columnconfigure(1,weight=1)
        self._refresh_cmds()
        self.current_cmd_idx=None

    def _refresh_cmds(self):
        self.cmd_list.delete(0,"end")
        for c in self.master.profiles[self.master.current_profile]:
            self.cmd_list.insert("end",c["label"])

    def _add_cmd(self):
        self.master.profiles[self.master.current_profile].append({"label":"New","cmd":"","hotkey":"","bgimg":None})
        self._refresh_cmds(); self.cmd_list.selection_clear(0,"end"); self.cmd_list.selection_set("end")
        self._load_cmd(); self.master._save_profiles()

    def _del_cmd(self):
        sel=self.cmd_list.curselection()
        if not sel: return
        idx=sel[0]
        self.master.profiles[self.master.current_profile].pop(idx)
        self._refresh_cmds(); self._clear_edit(); self.master._save_profiles(); self.master._render_buttons(); self.master._bind_hotkeys()

    def _load_cmd(self):
        sel=self.cmd_list.curselection()
        if not sel: return
        idx=sel[0]; self.current_cmd_idx=idx
        cmd=self.master.profiles[self.master.current_profile][idx]
        self.e_lbl.delete(0,"end"); self.e_lbl.insert(0,cmd["label"])
        self.e_cmd.delete("1.0","end"); self.e_cmd.insert("1.0",cmd["cmd"])
        self.e_hot.delete(0,"end"); self.e_hot.insert(0,cmd.get("hotkey",""))

    def _save_cmd(self):
        if self.current_cmd_idx is None: return
        lbl=self.e_lbl.get().strip(); txt=self.e_cmd.get("1.0","end").strip(); hk=self.e_hot.get().strip()
        if not lbl or not txt: messagebox.showerror("Input","Label & command required.",parent=self); return
        self.master.profiles[self.master.current_profile][self.current_cmd_idx].update({"label":lbl,"cmd":txt,"hotkey":hk})
        self._refresh_cmds(); self.master._save_profiles(); self.master._render_buttons(); self.master._bind_hotkeys()

    def _clear_edit(self):
        for w in (self.e_lbl,self.e_hot): w.delete(0,"end")
        self.e_cmd.delete("1.0","end"); self.current_cmd_idx=None

if __name__=="__main__":
    _ensure_default_profiles(); _ensure_default_config()
    AdminCommandsToolkit().mainloop()
