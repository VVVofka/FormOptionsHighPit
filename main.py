#!/usr/bin/env python3
"""Config editor (ini) for the C++ cellular automaton program."""
import itertools
import json
import math
import copy
import os
import random
import time
from array import array as word_array
import tkinter as tk
import tkinter.font as tkfont
from collections import Counter
from tkinter import ttk, filedialog, messagebox

from configobj import ConfigObj

from SDGP import sdgp as sdgp_mod

APP_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(APP_DIR, "form_state.json")
DEFAULT_FILE = os.path.join(APP_DIR, "default_stat.json")
DEFAULT_STATE = {
    "geometry": "1011x540+1330+178",
    "recent": [],
    "last_ini": None,
    "tab": 0,
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
            "FillPercent": "7",
            "Seed": "0",
            "SDGP": json.dumps(sdgp_mod.normalize_data(
                sdgp_mod.DEFAULT_TEMPLATES["Uniform"]), ensure_ascii=False),
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
        slastini = self.state.get("last_ini")
        self.current_path = slastini  or \
            os.path.join(APP_DIR, "ca.ini")
        self.cfg = cfg_to_nested(load_cfg(self.current_path))

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        btns = ttk.Frame(self)
        btns.pack(fill="x")
        ttk.Button(btns, text="Close", command=self.on_close).pack(side="right", padx=4, pady=4)
        ttk.Button(btns, text="Apply", command=self.on_apply).pack(side="right", padx=4, pady=4)
        ttk.Button(btns, text="Cancel", command=self.on_cancel).pack(side="right", pady=4)
        self.status = ttk.Label(self, relief="sunken", anchor="w", padding=(4, 2))
        self.status.pack(side="bottom", fill="x")

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
        try:
            tab = int(self.state.get("tab", 0))
            if 0 <= tab < self.nb.index("end"):
                self.nb.select(tab)
        except (TypeError, ValueError):
            pass
        self.refresh_all()

    # -- state / geometry -------------------------------------------------
    def set_status(self, text):
        self.status.config(text=text)

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
            "tab": self.nb.index(self.nb.select()),
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
GENER_PREVIEW = 256       # preview image side, px


def fmt_pct(v):
    """2 decimals with trailing zeros trimmed: 7.00 -> 7, 7.50 -> 7.5."""
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-", "-0") else s


class GenerTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=8)
        self.app = app
        self.records = []          # SDGP records
        self._rng = None           # persistent RNG for negative seed
        self._seed_init_pending = True   # negative seed: first run after tab select
        self._preview_img = None

        left = ttk.Frame(self)
        left.grid(row=0, column=0, sticky="nw")
        right = ttk.Frame(self)
        right.grid(row=0, column=1, sticky="nw", padx=(10, 0))

        # --- left: field size (combobox flush to the label)
        szf = ttk.Frame(left)
        szf.grid(row=0, column=0, sticky="w")
        ttk.Label(szf, text="Field side size:").pack(side="left")
        self.size_var = tk.StringVar()
        cb = ttk.Combobox(szf, textvariable=self.size_var,
                          values=[str(s) for s in SIZES], state="readonly", width=8)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda e: self.on_size_change())

        # --- left: fill percent
        pf = ttk.Frame(left)
        pf.grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Label(pf, text="Fill %:").pack(side="left")
        self.fill_var = tk.StringVar(value="7")
        ttk.Entry(pf, textvariable=self.fill_var, width=8).pack(
            side="left", padx=(4, 0))

        # --- left: RNG seed
        sf = ttk.Frame(left)
        sf.grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Label(sf, text="RNG seed:").pack(side="left")
        self.seed_var = tk.StringVar(value="0")
        ttk.Entry(sf, textvariable=self.seed_var, width=10).pack(
            side="left", padx=(4, 0))

        # --- left: SDGP info (readonly, multiline, scrollbars)
        head = ttk.Frame(left)
        head.grid(row=3, column=0, sticky="we", pady=(8, 0))
        ttk.Label(head, text="Start data:").pack(side="left")
        ttk.Button(head, text="Edit", command=self.edit_sdgp).pack(
            side="left", padx=6)
        box = ttk.Frame(left)
        box.grid(row=4, column=0, sticky="we")
        self.sdgp_txt = tk.Text(box, width=46, height=8, wrap="none",
                                state="disabled")
        sy = ttk.Scrollbar(box, orient="vertical", command=self.sdgp_txt.yview)
        sx = ttk.Scrollbar(box, orient="horizontal", command=self.sdgp_txt.xview)
        self.sdgp_txt.config(yscrollcommand=sy.set, xscrollcommand=sx.set)
        sy.pack(side="right", fill="y")
        sx.pack(side="bottom", fill="x")
        self.sdgp_txt.pack(fill="both", expand=True)

        # --- left: generation
        ttk.Button(left, text="Generation", command=self.on_generate).grid(
            row=5, column=0, sticky="w", pady=(8, 0))

        # --- left: weights group
        wg = ttk.LabelFrame(left, text="Layer weights")
        wg.grid(row=6, column=0, sticky="we", pady=4)
        self.w_frame = ttk.Frame(wg)
        self.w_frame.pack(fill="x")
        ttk.Button(wg, text="Align in line", command=self.align_sliders).pack(side="left", padx=2)
        ttk.Button(wg, text="Reset to 1", command=self.reset_sliders).pack(side="left", padx=2)
        self.sliders = []

        # --- right: preview (black square, 256x256)
        self.canvas = tk.Canvas(right, width=GENER_PREVIEW, height=GENER_PREVIEW,
                                bg="black", highlightthickness=0)
        self.canvas.grid(row=0, column=0)
        self.preview_img = tk.PhotoImage(width=GENER_PREVIEW,
                                         height=GENER_PREVIEW)
        self.canvas.create_image(0, 0, anchor="nw", image=self.preview_img)

        app.nb.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _on_tab_changed(self, _e):
        if self.app.nb.select() == str(self):
            self._seed_init_pending = True

    # -- helpers ----------------------------------------------------------
    def field_size(self):
        try:
            return int(self.size_var.get())
        except ValueError:
            return 128

    def on_size_change(self):
        self._cur_size = self.field_size()
        self.rebuild_sliders()

    @staticmethod
    def default_records():
        return sdgp_mod.normalize_data(sdgp_mod.DEFAULT_TEMPLATES["Uniform"])

    def refresh_sdgp_info(self):
        self.sdgp_txt.config(state="normal")
        self.sdgp_txt.delete("1.0", "end")
        for rec in self.records:
            self.sdgp_txt.insert("end", sdgp_mod.record_list_line(rec) + "\n")
        self.sdgp_txt.config(state="disabled")

    def edit_sdgp(self):
        res = sdgp_mod.OpenData(self.records)
        if res is not None:
            self.records = res
            self.refresh_sdgp_info()
            self.app.set_status(
                f"Start data updated: {len(self.records)} records")

    def read_fill(self):
        fill = parse_float(self.fill_var.get())
        return min(max(fill, 0.0), 100.0)

    def read_seed(self):
        return int(str(self.seed_var.get()).strip())

    # -- generation ---------------------------------------------------------
    GEN_TIMEOUT = 3.0        # seconds

    @staticmethod
    def _distribute(total, weights):
        """Largest-remainder split; tied leftovers are dropped so that
        equal weights keep an exactly equal ratio."""
        quotas = [0] * len(weights)
        tw = sum(weights)
        if total <= 0 or tw <= 0:
            return quotas
        fr = []
        base = 0
        for i, w in enumerate(weights):
            q = total * w / tw
            quotas[i] = math.floor(q)
            base += quotas[i]
            fr.append((q - quotas[i], i))
        fr.sort(reverse=True)
        rem = total - base
        while rem > 0 and fr:
            tie = 1
            while tie < len(fr) and fr[tie][0] == fr[0][0]:
                tie += 1
            if rem >= tie:             # whole tie group can grow together
                for k in range(tie):
                    quotas[fr[k][1]] += 1
                rem -= tie
                fr = fr[tie:]
            else:                      # would break the ratio: drop the rest
                break
        return quotas

    @staticmethod
    def _preview_pos(idx, size):
        """Field cell -> preview pixel (x, y); y is flipped:
        normalized -1 is the bottom of the preview."""
        px = (idx % size) * GENER_PREVIEW // size
        py = GENER_PREVIEW - max(1, GENER_PREVIEW // size) \
            - (idx // size) * GENER_PREVIEW // size
        return px, py

    @staticmethod
    def _parse_norm_params(text):
        """Parameters text -> (devx, devy, meanx, meany) or None (uniform).

        Formats: "devx devy meanx meany" | "devx devy" | "dev" | "" (uniform).
        dev <= 0 also means uniform.
        """
        toks = str(text or "").replace(",", " ").split()
        try:
            vals = [float(t) for t in toks]
        except ValueError:
            return None
        if len(vals) == 4:
            devx, devy, mx, my = vals
        elif len(vals) == 2:
            devx, devy, mx, my = vals[0], vals[1], 0.0, 0.0
        elif len(vals) == 1:
            devx = devy = vals[0]
            mx = my = 0.0
        else:
            return None
        if devx <= 0 or devy <= 0:
            return None
        return devx, devy, mx, my

    @staticmethod
    def _part1by1(n):
        """Spread bits of a 16-bit value into every other bit."""
        n &= 0x0000ffff
        n = (n | (n << 8)) & 0x00FF00FF
        n = (n | (n << 4)) & 0x0F0F0F0F
        n = (n | (n << 2)) & 0x33333333
        n = (n | (n << 1)) & 0x55555555
        return n

    @classmethod
    def _morton2(cls, y, x):
        """Morton interleave: y on even bits, x on odd bits
        (same as EncodeMorton2(idx_y, idx_x) in tordata.cpp)."""
        return cls._part1by1(y) | (cls._part1by1(x) << 1)

    @staticmethod
    def _wrap1(u):
        """Wrap a torus coordinate into [-1.0, 1.0)."""
        return (u + 1.0) % 2.0 - 1.0

    @staticmethod
    def _region_vals(rec):
        """Record -> parsed Region values (None = whole field)."""
        vals, err = sdgp_mod.parse_region(rec.get("Region", ""))
        if err:
            return None
        return vals or None

    @staticmethod
    def _inside(idx, size, vals):
        """Torus membership of cell center in Region values."""
        if not vals:
            return True
        if len(vals) == 2:             # a point: no area
            return False
        u = ((idx % size) + 0.5) / size * 2.0 - 1.0
        v = ((idx // size) + 0.5) / size * 2.0 - 1.0
        dx = ((u - vals[0] + 1.0) % 2.0) - 1.0
        dy = ((v - vals[1] + 1.0) % 2.0) - 1.0
        if len(vals) == 3:             # circle: x, y, r
            return dx * dx + dy * dy <= vals[2] * vals[2]
        # rectangle: x, y, w, h (center + sizes)
        return abs(dx) <= vals[2] / 2 and abs(dy) <= vals[3] / 2

    @staticmethod
    def _region_cells(size, vals):
        """Yield candidate cell indices (bounding box, torus-wrapped)."""
        if not vals:
            yield from range(size * size)
            return
        if len(vals) == 3:
            sx = sy = int(vals[2] * size) + 2
        elif len(vals) == 4:
            sx = int(vals[2] / 2 * size) + 2
            sy = int(vals[3] / 2 * size) + 2
        else:
            return
        cx0 = int((vals[0] + 1.0) / 2.0 * size)
        cy0 = int((vals[1] + 1.0) / 2.0 * size)
        for cy in range(cy0 - sy, cy0 + sy + 1):
            row = (cy % size) * size
            for cx in range(cx0 - sx, cx0 + sx + 1):
                yield row + cx % size

    def on_generate(self):
        try:
            fill = self.read_fill()
        except ValueError:
            self.app.set_status("Error: invalid Fill % value")
            return
        try:
            seed = self.read_seed()
        except ValueError:
            self.app.set_status("Error: invalid RNG seed value")
            return
        size = self.field_size()
        if seed > 0:                     # reseed with this number every run
            self._rng = random.Random(seed)
        elif seed == 0:                  # reseed from timer every run
            self._rng = random.Random()
        elif self._seed_init_pending:    # <0: first run after tab select
            self._rng = random.Random(-seed)
            self._seed_init_pending = False
        else:                            # <0: subsequent runs as with 0
            self._rng = random.Random()
        rng = self._rng

        def pct(r):
            if r["Colors"] == "N":
                return -1.0                 # N always means erase-fill
            return float(r.get("Percent", 0) or 0)

        active = [r for r in self.records
                  if r.get("Colors") not in ("", None)
                  and (pct(r) > 0 or pct(r) == -1)]
        if not active:
            active = self.default_records()
        normal = [r for r in active if pct(r) >= 0 and r["Colors"] != "N"]
        fill_ignored = not normal

        total_cells = size * size
        color_map = {"R": "#ff0000", "G": "#00ff00", "B": "#0000ff"}
        code_map = {"R": 1, "G": 2, "B": 3}   # 2-bit cell codes for output
        block = max(1, GENER_PREVIEW // size)
        occupied = bytearray(total_cells)
        solid = bytearray(total_cells)   # cells set by -1% records
        cells = bytearray(total_cells)   # final color code per cell (0=empty)
        touched = []                     # indices ever set (incl. erased)
        counts = {"R": 0, "G": 0, "B": 0}
        erased = 0
        # ops: ('P'|"point"|'S'|"solid", color, px, py); erase = ('E', ...)
        # at size > GENER_PREVIEW several field cells share a preview pixel,
        # so visibility is composed per pixel (see the render pass below)
        draws = []
        # quotas for normal records (Fill % of the field, exact ratios)
        qmap = {}
        if normal:
            n_req = min(int(round(fill / 100.0 * total_cells)), total_cells)
            for r, q in zip(normal, self._distribute(n_req, [pct(r) for r in normal])):
                qmap[id(r)] = q

        timeout = False
        deadline = time.perf_counter() + self.GEN_TIMEOUT
        steps = 0

        def expired():
            nonlocal timeout, steps
            steps += 1
            if timeout:
                return True
            if (steps & 0x3FF) == 0 and time.perf_counter() > deadline:
                timeout = True
            return timeout

        t0 = time.perf_counter()
        # records are processed sequentially in table order
        for r in active:
            vals = self._region_vals(r)
            letters = r["Colors"]
            if pct(r) < 0:
                # solid fill of the region ("as many as fit")
                is_erase = letters == "N"
                if is_erase and not vals:
                    continue        # erase needs an explicit Region
                for idx in self._region_cells(size, vals):
                    if expired():
                        break
                    if not self._inside(idx, size, vals):
                        continue
                    px, py = self._preview_pos(idx, size)
                    if is_erase:
                        if solid[idx]:          # erases only -1% fills
                            solid[idx] = 0
                            occupied[idx] = 0
                            cells[idx] = 0
                            erased += 1
                            draws.append(("E", None, px, py))
                    elif not occupied[idx]:
                        occupied[idx] = 1
                        solid[idx] = 1
                        ch = letters[0] if len(letters) == 1 else \
                            letters[int(rng.random() * len(letters))]
                        counts[ch] += 1
                        cells[idx] = code_map[ch]
                        touched.append(idx)
                        draws.append(("S", ch, px, py))
                if timeout:
                    break
            elif letters != "N" and id(r) in qmap:
                # quota points inside the region
                quota = qmap[id(r)]
                if vals and len(vals) == 2:
                    continue             # a point region has no area
                if vals:
                    if len(vals) == 3:
                        area_frac = math.pi * vals[2] * vals[2] / 4.0
                    else:
                        area_frac = vals[2] * vals[3] / 4.0
                    quota = min(quota, int(area_frac * total_cells))
                seq = []
                for ch, q in zip(letters, self._distribute(quota,
                                                            [1] * len(letters))):
                    seq.extend([ch] * q)
                rng.shuffle(seq)
                # distribution params are relative to the region bounds:
                # u in [-1,1] spans the region half-size; None = whole field
                half_x = half_y = 1.0
                if vals:
                    if len(vals) == 3:
                        half_x = half_y = vals[2]
                    else:
                        half_x, half_y = vals[2] / 2, vals[3] / 2
                np_ = self._parse_norm_params(r.get("Parameters", ""))
                gauss = rng.gauss if np_ else None
                devx = devy = 1.0
                if np_:
                    devx, devy, mx, my = np_
                fail = 0
                placed = 0
                while placed < len(seq):
                    if expired():
                        break
                    if gauss is not None:
                        # normal: sample in region-local coords, torus-wrapped
                        u = self._wrap1(gauss(mx, devx))
                        v = self._wrap1(gauss(my, devy))
                        gx = u if not vals else self._wrap1(vals[0] + u * half_x)
                        gy = v if not vals else self._wrap1(vals[1] + v * half_y)
                        idx = int((gx + 1.0) * 0.5 * size) % size + \
                            (int((gy + 1.0) * 0.5 * size) % size) * size
                        if not self._inside(idx, size, vals):
                            fail += 1          # e.g. corner of the bounding
                            if fail >= 100:    # square outside a circle
                                devx = devx * 1.01 + 0.01
                                devy = devy * 1.01 + 0.01
                                fail = 0
                            continue
                    else:
                        idx = rng.randrange(total_cells)
                        if not self._inside(idx, size, vals):
                            continue
                    if occupied[idx]:
                        fail += 1
                        if fail >= 100:        # density too high: widen dev
                            devx = devx * 1.01 + 0.01
                            devy = devy * 1.01 + 0.01
                            fail = 0
                        continue               # one point per cell
                    fail = 0
                    occupied[idx] = 1
                    ch = seq[placed]
                    counts[ch] += 1
                    cells[idx] = code_map[ch]
                    touched.append(idx)
                    px, py = self._preview_pos(idx, size)
                    draws.append(("P", ch, px, py))
                    placed += 1
                if timeout:
                    break
        t_gen = time.perf_counter() - t0

        t1 = time.perf_counter()
        img = self.preview_img
        img.blank()
        put = img.put
        if block > 1:
            strs = {c: ("{%s %s} {%s %s}" % (v, v, v, v))
                    for c, v in color_map.items()}
        else:
            strs = {c: "{%s}" % v for c, v in color_map.items()}
        # compose per preview pixel: a normal point wins over a solid fill
        # sharing the same pixel; erase clears only solid-owned pixels
        pix = {}
        for kind, ch, px, py in draws:
            p = (px, py)
            if kind == "E":
                if pix.get(p, ("",))[0] == "S":
                    del pix[p]
            elif kind == "P" or p not in pix or pix[p][0] == "S":
                pix[p] = (kind, ch)
        for (px, py), (_kind, ch) in pix.items():
            put(strs[ch], to=(px, py))
        t_draw = time.perf_counter() - t1

        # -- binary start data: Morton order, 2 bits per cell, 64-bit words.
        # bit layout follows tordata.cpp: EncodeMorton2(idx_y, idx_x) ->
        # y on even bits, x on odd bits; cell code: 0=N, 1=R, 2=G, 3=B
        t2 = time.perf_counter()
        n_words = (total_cells + 31) // 32
        words = word_array("Q", bytes(8 * n_words))
        morton = self._morton2
        for idx in touched:
            code = cells[idx]
            if code:
                m = morton(idx // size, idx % size)
                words[m >> 5] |= code << ((m & 31) * 2)
        self.out_words = words
        self.out_size = size
        t_out = time.perf_counter() - t2

        total = counts["R"] + counts["G"] + counts["B"]
        msg = (f"R={counts['R']} G={counts['G']} B={counts['B']}, "
               f"total={total}")
        if erased:
            msg += f", erased={erased}"
        if timeout:
            msg = f"Generation timeout after {self.GEN_TIMEOUT:.0f} s: " + msg
        else:
            msg = "Generated: " + msg + \
                f"  (calc {t_gen:.2f} s, draw {t_draw:.2f} s)"
        if fill_ignored:
            msg += "  [Fill % ignored: no counted records]"
        msg += f"  binary: {n_words} words / {8 * n_words} bytes"
        self.app.set_status(msg)

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
        self.size_var.set(g.get("FieldSize", "128"))
        self._cur_size = self.field_size()
        try:
            self.fill_var.set(fmt_pct(parse_float(g.get("FillPercent", "7"))))
        except ValueError:
            self.fill_var.set("7")
        try:
            self.seed_var.set(str(int(g.get("Seed", "0"))))
        except ValueError:
            self.seed_var.set("0")
        self.records = None
        raw = g.get("SDGP")
        if raw:
            try:
                self.records = sdgp_mod.normalize_data(json.loads(raw))
            except (ValueError, TypeError):
                self.records = None
        if not self.records:
            self.records = self.default_records()
        self.refresh_sdgp_info()
        self._old_sliders = []
        self.rebuild_sliders()
        ws = [parse_float(x) for x in g.get("Weights", "").split()]
        for i, v in enumerate(self.sliders):
            if i < len(ws):
                v.set(ws[i])
        self._old_sliders = list(self.sliders)

    def collect(self, cfg):
        g = cfg["Gener"]
        g["FieldSize"] = self.size_var.get()
        g["FillPercent"] = fmt_pct(self.read_fill())
        g["Seed"] = str(self.read_seed())
        g["SDGP"] = json.dumps(self.records, ensure_ascii=False)
        g["Weights"] = " ".join(f"{v.get():.3f}" for v in self.sliders)


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
