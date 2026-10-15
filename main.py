#!/usr/bin/env python3
"""Config editor (ini) for the C++ cellular automaton program."""
import itertools
import json
import math
import copy
import os
import time
import tkinter as tk
import tkinter.font as tkfont
from collections import Counter
from tkinter import ttk, filedialog, messagebox

from configobj import ConfigObj

APP_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(APP_DIR, "form_state.json")
DEFAULT_FILE = os.path.join(APP_DIR, "default_stat.json")
DEFAULT_STATE = {
    "geometry": "1011x540+1330+178",
    "recent": [],
    "last_ini": None,
}
LETTERS = "NRGB"
SIZES = [128, 256, 512, 1024, 2048, 4096, 8192, 16384]


def layers_for(size):
    return int(math.log2(size)) - 1


def next3(c):
    return 1 if c == 3 else c + 1


def quad_str(code):
    return "".join(LETTERS[(code >> (2 * i)) & 3] for i in range(4))


def code_from_str(s):
    v = 0
    for i, ch in enumerate(s):
        v |= LETTERS.index(ch) << (2 * i)
    return v


def all_quads():
    return [quad_str(i) for i in range(256)]


def perms_of_multiset(s):
    return sorted(set("".join(p) for p in itertools.permutations(s)))


def parse_float(s):
    """Accept both '.' and ',' as decimal separator."""
    return float(str(s).strip().replace(",", "."))


def fmt_float(x):
    return f"{x:g}"


# ---------------------------------------------------------------- ProcUp ---
def default_procup_table():
    """256-digit string; position = input quad code."""
    tbl = []
    for code in range(256):
        s = quad_str(code)
        cnt = Counter(s)
        ne_cnt = 4 - cnt["N"]
        ne = [c for c in cnt if c != "N"]
        out = "N"
        if ne_cnt == 2:
            if len(ne) == 2:
                x, y = ne
                if next3(LETTERS.index(x)) == LETTERS.index(y):
                    out = y          # XYNN -> Y
                else:
                    out = x          # Y is predecessor of X (XXZ-like pair)
        elif ne_cnt == 3:
            if len(ne) == 2:  # 2+1
                x = max(ne, key=lambda c: cnt[c])
                y = [c for c in ne if cnt[c] == 1][0]
                if next3(next3(LETTERS.index(x))) == LETTERS.index(y):
                    out = x          # XXZ -> X
                # XXY -> N
        return_ = LETTERS.index(out)
        tbl.append(return_)
    return "".join(map(str, tbl))


PROCUP_LEVEL1 = [
    "0", "1", "2", "3 mask", "3", "4 mask", "4",
]


def mask_expand(mask):
    """Expand mask (with XYZ letters) into concrete quad strings."""
    outs = set()
    for x in "RGB":
        sub = {"X": x}
        if "Y" in mask:
            sub["Y"] = LETTERS[next3(LETTERS.index(x))]
        if "Z" in mask:
            sub["Z"] = LETTERS[next3(next3(LETTERS.index(x)))]
        outs.add("".join(sub.get(ch, ch) for ch in mask))
    return sorted(outs)


def level2_items(l1):
    return {
        "0": ["NNNN"],
        "1": ["XNNN", "RNNN", "GNNN", "BNNN"],
        "2": ["XXNN", "XYNN", "RRNN", "GGNN", "BBNN", "RGNN", "GBNN", "BRNN"],
        "3 mask": ["XXXN", "XXYN", "XXZN", "XYZN"],
        "3": ["RRRN", "RRGN", "RRBN", "GGGN", "GGBN", "GGRN",
              "BBBN", "BBRN", "BBGN", "RGBN"],
        "4 mask": ["XXXX", "XXXY", "XXXZ", "XXYZ"],
        "4": ["RRRR", "RRRG", "RRRB", "RRGB", "GGGG", "GGGB",
              "GGGR", "GGBR", "BBBB", "BBBR", "BBBG", "BBRG"],
    }[l1]


# ---------------------------------------------------------------- ProcDn ---
# positions 0=(0,0) 1=(0,1) 2=(1,0) 3=(1,1), string order = row-major
ROT = [1, 3, 0, 2]     # new[ROT[i]] = old[i]  (90 cw)
MIR = [1, 0, 3, 2]     # horizontal mirror


def compose(p1, p2):
    return [p2[p1[i]] for i in range(4)]


def d4_group():
    def pow_perm(p, k):
        r = [0, 1, 2, 3]
        for _ in range(k):
            r = compose(r, p)
        return r
    group = []
    for k in range(4):
        group.append((pow_perm(ROT, k), False))       # rotation: no flip
    for k in range(4):
        group.append((compose(MIR, pow_perm(ROT, k)), True))  # mirror: flip
    return group


D4 = d4_group()


def apply_perm(perm, s):
    new = [""] * 4
    for i in range(4):
        new[perm[i]] = s[i]
    return "".join(new)


def transform_vals(v, flip):
    v = list(v)
    if flip:
        for i in range(4, 8):
            v[i] = -v[i]
    return v


def template_matches(q, t):
    a = lambda c: c != "N"
    if t == "NNNN":
        return q == "NNNN"
    if t == "ANNN":
        return a(q[0]) and q[1] == q[2] == q[3] == "N"
    if t == "XXNN":
        return a(q[0]) and a(q[1]) and q[0] == q[1] and q[2] == q[3] == "N"
    if t == "XYNN":
        return a(q[0]) and a(q[1]) and q[0] != q[1] and q[2] == q[3] == "N"
    if t == "XNYN":
        return a(q[0]) and a(q[2]) and q[0] != q[2] and q[1] == q[3] == "N"
    if t == "AAAN":
        return a(q[0]) and q[0] == q[1] == q[2] and q[3] == "N"
    if t == "AAAA":
        return all(a(c) for c in q)
    return False


def quad_template(q):
    for t in TEMPLATES:
        if template_matches(q, t):
            return t
    return None


TEMPLATES = ["NNNN", "ANNN", "XXNN", "XYNN", "XNYN", "AAAN", "AAAA"]
CONCRETE_BASES = ["NNNN", "RNNN", "GNNN", "BNNN", "RRNN", "GGNN", "BBNN",
                  "RGNN", "GBNN", "BRNN", "RNGN", "GNBN", "BNRN"]


def template_quads(tmpl):
    return [q for q in all_quads() if template_matches(q, tmpl)]


def expand_forces(edited):
    """edited: dict quad->8 signed indices. Returns dict for all 256 quads."""
    result = {q: [0] * 8 for q in all_quads()}
    assigned = set()
    for q, v in edited.items():
        result[q] = list(v)
        assigned.add(q)
    for q, v in edited.items():
        for perm, flip in D4:
            t = apply_perm(perm, q)
            if t not in assigned:
                result[t] = transform_vals(v, flip)
                assigned.add(t)
    return result


def orbit_of(q):
    return {apply_perm(perm, q) for perm, _ in D4}


FDN_LABELS = ["Radial center empty", "Radial edge empty",
              "Radial center full", "Radial edge full",
              "Circular center empty", "Circular edge empty",
              "Circular center full", "Circular edge full"]

DEFAULT_TABLEF = [0.0, 0.05, 0.1, 0.2, 0.33, 0.5, 0.71, 1.0]


# ------------------------------------------------------------- defaults ---
def default_cfg():
    size = 128
    nl = layers_for(size)
    return {
        "General": {
            "AppLeft": "100", "AppTop": "100",
            "AppWidth": "800", "AppHeight": "600",
        },
        "Gener": {
            "FieldSize": str(size),
            "PointsMode": "Count",
            "PointsR": "300", "PointsG": "300", "PointsB": "400",
            "Distrib": "Uniform",
            "NormalX": "0", "NormalY": "0",
            "NormalSX": "10", "NormalSY": "10",
            "Areas": "0,0,10,10",
            "Weights": " ".join("1.0" for _ in range(nl)),
        },
        "ProcUp": {
            "Table": default_procup_table(),
        },
        "ProcDn": {
            "TableF": " ".join(str(v) for v in DEFAULT_TABLEF),
            "UseTemplates": "True",
        },
    }


def load_defaults():
    try:
        with open(DEFAULT_FILE) as f:
            return json.load(f)
    except Exception:
        return default_cfg()


def load_cfg(path):
    if not os.path.exists(path):
        cfg = load_defaults()
        co = ConfigObj()
        for sec, items in cfg.items():
            co[sec] = items
        co.filename = path
        co.write()
        return ConfigObj(path)
    return ConfigObj(path)


def cfg_to_nested(co):
    d = {}
    for sec in co.sections:
        d[sec] = {k: co[sec][k] for k in co[sec].scalars}
    base = default_cfg()
    for sec in base:
        d.setdefault(sec, {})
        for k, v in base[sec].items():
            d[sec].setdefault(k, v)
    return d


def write_ini_with_retry(path, co):
    deadline = time.time() + 3.0
    last_err = None
    while time.time() < deadline:
        try:
            co.filename = path
            co.write()
            return True
        except OSError as e:
            last_err = e
            time.sleep(0.2)
    messagebox.showwarning(
        "File busy",
        f"Cannot write {path}:\n{last_err}\nThe ini file is locked by the CA program.")
    return False


# ------------------------------------------------------------------ app ---
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FormOptions HighPit")
        self.state = self.load_state()
        geo = self.state.get("geometry")
        if geo:
            self.geometry(geo)
        self.current_path = self.state.get("last_ini") or \
            os.path.join(APP_DIR, "ca.ini")
        self.cfg = cfg_to_nested(load_cfg(self.current_path))

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        btns = ttk.Frame(self)
        btns.pack(fill="x")
        ttk.Button(btns, text="Close", command=self.on_close).pack(side="right", padx=4, pady=4)
        ttk.Button(btns, text="Apply", command=self.on_apply).pack(side="right", padx=4, pady=4)
        ttk.Button(btns, text="Cancel", command=self.on_cancel).pack(side="right", pady=4)

        self.nb = ttk.Notebook(body)
        self.nb.pack(fill="both", expand=True)
        self.tab_general = GeneralTab(self.nb, self)
        self.tab_gener = GenerTab(self.nb, self)
        self.tab_up = ProcUpTab(self.nb, self)
        self.tab_dn = ProcDnTab(self.nb, self)
        self.nb.add(self.tab_general, text="General")
        self.nb.add(self.tab_gener, text="Gener")
        self.nb.add(self.tab_up, text="Proc Up")
        self.nb.add(self.tab_dn, text="Proc Dn")

        self._geo_job = None
        self.bind("<Configure>", self.on_configure)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.refresh_all()

    # -- state / geometry -------------------------------------------------
    def load_state(self):
        st = dict(DEFAULT_STATE)
        try:
            with open(STATE_FILE) as f:
                st.update(json.load(f))
        except Exception:
            pass
        return st

    def save_state(self):
        st = {
            "geometry": f"{self.winfo_width()}x{self.winfo_height()}"
                        f"+{self.winfo_x()}+{self.winfo_y()}",
            "recent": self.state.get("recent", []),
            "last_ini": self.current_path,
            "defaults": default_cfg(),
        }
        try:
            with open(STATE_FILE, "w") as f:
                json.dump(st, f, indent=2)
        except OSError:
            pass
        self.state = st

    def on_configure(self, _e):
        if self._geo_job:
            self.after_cancel(self._geo_job)
        self._geo_job = self.after(500, self.save_state)

    def push_recent(self, path):
        recent = [p for p in self.state.get("recent", []) if p != path]
        recent.insert(0, path)
        self.state["recent"] = recent[:10]
        self.save_state()

    # -- data flow ----------------------------------------------------------
    def open_ini(self, path):
        if not path:
            return
        if not os.path.exists(path):
            if not messagebox.askyesno(
                    "Create file",
                    f"File not found:\n{path}\n\nCreate it with default values?"):
                return
        try:
            self.cfg = cfg_to_nested(load_cfg(path))
        except Exception as e:
            messagebox.showerror("Open error", str(e))
            return
        self.current_path = path
        self.push_recent(path)
        self.refresh_all()

    def refresh_all(self):
        self.tab_general.load(self.cfg)
        self.tab_gener.load(self.cfg)
        self.tab_up.load(self.cfg)
        self.tab_dn.load(self.cfg)
        self.saved_cfg = copy.deepcopy(self.cfg)

    def is_dirty(self):
        tmp = copy.deepcopy(self.cfg)
        try:
            self.tab_general.collect(tmp)
            self.tab_gener.collect(tmp)
            self.tab_up.collect(tmp)
            self.tab_dn.collect(tmp)
        except ValueError:
            return True
        return tmp != self.saved_cfg

    def on_apply(self):
        try:
            self.tab_general.collect(self.cfg)
            self.tab_gener.collect(self.cfg)
            self.tab_up.collect(self.cfg)
            self.tab_dn.collect(self.cfg)
        except ValueError as e:
            messagebox.showerror("Invalid value", str(e))
            return
        co = ConfigObj()
        for sec, items in self.cfg.items():
            co[sec] = {k: str(v) for k, v in items.items()}
        path = self.current_path or os.path.join(APP_DIR, "ca.ini")
        if write_ini_with_retry(path, co):
            self.current_path = path
            self.push_recent(path)
            self.saved_cfg = copy.deepcopy(self.cfg)

    def on_cancel(self):
        if self.current_path:
            self.cfg = cfg_to_nested(load_cfg(self.current_path))
        self.refresh_all()

    def on_close(self):
        if self.is_dirty():
            ans = messagebox.askyesnocancel(
                "Close",
                "There are unsaved changes.\nSave them before closing?")
            if ans is None:
                return
            if ans:
                self.on_apply()
        self.save_state()
        self.destroy()


# --------------------------------------------------------------- General ---
class GeneralTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=8)
        self.app = app
        ttk.Label(self, text="Current ini file:").grid(row=0, column=0, sticky="w")
        self.lbl_path = ttk.Label(self, text="-")
        self.lbl_path.grid(row=0, column=1, sticky="w")
        ttk.Button(self, text="Open...", command=self.open_dialog).grid(
            row=0, column=2, padx=4)

        ttk.Label(self, text="Recent files:").grid(row=1, column=0, sticky="nw")
        self.lst = tk.Listbox(self, height=10, width=60)
        self.lst.grid(row=1, column=1, columnspan=2, sticky="we")
        self.lst.bind("<Double-Button-1>", lambda e: self.open_selected())

        box = ttk.LabelFrame(self, text="CA application window")
        box.grid(row=2, column=0, columnspan=3, sticky="we", pady=8)
        self.vars = {}
        for i, (name, lbl) in enumerate(
                [("AppLeft", "X"), ("AppTop", "Y"),
                 ("AppWidth", "Width"), ("AppHeight", "Height")]):
            ttk.Label(box, text=lbl).grid(row=0, column=i * 2, padx=2)
            v = tk.StringVar()
            ttk.Entry(box, textvariable=v, width=7).grid(row=0, column=i * 2 + 1)
            self.vars[name] = v
        self.columnconfigure(1, weight=1)

    def open_dialog(self):
        path = filedialog.asksaveasfilename(
            title="Open ini (missing file will be created)",
            defaultextension=".ini", confirmoverwrite=False,
            filetypes=[("ini files", "*.ini"), ("All", "*.*")])
        self.app.open_ini(path)

    def open_selected(self):
        sel = self.lst.curselection()
        if sel:
            self.app.open_ini(self.lst.get(sel[0]))

    def load(self, cfg):
        self.lbl_path.config(text=self.app.current_path or "-")
        self.lst.delete(0, "end")
        for p in self.app.state.get("recent", []):
            self.lst.insert("end", p)
        for k, v in cfg["General"].items():
            if k in self.vars:
                self.vars[k].set(str(v))

    def collect(self, cfg):
        for k, v in self.vars.items():
            cfg["General"][k] = str(int(v.get()))


# ----------------------------------------------------------------- Gener ---
class GenerTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=8)
        self.app = app

        ttk.Label(self, text="Field side size:").grid(row=0, column=0, sticky="w")
        self.size_var = tk.StringVar()
        cb = ttk.Combobox(self, textvariable=self.size_var,
                          values=[str(s) for s in SIZES], state="readonly", width=8)
        cb.grid(row=0, column=1, sticky="w")
        cb.bind("<<ComboboxSelected>>", lambda e: self.on_size_change())

        # --- points group
        pg = ttk.LabelFrame(self, text="Points")
        pg.grid(row=1, column=0, sticky="we", pady=4)
        self.pt_mode = tk.StringVar(value="Count")
        self.pt_same = tk.StringVar(value="True")
        self.pts_counts = [300.0, 300.0, 400.0]   # canonical counts R,G,B
        ttk.Radiobutton(pg, text="Count", variable=self.pt_mode, value="Count",
                        command=self.rebuild_points).grid(row=0, column=0)
        ttk.Radiobutton(pg, text="Percent", variable=self.pt_mode, value="Percent",
                        command=self.rebuild_points).grid(row=0, column=1)
        ttk.Radiobutton(pg, text="Same for colors", variable=self.pt_same, value="True",
                        command=self.rebuild_points).grid(row=0, column=2)
        ttk.Radiobutton(pg, text="Per color", variable=self.pt_same, value="False",
                        command=self.rebuild_points).grid(row=0, column=3)
        self.pt_frame = ttk.Frame(pg)
        self.pt_frame.grid(row=1, column=0, columnspan=4, sticky="w", pady=2)
        self.pt_vars = {}

        # --- weights group
        wg = ttk.LabelFrame(self, text="Layer weights")
        wg.grid(row=2, column=0, sticky="we", pady=4)
        self.w_frame = ttk.Frame(wg)
        self.w_frame.pack(fill="x")
        ttk.Button(wg, text="Align in line", command=self.align_sliders).pack(side="left", padx=2)
        ttk.Button(wg, text="Reset to 1", command=self.reset_sliders).pack(side="left", padx=2)
        self.sliders = []

        # --- distribution group
        dg = ttk.LabelFrame(self, text="Initial points placement")
        dg.grid(row=3, column=0, sticky="we", pady=4)
        self.dist_common = tk.StringVar(value="True")
        self._prev_dist_common = "True"
        ttk.Radiobutton(dg, text="Common", variable=self.dist_common, value="True",
                        command=self.on_dist_change).grid(row=0, column=0)
        ttk.Radiobutton(dg, text="Per color", variable=self.dist_common, value="False",
                        command=self.on_dist_change).grid(row=0, column=1)
        self.dist_type = tk.StringVar(value="Uniform")
        dt = ttk.Combobox(dg, textvariable=self.dist_type, state="readonly",
                          values=["Uniform", "Normal", "Areas"], width=10)
        dt.grid(row=0, column=2)
        dt.bind("<<ComboboxSelected>>", lambda e: self.on_dist_change())
        self.dist_frame = ttk.Frame(dg)
        self.dist_frame.grid(row=1, column=0, columnspan=3, sticky="w")
        self.dist_vars = {}
        self.dist_vals = {}          # (color, field) -> string value
        self._g = {}                 # Gener section of the current cfg

    # -- dynamic builders ---------------------------------------------------
    def field_size(self):
        try:
            return int(self.size_var.get())
        except ValueError:
            return 128

    def pts_to_counts(self, raw):
        """Displayed value -> canonical count."""
        if self.pt_mode.get() == "Percent":
            n = self.field_size() ** 2
            return raw / 100.0 * n
        return raw

    def pts_display_val(self, k):
        """Canonical counts -> displayed value for field k."""
        if self.pt_mode.get() == "Percent":
            n = self.field_size() ** 2
            vals = [c / n * 100.0 for c in self.pts_counts]
        else:
            vals = [round(c) for c in self.pts_counts]
        if k == "Total":
            return sum(vals)
        return vals["RGB".index(k)]

    def pts_fmt(self, val):
        if self.pt_mode.get() == "Percent":
            return fmt_float(round(val, 4))
        return str(int(val))

    def on_pts_edit(self, k):
        if getattr(self, "_pts_guard", False):
            return
        try:
            raw = parse_float(self.pt_vars[k].get())
        except ValueError:
            return
        val = self.pts_to_counts(raw)
        if k == "Total":
            self.pts_counts = [val / 3.0] * 3
        else:
            self.pts_counts["RGB".index(k)] = val
        self.refresh_pts_entries(exclude=k)

    def refresh_pts_entries(self, exclude=None):
        self._pts_guard = True
        for k, v in self.pt_vars.items():
            if k != exclude:
                v.set(self.pts_fmt(self.pts_display_val(k)))
        self._pts_guard = False

    def rebuild_points(self):
        for w in self.pt_frame.winfo_children():
            w.destroy()
        self.pt_vars = {}
        keys = ["Total"] if self.pt_same.get() == "True" else ["R", "G", "B"]
        pct = self.pt_mode.get() == "Percent"
        self._pts_guard = True
        for i, k in enumerate(keys):
            ttk.Label(self.pt_frame, text=k + (" %" if pct else "")).grid(
                row=0, column=i * 2, padx=2)
            v = tk.StringVar(value=self.pts_fmt(self.pts_display_val(k)))
            v.trace_add("write", lambda *a, k=k: self.on_pts_edit(k))
            ttk.Entry(self.pt_frame, textvariable=v, width=8).grid(
                row=0, column=i * 2 + 1)
            self.pt_vars[k] = v
        self._pts_guard = False

    def scale_rects(self, s, k):
        """Scale all numbers in "x,y,w,h; ..." by k."""
        out = []
        for part in str(s).split(";"):
            nums = [x.strip() for x in part.split(",") if x.strip()]
            if not nums:
                continue
            try:
                scaled = [round(parse_float(x) * k, 2) for x in nums]
            except ValueError:
                out.append(part.strip())
                continue
            out.append(",".join(fmt_float(v) for v in scaled))
        return "; ".join(out)

    def on_size_change(self):
        new = self.field_size()
        old = getattr(self, "_cur_size", new)
        if new != old:
            # keep percents: counts scale with the field area
            k_sq = (new * new) / (old * old)
            self.pts_counts = [c * k_sq for c in self.pts_counts]
            # scale Areas rects proportionally
            k = new / old
            for key, val in list(self.dist_vals.items()):
                if key[1].startswith("Rects") and val:
                    self.dist_vals[key] = self.scale_rects(val, k)
        self._cur_size = new
        self.rebuild_sliders()
        self.rebuild_points()     # percent displays depend on the field size
        if self.dist_type.get() == "Areas":
            self.rebuild_dist()

    DIST_FIELDS = {"Uniform": [],
                   "Normal": ["X", "Y", "SigmaX", "SigmaY"],
                   "Areas": ["Rects (x,y,w,h; ...)"]}

    def reload_areas_for_size(self):
        """Areas are stored per field size: Areas1024 = "0,0,10,10"."""
        g = self._g or {}
        size = self.field_size()
        common_key = f"Areas{size}"
        colors = [""] if self.dist_common.get() == "True" else ["R", "G", "B"]
        for c in colors:
            v = g.get(common_key + c) or g.get(common_key) or g.get("Areas")
            if v:
                self.dist_vals[(c, "Rects (x,y,w,h; ...)")] = str(v)

    def on_dist_change(self):
        # Common <-> Per color: propagate values
        now_common = self.dist_common.get()
        if self._prev_dist_common == "True" and now_common == "False":
            for f in self.DIST_FIELDS["Normal"] + self.DIST_FIELDS["Areas"]:
                src = self.dist_vals.get(("", f), "")
                for c in "RGB":
                    self.dist_vals[(c, f)] = src
        elif self._prev_dist_common == "False" and now_common == "True":
            for f in self.DIST_FIELDS["Normal"] + self.DIST_FIELDS["Areas"]:
                self.dist_vals[("", f)] = self.dist_vals.get(("R", f), "")
        self._prev_dist_common = now_common
        if self.dist_type.get() == "Areas":
            self.reload_areas_for_size()
        self.rebuild_dist()

    def rebuild_dist(self):
        for w in self.dist_frame.winfo_children():
            w.destroy()
        self.dist_vars = {}
        colors = [""] if self.dist_common.get() == "True" else ["R", "G", "B"]
        t = self.dist_type.get()
        fields = self.DIST_FIELDS[t]
        for r, c in enumerate(colors):
            for i, f in enumerate(fields):
                ttk.Label(self.dist_frame, text=(c or " ") + f).grid(
                    row=r, column=i * 2, padx=2, sticky="w")
                v = tk.StringVar(value=self.dist_vals.get((c, f), ""))
                w = 40 if "Rects" in f else 8
                ttk.Entry(self.dist_frame, textvariable=v, width=w).grid(
                    row=r, column=i * 2 + 1)
                self.dist_vars[(c, f)] = v

    def rebuild_sliders(self):
        for w in self.w_frame.winfo_children():
            w.destroy()
        self.sliders = []
        try:
            size = int(self.size_var.get())
        except ValueError:
            return
        n = layers_for(size)
        old = [s.get() for s in getattr(self, "_old_sliders", [])]
        base = tkfont.nametofont("TkDefaultFont")
        small = (base.actual("family"), base.actual("size") - 2)
        ticks = ttk.Frame(self.w_frame, width=30, height=132)
        ticks.grid(row=0, column=0, sticky="ns")
        ticks.grid_propagate(False)
        for val, txt in [(2.0, "+2"), (1.0, "+1"), (0.0, "0"), (-1.0, "-1")]:
            l = ttk.Label(ticks, text=txt, font=small)
            l.place(relx=1.0, y=6 + (2.0 - val) / 3.0 * 120, anchor="e", x=-2)
        for i in range(n):
            v = tk.DoubleVar(value=old[i] if i < len(old) else 1.0)
            s = ttk.Scale(self.w_frame, from_=2.0, to=-1.0, variable=v,
                          orient="vertical", length=120)
            s.grid(row=0, column=i + 1, padx=1)
            lbl = ttk.Label(self.w_frame, text=f"{v.get():.2f}", font=small,
                            width=5, anchor="center")
            holder = ttk.Frame(self.w_frame, width=34, height=16)
            holder.grid(row=1, column=i + 1)
            holder.grid_propagate(False)
            lbl = ttk.Label(self.w_frame, text=f"{v.get():.2f}", font=small,
                            width=5, anchor="center")
            lbl.place(in_=holder, relx=0.5, rely=0.0, y=-6, anchor="n")
            v.trace_add("write", lambda *a, v=v, l=lbl: l.config(text=f"{v.get():.2f}"))

            step = 0.05

            def clamp(x):
                return max(-1.0, min(2.0, x))

            def nudge(delta, q=step, var=v):
                base = round(var.get() / q) * q + delta
                var.set(clamp(round(base, 2)))

            s.bind("<Button-1>",
                   lambda e, sc=s: sc.focus_set(), add="+")
            s.bind("<Button-4>", lambda e, d=+step, f=nudge: f(d))
            s.bind("<Button-5>", lambda e, d=-step, f=nudge: f(d))
            s.bind("<MouseWheel>",
                   lambda e, f=nudge: f(+step if e.delta > 0 else -step))
            s.bind("<Left>", lambda e, d=-step, f=nudge: (f(d), "break")[1])
            s.bind("<Right>", lambda e, d=+step, f=nudge: (f(d), "break")[1])
            s.bind("<Up>", lambda e, d=+step, f=nudge: (f(d), "break")[1])
            s.bind("<Down>", lambda e, d=-step, f=nudge: (f(d), "break")[1])
            s.bind("<Home>", lambda e, var=v: (var.set(-1.0), "break")[1])
            s.bind("<End>", lambda e, var=v: (var.set(2.0), "break")[1])
            s.bind("<Prior>", lambda e, d=+0.5, f=nudge: (f(d, 0.05), "break")[1])
            s.bind("<Next>", lambda e, d=-0.5, f=nudge: (f(d, 0.05), "break")[1])
            for seq, d, q in [("<Shift-Up>", +0.01, 0.01), ("<Shift-Down>", -0.01, 0.01),
                              ("<Shift-Right>", +0.01, 0.01), ("<Shift-Left>", -0.01, 0.01)]:
                s.bind(seq, lambda e, d=d, q=q, f=nudge: (f(d, q), "break")[1])
            s.bind("<Shift-Button-4>", lambda e, d=+0.01, f=nudge: f(d, 0.01))
            s.bind("<Shift-Button-5>", lambda e, d=-0.01, f=nudge: f(d, 0.01))
            s.configure(takefocus=1)
            self.sliders.append(v)
        self._old_sliders = list(self.sliders)

    def align_sliders(self):
        if len(self.sliders) < 2:
            return
        a, b = self.sliders[0].get(), self.sliders[-1].get()
        n = len(self.sliders) - 1
        for i, v in enumerate(self.sliders):
            v.set(a + (b - a) * i / n)

    def reset_sliders(self):
        for v in self.sliders:
            v.set(1.0)

    # -- load / collect -------------------------------------------------------
    def load(self, cfg):
        g = cfg["Gener"]
        self._g = g
        self.size_var.set(g.get("FieldSize", "128"))
        self._cur_size = self.field_size()
        self.pt_mode.set(g.get("PointsMode", "Count"))
        # saved values are in PointsMode units; keep canonical counts
        raw_pts = [parse_float(g.get("Points" + c, "0")) for c in "RGB"]
        if self.pt_mode.get() == "Percent":
            n = self.field_size() ** 2
            self.pts_counts = [x / 100.0 * n for x in raw_pts]
        else:
            self.pts_counts = raw_pts
        self.pt_same.set("True" if self.pts_counts[0] == self.pts_counts[1]
                         == self.pts_counts[2] else "False")
        self.rebuild_points()
        self._old_sliders = []
        self.rebuild_sliders()
        ws = [parse_float(x) for x in g.get("Weights", "").split()]
        for i, v in enumerate(self.sliders):
            if i < len(ws):
                v.set(ws[i])
        self._old_sliders = list(self.sliders)
        # Common/Per color derived from per-color keys presence
        size = self.field_size()
        per_keys = [f"Normal{f}{c}" for f in ("X", "Y", "SX", "SY") for c in "RGB"] + \
                   [f"Areas{size}{c}" for c in "RGB"]
        is_per = any(k in g for k in per_keys)
        self.dist_common.set("False" if is_per else "True")
        self._prev_dist_common = self.dist_common.get()
        self.dist_type.set(g.get("Distrib", "Uniform"))
        self.dist_vals = {}
        for f in ("X", "Y", "SigmaX", "SigmaY"):
            base = {"X": "NormalX", "Y": "NormalY",
                    "SigmaX": "NormalSX", "SigmaY": "NormalSY"}[f]
            if is_per:
                for c in "RGB":
                    self.dist_vals[(c, f)] = str(g.get(base + c,
                                                       g.get(base, "0")))
            else:
                self.dist_vals[("", f)] = str(g.get(base, "0"))
        for c in ([""] if not is_per else ["R", "G", "B"]):
            v = g.get(f"Areas{size}{c}", g.get("Areas", "0,0,10,10"))
            self.dist_vals[(c, "Rects (x,y,w,h; ...)")] = str(v)
        self.rebuild_dist()

    def collect(self, cfg):
        g = cfg["Gener"]
        g["FieldSize"] = self.size_var.get()
        g["PointsMode"] = self.pt_mode.get()   # view mode only
        size = self.field_size()
        # PointsR/G/B are always saved as counts
        for i, c in enumerate("RGB"):
            g["Points" + c] = str(int(round(self.pts_counts[i])))
        for k in ("PointsSame", "PointsTotal", "DistribCommon"):
            g.pop(k, None)
        g["Weights"] = " ".join(f"{v.get():.3f}" for v in self.sliders)
        g["Distrib"] = self.dist_type.get()
        common = self.dist_common.get() == "True"
        normal_map = {"X": "NormalX", "Y": "NormalY",
                      "SigmaX": "NormalSX", "SigmaY": "NormalSY"}
        for (c, f), var in self.dist_vars.items():
            if f in normal_map:
                base = normal_map[f]
                try:
                    val = fmt_float(parse_float(var.get()))
                except ValueError:
                    val = var.get()
                g[base if common else base + c] = val
            elif f.startswith("Rects"):
                g[f"Areas{size}{c}"] = var.get()


# --------------------------------------------------------------- ProcUp ---
class ProcUpTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=8)
        self.app = app
        self.table = list(default_procup_table())
        self.sel_combo = None

        top = ttk.Frame(self)
        top.pack(fill="both", expand=False)
        ttk.Label(top, text="1) Non-empty count").grid(row=0, column=0)
        ttk.Label(top, text="2) Combinations").grid(row=0, column=1)
        self.lbl3 = ttk.Label(top, text="3) Concrete")
        self.lbl3.grid(row=0, column=2)
        self.lbl_res = ttk.Label(top, text="Result color")
        self.lbl_res.grid(row=0, column=3)

        self.lb1 = tk.Listbox(top, height=10, width=16, exportselection=False)
        self.lb2 = tk.Listbox(top, height=10, width=16, exportselection=False)
        self.lb2_scroll = ttk.Scrollbar(top, orient="vertical",
                                        command=self.lb2.yview)
        self.lb2.config(yscrollcommand=self.lb2_scroll.set)
        self.lb3 = tk.Listbox(top, height=10, width=16, exportselection=False)
        self.lb1.grid(row=1, column=0, sticky="ns", padx=2)
        self.lb2.grid(row=1, column=1, sticky="ns", padx=2)
        self.lb2_scroll.grid(row=1, column=1, sticky="ens")
        self.lb3.grid(row=1, column=2, sticky="ns", padx=2)
        for item in PROCUP_LEVEL1:
            self.lb1.insert("end", item)
        self.lb1.bind("<<ListboxSelect>>", lambda e: self.on_l1())
        self.lb2.bind("<<ListboxSelect>>", lambda e: self.on_l2())
        self.lb3.bind("<<ListboxSelect>>", lambda e: self.on_l3())

        self.result = tk.StringVar(value="N")
        self.rf = ttk.Frame(top)
        self.rf.grid(row=1, column=3, sticky="n", padx=6)
        for val, txt in [("0", "N"), ("1", "R"), ("2", "G"), ("3", "B")]:
            ttk.Radiobutton(self.rf, text=txt, variable=self.result, value=val,
                            command=self.apply_result).pack(anchor="w")

        self.lb3.grid_remove()
        self.lbl3.grid_remove()
        self.rf.grid_remove()
        self.lbl_res.grid_remove()

        # initial selection: first row of each list
        self.lb1.selection_set(0)
        self.on_l1()
        self.lb2.selection_set(0)
        self.on_l2()

    def on_l1(self):
        sel = self.lb1.curselection()
        if not sel:
            return
        self.lb2.delete(0, "end")
        self.lb3.delete(0, "end")
        self.lb3.grid_remove()
        self.lbl3.grid_remove()
        self.rf.grid_remove()
        self.lbl_res.grid_remove()
        self.sel_combo = None
        for it in level2_items(self.lb1.get(sel[0])):
            self.lb2.insert("end", it)
        self.lb2.selection_clear(0, "end")
        self.lb2.selection_set(0)
        self.on_l2()

    def on_l2(self):
        sel = self.lb2.curselection()
        if not sel:
            return
        item = self.lb2.get(sel[0])
        self.lb3.delete(0, "end")
        self.lb3.selection_clear(0, "end")
        if any(ch in "XYZ" for ch in item):
            quads = mask_expand(item)
            for q in quads:
                self.lb3.insert("end", q)
            if all(self.table[code_from_str(q)] == self.table[code_from_str(quads[0])]
                   for q in quads):
                # uniform Result color over the mask: show Result group only
                self.lb3.grid_remove()
                self.lbl3.grid_remove()
                self.rf.grid()
                self.lbl_res.grid()
                self.sel_combo = item
                self.show_current(quads[0])
            else:
                # mixed Result colors: show Concrete list instead
                self.rf.grid_remove()
                self.lbl_res.grid_remove()
                self.lb3.grid()
                self.lbl3.grid()
                self.sel_combo = None
        else:
            self.lb3.grid_remove()
            self.lbl3.grid_remove()
            self.rf.grid()
            self.lbl_res.grid()
            self.sel_combo = item
            self.show_current(item)

    def on_l3(self):
        sel = self.lb3.curselection()
        if not sel:
            return
        self.sel_combo = self.lb3.get(sel[0])
        self.rf.grid()
        self.lbl_res.grid()
        self.show_current(self.sel_combo)

    def show_current(self, combo):
        code = code_from_str(combo)
        self.result.set(self.table[code])

    def apply_result(self):
        if not self.sel_combo:
            return
        if any(ch in "XYZ" for ch in self.sel_combo):
            for q in mask_expand(self.sel_combo):
                for p in perms_of_multiset(q):
                    self.table[code_from_str(p)] = self.result.get()
        else:
            for q in perms_of_multiset(self.sel_combo):
                self.table[code_from_str(q)] = self.result.get()

    def load(self, cfg):
        t = cfg["ProcUp"].get("Table", default_procup_table())
        t = "".join(ch for ch in t if ch in "0123")
        self.table = list(t.ljust(256, "0")[:256])
        self.sel_combo = None
        if self.lb2.curselection():
            self.on_l2()
        elif self.lb1.curselection():
            self.on_l1()

    def collect(self, cfg):
        cfg["ProcUp"]["Table"] = "".join(self.table)


# --------------------------------------------------------------- ProcDn ---
# layout of the quad visualization (tune manually)
DN_CANVAS_W = 340        # canvas width, px
DN_CANVAS_H = 340        # canvas height, px

DN_CELL = 120            # cell side, px
DN_GAP = 14              # gap between cells after cutting, px
DN_SCALE = 3.0           # vector of magnitude 1 spans cell side / DN_SCALE

# touching-quad center on the canvas (px) = 164
DN_CENTER = (DN_CANVAS_W - DN_GAP + 1) / 2 


class ProcDnTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=8)
        self.app = app
        self.edited = {}          # quad -> 8 signed indices
        self.full = {}            # all 256 quads -> 8 values
        self.tablef = list(DEFAULT_TABLEF)

        topf = ttk.Frame(self)
        topf.grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(topf, text="Force table:").pack(side="left")
        self.tf_var = tk.StringVar()
        ttk.Entry(topf, textvariable=self.tf_var, width=45).pack(side="left")
        self.tf_var.trace_add("write", lambda *a: self.parse_tablef())

        ttk.Label(self, text="Combinations:").grid(row=1, column=0, sticky="w")
        self.use_tmpl = tk.BooleanVar(value=True)
        self.tmpl_cb = ttk.Checkbutton(self, text="Templates",
                                       variable=self.use_tmpl,
                                       command=self.rebuild_combos)
        self.tmpl_cb.grid(row=1, column=0, sticky="w", padx=(110, 0))
        self.lb1 = tk.Listbox(self, height=8, exportselection=False)
        self.lb1.grid(row=2, column=0, rowspan=8, sticky="ns", padx=2)
        self.lb1.bind("<<ListboxSelect>>", lambda e: self.on_combo())

        self.lb2 = tk.Listbox(self, height=8, exportselection=False)
        self.lb2.grid(row=2, column=1, rowspan=8, sticky="nw", padx=2)
        self.lb2.bind("<<ListboxSelect>>", self.on_lb2_select)
        self.lbl2 = ttk.Label(self, text="Specific quads (on conflict):")
        self.lbl2.grid(row=1, column=1, sticky="w")
        self.lb2.grid_remove()
        self.lbl2.grid_remove()

        self.fields = []
        self.field_cbs = []
        fbox = ttk.Frame(self)
        fbox.grid(row=2, column=2, rowspan=4, sticky="nw", padx=6)
        for i, lbl in enumerate(FDN_LABELS):
            ttk.Label(fbox, text=lbl).grid(row=i // 2, column=(i % 2) * 2, sticky="w", padx=2)
            v = tk.StringVar()
            cb = ttk.Combobox(fbox, textvariable=v, width=9, state="readonly")
            cb.grid(row=i // 2, column=(i % 2) * 2 + 1)
            cb.bind("<<ComboboxSelected>>", lambda e: self.on_field_change())
            self.field_cbs.append(cb)
            self.fields.append(v)

        self.canvas = tk.Canvas(self, width=DN_CANVAS_W, height=DN_CANVAS_H,
                                bg="white")
        self.canvas.grid(row=6, column=2, rowspan=4, padx=6)

    # -- helpers ----------------------------------------------------------
    def parse_tablef(self):
        try:
            vals = [parse_float(x) for x in self.tf_var.get().split()]
            if len(vals) == 8:
                self.tablef = vals
                self.refresh_field_values()
                self.draw_quad()
        except ValueError:
            pass

    def combo_values(self):
        out = []
        for s in (1, -1):
            for i in range(8):
                out.append(f"{s * i:+d} ({s * self.tablef[i]:+.2f})")
        return out

    def refresh_field_values(self):
        vals = self.combo_values()
        for cb in self.field_cbs:
            cb["values"] = vals
        cur = [v.get().split(" ")[0] if v.get() else None for v in self.fields]
        for v, c in zip(self.fields, cur):
            if c:
                sign = -1 if c.startswith("-") else 1
                idx = abs(int(c))
                v.set(f"{sign * idx:+d} ({sign * self.tablef[idx]:+.2f})")

    def current_quad(self):
        """Quad string (may contain template letters) currently selected."""
        sel = self.lb1.curselection()
        if not sel:
            return None
        return self.lb1.get(sel[0])

    def rebuild_combos(self):
        self.lb1.delete(0, "end")
        self.lb2.delete(0, "end")
        items = TEMPLATES if self.use_tmpl.get() else CONCRETE_BASES
        for it in items:
            self.lb1.insert("end", it)
        if items:
            self.lb1.selection_set(0)
            self.on_combo()

    def on_combo(self):
        q = self.current_quad()
        if not q:
            return
        self.update_field_states(q)
        self.lb2.delete(0, "end")
        quads = template_quads(q) if self.use_tmpl.get() else orbit_of(q)
        groups = {}
        for c in quads:
            groups.setdefault(tuple(self.full.get(c, [0] * 8)), []).append(c)
        if len(groups) == 1:
            self.lb2.delete(0, "end")
            self.lb2.grid_remove()
            self.lbl2.grid_remove()
            self.load_values(list(groups.values())[0][0])
        else:
            for vals, qs in groups.items():
                self.lb2.insert("end", f"{qs[0]}  =  {' '.join(map(str, vals))}")
            self.lb2.grid()
            self.lbl2.grid()
        self.draw_quad()

    def on_lb2_select(self, _e=None):
        sel = self.lb2.curselection()
        if sel:
            self.load_values(self.lb2.get(sel[0])[:4])
            self.draw_quad()

    def update_field_states(self, q):
        """Disable force fields that do not apply to the current combination."""
        if q is None:
            return
        has_n = "N" in q
        has_full = any(c != "N" for c in q)
        empty_idx = (0, 1, 4, 5)
        full_idx = (2, 3, 6, 7)
        for i, cb in enumerate(self.field_cbs):
            if i in empty_idx and not has_n:
                cb.state(["disabled"])
            elif i in full_idx and not has_full:
                cb.state(["disabled"])
            else:
                cb.state(["!disabled"])

    def load_values(self, quad):
        v = self.full.get(quad, [0] * 8)
        for i, fv in enumerate(self.fields):
            idx = v[i]
            val = (1 if idx >= 0 else -1) * self.tablef[min(abs(idx), 7)]
            fv.set(f"{idx:+d} ({val:+.2f})")

    def on_field_change(self):
        q = self.current_quad()
        if not q:
            return
        vals = []
        for fv in self.fields:
            if not fv.get():
                return
            vals.append(int(fv.get().split(" ")[0]))
        targets = template_quads(q) if self.use_tmpl.get() else orbit_of(q)
        for t in targets:
            self.edited[t] = list(vals)
        self.full = expand_forces(self.edited)
        self.draw_quad()

    def draw_quad(self):
        cv = self.canvas
        cv.delete("all")
        q = self.current_quad()
        if not q:
            return
        size = DN_CELL
        gap = DN_GAP
        # touching quad spans CENTER±size, so cell borders coincide with
        # the vector grid points before the gap shift
        x0, y0 = DN_CENTER - size, DN_CENTER - size
        colors = {"N": "#ffffff", "R": "#ff4444", "G": "#44cc44", "B": "#4488ff",
                  "A": "#cccccc", "X": "#00ffff", "Y": "#ff00ff", "Z": "#ffff00"}
        fvals = [int(fv.get().split(" ")[0]) if fv.get() else 0 for fv in self.fields]
        for i, ch in enumerate(q):
            r, c = divmod(i, 2)
            cx = x0 + c * (size + gap)
            cy = y0 + r * (size + gap)
            cv.create_rectangle(cx, cy, cx + size, cy + size,
                                fill=colors.get(ch, "#ffffff"),
                                outline="#888888")
            empty = ch in ("N",)
            self.draw_cell_vectors(cx, cy, size, empty, fvals, c, r, gap)

    def draw_cell_vectors(self, cx, cy, size, empty, fvals, c, r, gap):
        cv = self.canvas
        rc_f, re_f = (fvals[0], fvals[1]) if empty else (fvals[2], fvals[3])
        cc_f, ce_f = (fvals[4], fvals[5]) if empty else (fvals[6], fvals[7])
        tf = self.tablef

        def mag(idx):
            return (1 if idx >= 0 else -1) * tf[abs(idx)] if abs(idx) < 8 else 0

        # vectors are computed on the touching 2x2 quad (no gap) whose
        # center is (200,200); then only positions are
        # shifted apart by the cell's gap, directions/lengths unchanged
        bx = DN_CENTER - size + c * size
        by = DN_CENTER - size + r * size
        for gi in range(4):
            for gj in range(4):
                px0 = bx + size * (1.0 / 3.0) * gj
                py0 = by + size * (1.0 / 3.0) * gi
                # magnitude and direction: both measured on the touching
                # quad, so the whole picture has D4 symmetry
                rx, ry = px0 - DN_CENTER, py0 - DN_CENTER
                r_ = math.hypot(rx, ry)
                if r_ < 1e-6:
                    # the 4 coincident center points: direction = the cell's
                    # own shift after cutting the quad apart (toward its far
                    # corner), magnitude = the center value (t = 0)
                    ux = (2 * c - 1) / math.sqrt(2)
                    uy = (2 * r - 1) / math.sqrt(2)
                    t = 0.0
                else:
                    t = min(r_ / (size * math.sqrt(2)), 1.0)
                    ux, uy = rx / r_, ry / r_
                rad = mag(rc_f) + (mag(re_f) - mag(rc_f)) * t
                cir = mag(cc_f) + (mag(ce_f) - mag(cc_f)) * t
                vx = rad * ux - cir * uy
                vy = rad * uy + cir * ux
                px, py = px0 + c * gap, py0 + r * gap
                scale = size / DN_SCALE  # vector of magnitude 1 spans cell side / DN_SCALE
                cv.create_oval(px - 2, py - 2, px + 2, py + 2, fill="black")
                cv.create_line(px, py, px + vx * scale, py + vy * scale,
                               width=2, fill="#222222")

    def load(self, cfg):
        d = cfg["ProcDn"]
        self.tf_var.set(d.get("TableF", " ".join(map(str, DEFAULT_TABLEF))))
        self.parse_tablef()
        self.use_tmpl.set(d.get("UseTemplates", "True") == "True")
        self.edited = {}
        for k, v in d.items():
            if len(k) == 4 and all(ch in "0123" for ch in k) and k != "TableF":
                try:
                    vals = [int(x) for x in str(v).split()]
                    if len(vals) == 8:
                        self.edited[quad_str(int(k, 4) if False else 0) if False
                                    else "".join(LETTERS[int(ch)] for ch in k)] = vals
                except ValueError:
                    continue
        self.full = expand_forces(self.edited)
        self.rebuild_combos()
        self.draw_quad()

    def collect(self, cfg):
        d = cfg["ProcDn"]
        d["TableF"] = self.tf_var.get()
        d["UseTemplates"] = str(self.use_tmpl.get())
        full = expand_forces(self.edited)
        for q in all_quads():
            d["".join(str(LETTERS.index(ch)) for ch in q)] = " ".join(map(str, full[q]))


if __name__ == "__main__":
    App().mainloop()
