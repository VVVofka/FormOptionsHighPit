#!/usr/bin/env python3
"""SDGP - settings editor for records (Colors, Region, Parameters).

Standalone app or external module.
Data file: JSON with extension .sdgp
"""

import json
import os
import re
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

COLORS_VALUES = ["RGB", "R", "G", "B", "RG", "GB", "BR", "N"]

CONFIG_NAME = ".sdgp_config.json"

DEFAULT_TEMPLATES = {
    "Uniform": [{"Colors": "RGB", "Region": "", "Parameters": "", "Percent": 100.0}],
    "Normal": [{"Colors": "RGB", "Region": "", "Parameters": "0.9 1.2", "Percent": 100.0}],
    "Zones": [
        {"Colors": "BR", "Region": "-0.3 0 0.4", "Parameters": "", "Percent": 50.0},
        {"Colors": "G", "Region": "0.3 0.2 0.45", "Parameters": "0.85 0.8 0.9 0.75", "Percent": 50.0},
    ],
}


# ---------------- data / parsing ----------------

_VALUE_RE = re.compile(r"[+-]?[0-9.,]+")


def parse_region(text):
    """Parse Region text -> (values list or None, error message or None)."""
    if text is None:
        text = ""
    text = text.strip()
    if not text:
        return [], None
    if len(text) >= 64:
        return None, "Region: длина поля должна быть меньше 64 символов"
    tokens = _VALUE_RE.findall(text)
    values = []
    for t in tokens:
        try:
            values.append(float(t.replace(",", ".")))
        except ValueError:
            return None, "Region: не удалось разобрать значение '%s'" % t
    if len(values) not in (2, 3, 4):
        return None, "Region: должно быть 2, 3 или 4 значения, получено %d" % len(values)
    x, y = values[0], values[1]
    if not (-1.0 <= x <= 1.0 and -1.0 <= y <= 1.0):
        return None, "Region: x, y должны быть в диапазоне [-1.0; +1.0]"
    if len(values) == 4:
        w, h = values[2], values[3]
        if not (0.0 < w <= 1.0 and 0.0 < h <= 1.0):
            return None, "Region: w, h должны быть в диапазоне (0; +1.0]"
    return values, None


def normalize_colors(value):
    v = (value or "").strip()
    return v if v in COLORS_VALUES else "RGB"


def parse_percent(value):
    """Parse Percent -> float; empty or invalid -> 0.0."""
    if value is None or value == "":
        return 0.0
    try:
        return float(str(value).strip().replace(",", "."))
    except ValueError:
        return 0.0


def normalize_percents(records):
    """Scale percents of non-N records so that their sum is exactly 100.

    Records with Colors=N keep Percent=0. If all are 0, distribute equally.
    """
    idx = [i for i, r in enumerate(records) if r.get("Colors") != "N"]
    if not idx:
        return
    total = sum(float(records[i].get("Percent", 0) or 0) for i in idx)
    if total == 0:
        share = 100.0 / len(idx)
        for i in idx:
            records[i]["Percent"] = share
    else:
        for i in idx:
            records[i]["Percent"] = float(records[i]["Percent"]) * 100.0 / total


def _fmt2(v):
    """Format with 2 decimals, trailing zeros trimmed: 0.20 -> 0.2, 1.00 -> 1."""
    s = ("%.2f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("", "-", "-0") else s


def region_display(values):
    """Format parsed values for the list: 'x:.. y:..' ['r:..' | 'w:.. h:..']."""
    if not values:
        return ""
    parts = ["x:" + _fmt2(values[0]), "y:" + _fmt2(values[1])]
    if len(values) == 3:
        parts.append("r:" + _fmt2(values[2]))
    elif len(values) == 4:
        parts.append("w:" + _fmt2(values[2]))
        parts.append("h:" + _fmt2(values[3]))
    return " ".join(parts)


def percent_display(rec):
    """' 30%' style suffix after Colors; empty when 0 or Colors=N."""
    if rec.get("Colors") == "N":
        return ""
    p = float(rec.get("Percent", 0) or 0)
    if p == 0:
        return ""
    return " " + _fmt2(p) + "%"


def record_list_line(rec):
    """One line of the records list: 'Colors X%; x:.. y:.. ..; [Parameters]'."""
    values, err = parse_region(rec.get("Region", ""))
    if err:
        return "#err"
    params = (rec.get("Parameters", "") or "").strip()
    return "%s%s; %s; [%s]" % (
        normalize_colors(rec.get("Colors", "RGB")),
        percent_display(rec),
        region_display(values),
        params,
    )


def normalize_data(data):
    """List of raw dicts -> list of normalized records."""
    records = []
    if isinstance(data, dict):
        data = data.get("records", [])
    if not isinstance(data, list):
        raise ValueError("Некорректный формат данных")
    for item in data:
        if not isinstance(item, dict):
            item = {"Colors": str(item), "Region": "", "Parameters": ""}
        records.append(
            {
                "Colors": normalize_colors(item.get("Colors", "RGB")),
                "Percent": 0.0 if normalize_colors(item.get("Colors", "RGB")) == "N"
                else parse_percent(item.get("Percent", 0)),
                "Region": str(item.get("Region", "") or ""),
                "Parameters": str(item.get("Parameters", "") or ""),
            }
        )
    return records


def load_file(name):
    with open(name, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = data.get("records", [])
    return normalize_data(data)


def save_file(name, records):
    with open(name, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


# ---------------- config ----------------

def config_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_NAME)


def load_config():
    cfg = {"last_file": "", "templates": DEFAULT_TEMPLATES}
    try:
        with open(config_path(), "r", encoding="utf-8") as f:
            stored = json.load(f)
        if isinstance(stored, dict):
            cfg["last_file"] = stored.get("last_file", "") or ""
            tpl = stored.get("templates")
            if isinstance(tpl, dict) and tpl:
                cfg["templates"] = tpl
    except (OSError, ValueError):
        pass
    return cfg


def save_config(cfg):
    try:
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


# ---------------- GUI ----------------

class App(tk.Tk):
    def __init__(self, filename=None, data=None, create_missing=False):
        super().__init__()
        self.title("SDGP - настройки")
        self.geometry("760x480")
        self.cfg = load_config()
        self.filename = filename
        self.modified = False
        if data is not None:
            self.records = normalize_data(data)
        elif filename and os.path.isfile(filename):
            try:
                self.records = load_file(filename)
            except (OSError, ValueError) as e:
                messagebox.showerror("SDGP", "Ошибка открытия файла:\n%s" % e)
                self.records = []
        else:
            self.records = []
        self.result = None  # data returned to caller
        normalize_percents(self.records)
        self._build_ui()
        self._fill_list(select_last=True)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        if create_missing and filename and not os.path.isfile(filename):
            self.after(100, lambda: self.open_missing(filename))

    # ----- UI construction -----

    def _build_ui(self):
        # 1. file controls
        ffile = ttk.Frame(self)
        ffile.pack(fill=tk.X, padx=6, pady=4)
        fpath = ttk.Frame(ffile)
        fpath.pack(fill=tk.X)
        ttk.Label(fpath, text="Current file:").pack(side=tk.LEFT)
        self.var_file = tk.StringVar(value=self.filename or "")
        ent = ttk.Entry(fpath, textvariable=self.var_file, state="readonly")
        ent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        frow = ttk.Frame(ffile)
        frow.pack(fill=tk.X)
        ttk.Button(frow, text="Template", command=self.open_template).pack(side=tk.LEFT, padx=3)
        ttk.Button(frow, text="Open", command=self.open_file).pack(side=tk.LEFT)

        # 2. input + table: two equal columns
        fmid = ttk.Frame(self)
        fmid.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        fmid.columnconfigure(0, weight=1, uniform="mid")
        fmid.columnconfigure(1, weight=1, uniform="mid")
        fmid.rowconfigure(0, weight=1)

        # input area
        finput = ttk.Frame(fmid)
        finput.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        ttk.Label(finput, text="Colors / Percent").pack(anchor=tk.W)
        frow = ttk.Frame(finput)
        frow.pack(fill=tk.X)
        self.var_colors = tk.StringVar()
        self.cmb_colors = ttk.Combobox(
            frow, textvariable=self.var_colors, values=COLORS_VALUES, state="readonly"
        )
        self.cmb_colors.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.cmb_colors.bind("<<ComboboxSelected>>", lambda e: self.on_colors_change())
        self.var_percent = tk.StringVar()
        self.ent_percent = ttk.Entry(frow, textvariable=self.var_percent, width=9)
        self.ent_percent.pack(side=tk.LEFT, padx=(4, 0))
        ttk.Label(finput, text="Region").pack(anchor=tk.W, pady=(8, 0))
        self.var_region = tk.StringVar()
        ttk.Entry(finput, textvariable=self.var_region).pack(fill=tk.X)
        ttk.Label(finput, text="Parameters").pack(anchor=tk.W, pady=(8, 0))
        fparams = ttk.Frame(finput)
        fparams.pack(fill=tk.BOTH, expand=True)
        self.txt_params = tk.Text(fparams, wrap=tk.WORD, height=6)
        sbp = ttk.Scrollbar(fparams, orient=tk.VERTICAL, command=self.txt_params.yview)
        self.txt_params.config(yscrollcommand=sbp.set)
        sbp.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_params.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        fbtn = ttk.Frame(finput)
        fbtn.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(fbtn, text="New", command=self.input_new).pack(side=tk.LEFT, padx=3)
        ttk.Button(fbtn, text="Add", command=self.input_add).pack(side=tk.LEFT, padx=3)
        ttk.Button(fbtn, text="Update", command=self.field_changed).pack(side=tk.LEFT, padx=3)

        # table area
        ftable = ttk.Frame(fmid)
        ftable.grid(row=0, column=1, sticky="nsew")
        self.lst = tk.Listbox(ftable, activestyle="dotbox", exportselection=False)
        sb = ttk.Scrollbar(ftable, orient=tk.VERTICAL, command=self.lst.yview)
        self.lst.config(yscrollcommand=sb.set)
        self.lst.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.LEFT, fill=tk.Y)
        self.lst.bind("<<ListboxSelect>>", self.on_select)

        # 3. control buttons: record management row (right-aligned)
        fctl = ttk.Frame(self)
        fctl.pack(fill=tk.X, padx=6, pady=(4, 0))
        ttk.Button(fctl, text="Dn", command=lambda: self.rec_move(1)).pack(side=tk.RIGHT, padx=3)
        ttk.Button(fctl, text="Up", command=lambda: self.rec_move(-1)).pack(side=tk.RIGHT, padx=3)
        ttk.Button(fctl, text="Del", command=self.rec_delete).pack(side=tk.RIGHT, padx=3)
        ttk.Button(fctl, text="Copy", command=self.rec_copy).pack(side=tk.RIGHT, padx=3)
        ttk.Button(fctl, text="Check", command=self.check_current).pack(side=tk.RIGHT, padx=3)
        ttk.Label(fctl, text="Record:").pack(side=tk.RIGHT, padx=(0, 8))

        # table management row (right-aligned)
        fctl2 = ttk.Frame(self)
        fctl2.pack(fill=tk.X, padx=6, pady=4)
        ttk.Button(fctl2, text="Close", command=self.on_close).pack(side=tk.RIGHT, padx=3)
        ttk.Button(fctl2, text="Cancel", command=self.cancel).pack(side=tk.RIGHT, padx=3)
        ttk.Button(fctl2, text="Save as", command=self.save_as).pack(side=tk.RIGHT, padx=3)
        ttk.Button(fctl2, text="Save", command=self.save).pack(side=tk.RIGHT, padx=3)
        ttk.Button(fctl2, text="Check", command=self.check_all).pack(side=tk.RIGHT, padx=3)
        ttk.Label(fctl2, text="Table:").pack(side=tk.RIGHT, padx=(0, 8))

    # ----- helpers -----

    def _cur_index(self):
        sel = self.lst.curselection()
        return sel[0] if sel else None

    def _fill_list(self, select_last=False, keep_index=None):
        self.lst.delete(0, tk.END)
        for rec in self.records:
            self.lst.insert(tk.END, record_list_line(rec))
        if keep_index is not None and keep_index < self.lst.size():
            self.lst.selection_set(keep_index)
            self.lst.activate(keep_index)
            self.lst.see(keep_index)
        elif select_last and self.lst.size():
            i = self.lst.size() - 1
            self.lst.selection_set(i)
            self.lst.activate(i)
            self.lst.see(i)
        self.show_current()

    def show_current(self):
        i = self._cur_index()
        if i is None:
            return
        self._set_input(self.records[i])

    def on_select(self, _e=None):
        # save edits of previous record happens in field_changed
        self.show_current()

    def field_changed(self):
        i = self._cur_index()
        if i is None:
            return
        rec = self.records[i]
        new = self._record_from_input()
        if new != rec:
            self.records[i] = new
            self.modified = True
            self.lst.delete(i)
            self.lst.insert(i, record_list_line(new))
            self.lst.selection_set(i)
            self.lst.activate(i)

    # ----- record buttons -----

    def _record_from_input(self):
        percent = 0.0 if self.var_colors.get() == "N" else parse_percent(self.var_percent.get())
        return {
            "Colors": normalize_colors(self.var_colors.get()),
            "Percent": percent,
            "Region": self.var_region.get(),
            "Parameters": self.txt_params.get("1.0", tk.END).rstrip("\n"),
        }

    def _set_input(self, rec):
        self.var_colors.set(rec["Colors"])
        self.var_region.set(rec["Region"])
        self.txt_params.delete("1.0", tk.END)
        self.txt_params.insert("1.0", rec["Parameters"])
        self.var_percent.set(_fmt2(float(rec.get("Percent", 0) or 0)))
        self._update_percent_state()

    def _update_percent_state(self):
        if self.var_colors.get() == "N":
            self.var_percent.set("0")
            self.ent_percent.state(["disabled"])
        else:
            self.ent_percent.state(["!disabled"])

    def on_colors_change(self):
        self._update_percent_state()

    def input_new(self):
        """Reset the input fields to the Normal template."""
        self._set_input(normalize_data(DEFAULT_TEMPLATES["Normal"])[0])

    def input_add(self):
        """Add a record composed from the input fields."""
        self.records.append(self._record_from_input())
        self.modified = True
        self._fill_list(select_last=True)

    def rec_copy(self):
        """Duplicate the current record and select the copy."""
        i = self._cur_index()
        if i is None:
            return
        self.records.insert(i + 1, dict(self.records[i]))
        self.modified = True
        self._fill_list(keep_index=i + 1)

    def rec_delete(self):
        i = self._cur_index()
        if i is None:
            return
        del self.records[i]
        self.modified = True
        keep = min(i, len(self.records) - 1)
        self._fill_list(keep_index=keep if keep >= 0 else None)

    def rec_move(self, delta):
        i = self._cur_index()
        if i is None:
            return
        j = i + delta
        if not (0 <= j < len(self.records)):
            return
        self.records[i], self.records[j] = self.records[j], self.records[i]
        self.modified = True
        self._fill_list(keep_index=j)

    # ----- validation -----

    def apply_normalization(self):
        """Normalize percents to 100 and refresh the list."""
        normalize_percents(self.records)
        self._fill_list(keep_index=self._cur_index())

    def check_current(self, show_ok=True):
        self.apply_normalization()
        _, err = parse_region(self.var_region.get())
        if err:
            messagebox.showerror("Проверка Region", err)
            return False
        if show_ok:
            messagebox.showinfo("Проверка Region", "Ошибок нет")
        return True

    def check_all(self, show_ok=True):
        self.apply_normalization()
        errors = []
        for n, rec in enumerate(self.records, 1):
            _, err = parse_region(rec.get("Region", ""))
            if err:
                errors.append("Запись %d: %s" % (n, err))
        if errors:
            messagebox.showerror("Проверка Region", "\n".join(errors))
            return False
        if show_ok:
            messagebox.showinfo("Проверка Region", "Ошибок нет")
        return True

    # ----- file operations -----

    def open_file(self):
        if not self.ask_save_if_modified():
            return
        name = filedialog.askopenfilename(
            title="Открыть файл sdgp",
            filetypes=[("SDGP files", "*.sdgp"), ("All files", "*.*")],
        )
        if not name:
            return
        if not os.path.isfile(name):
            self.open_missing(name)
            return
        try:
            self.records = load_file(name)
        except (OSError, ValueError) as e:
            messagebox.showerror("SDGP", "Ошибка открытия файла:\n%s" % e)
            return
        self.filename = name
        self.var_file.set(name)
        self.modified = False
        normalize_percents(self.records)
        self._fill_list(select_last=True)

    def open_template(self):
        """Pick a template, then choose the file name like 'Save as'."""
        if not self.ask_save_if_modified():
            return
        templates = list(self.cfg.get("templates", {}).keys())
        if not templates:
            return
        tpl = TemplateDialog(self, templates).result
        if tpl is None:
            return
        name = filedialog.asksaveasfilename(
            title="Save as",
            defaultextension=".sdgp",
            filetypes=[("SDGP files", "*.sdgp"), ("All files", "*.*")],
        )
        if not name:
            return
        self.records = normalize_data(self.cfg["templates"][tpl])
        normalize_percents(self.records)
        self._do_save(name)

    def open_missing(self, name):
        """File does not exist: offer a template, else empty."""
        templates = list(self.cfg.get("templates", {}).keys())
        answer = messagebox.askyesnocancel(
            "SDGP",
            "Файл '%s' не существует.\nСоздать новый файл из шаблона?" % name,
        )
        if answer is None:
            return
        if answer:
            tpl = TemplateDialog(self, templates).result
            if tpl is None:
                return
            self.records = normalize_data(self.cfg["templates"][tpl])
        else:
            self.records = []
        # create the new file with the entered name
        self._do_save(name)

    def _do_save(self, name):
        if not self.check_all(show_ok=False):
            return False
        try:
            save_file(name, self.records)
        except OSError as e:
            messagebox.showerror("SDGP", "Ошибка сохранения:\n%s" % e)
            return False
        self.filename = name
        self.var_file.set(name)
        self.modified = False
        self._fill_list(keep_index=self._cur_index())
        return True

    def save(self):
        if not self.check_all(show_ok=False):
            return False
        if not self.filename:
            return self.save_as()
        return self._do_save(self.filename)

    def save_as(self):
        if not self.check_all(show_ok=False):
            return False
        name = filedialog.asksaveasfilename(
            title="Сохранить как",
            defaultextension=".sdgp",
            filetypes=[("SDGP files", "*.sdgp"), ("All files", "*.*")],
        )
        if not name:
            return False
        return self._do_save(name)

    def cancel(self):
        if not self.ask_save_if_modified():
            return
        if self.filename and os.path.isfile(self.filename):
            try:
                self.records = load_file(self.filename)
            except (OSError, ValueError) as e:
                messagebox.showerror("SDGP", "Ошибка открытия файла:\n%s" % e)
                return
        else:
            self.records = []
        self.modified = False
        normalize_percents(self.records)
        self._fill_list(select_last=True)

    # ----- close -----

    def ask_save_if_modified(self):
        if not self.modified:
            return True
        ans = messagebox.askyesnocancel(
            "SDGP", "Данные изменены. Сохранить изменения?"
        )
        if ans is None:
            return False
        if ans:
            return self.save()
        self.modified = False
        return True

    def on_close(self):
        if not self.ask_save_if_modified():
            return
        normalize_percents(self.records)
        self.result = self.records
        self.cfg["last_file"] = self.filename or ""
        save_config(self.cfg)
        self.destroy()


class TemplateDialog(tk.Toplevel):
    def __init__(self, master, names):
        super().__init__(master)
        self.title("Выбор шаблона")
        self.result = None
        if master.winfo_viewable():
            self.transient(master)
        ttk.Label(self, text="Шаблон:").pack(padx=10, pady=6)
        initial = "Normal" if "Normal" in names else (names[0] if names else "")
        self.var = tk.StringVar(value=initial)
        cmb = ttk.Combobox(self, textvariable=self.var, values=names, state="readonly")
        cmb.pack(padx=10, fill=tk.X)
        f = tk.Frame(self)
        f.pack(pady=8)
        ttk.Button(f, text="OK", command=self._ok).pack(side=tk.LEFT, padx=4)
        ttk.Button(f, text="Отмена", command=self.destroy).pack(side=tk.LEFT, padx=4)
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        self.geometry("+%d+%d" % ((sw - w) // 2, (sh - h) // 2))
        self.deiconify()
        self.lift()
        self.focus_set()
        self.wait_visibility()
        self.grab_set()
        self.wait_window()

    def _ok(self):
        self.result = self.var.get()
        self.destroy()


# ---------------- standalone / API ----------------

def _run_app(filename=None, data=None, create_missing=False):
    app = App(filename=filename, data=data, create_missing=create_missing)
    app.mainloop()
    return app.result


def OpenDlg():
    """Run standalone; returns new data."""
    cfg = load_config()
    last = cfg.get("last_file", "")
    if last and os.path.isfile(last):
        return _run_app(filename=last)
    # no last file (or it is missing): show open dialog (allows a new name)
    root = tk.Tk()
    root.withdraw()
    name = filedialog.askopenfilename(
        title="Открыть файл sdgp",
        filetypes=[("SDGP files", "*.sdgp"), ("All files", "*.*")],
    )
    root.destroy()
    if not name:
        return None
    return _run_app(filename=name)


def OpenFile(file_name):
    """Open form with the given file; returns new data."""
    return _run_app(filename=file_name)


def OpenData(data):
    """Show passed data for modification; returns new data."""
    return _run_app(data=data)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    filename = None
    template = None
    args = list(argv)
    while args:
        a = args.pop(0)
        if a == "-t":
            if args:
                template = args.pop(0)
        else:
            filename = a
    if template is not None:
        cfg = load_config()
        tpl = cfg.get("templates", {}).get(template)
        if tpl is None:
            print("Шаблон '%s' не найден" % template)
            return 1
        return 0 if _run_app(data=normalize_data(tpl)) is not None else 1
    if filename:
        if os.path.isfile(filename):
            return 0 if _run_app(filename=filename) is not None else 1
        # missing file given on command line: new-file flow inside the app
        return 0 if _run_app(filename=filename, create_missing=True) is not None else 1
    result = OpenDlg()
    return 0 if result is not None else 1


if __name__ == "__main__":
    sys.exit(main())
