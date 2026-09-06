"""
Font Text Exporter
------------------
Een kleine Windows-desktopapp waarmee je een eigen lettertype (TTF/OTF)
kunt uploaden, tekst kunt typen in dat lettertype, en het resultaat kunt
exporteren als PNG, JPEG/JPG, SVG of PDF.

Gebouwd met: tkinter (GUI), Pillow (rasterbeelden), ReportLab (PDF).
"""

import os
import io
import base64
import shutil
import tempfile
import tkinter as tk
from tkinter import ttk, filedialog, colorchooser, messagebox

from PIL import Image, ImageDraw, ImageFont, ImageTk

try:
    from reportlab.pdfgen import canvas as pdf_canvas
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase import pdfmetrics
    REPORTLAB_OK = True
except Exception:
    REPORTLAB_OK = False


APP_TITLE = "Font Text Exporter"
PADDING = 24
PX_TO_PT = 72.0 / 96.0  # omrekening van pixels (96 dpi scherm) naar PDF-punten


def hex_to_rgb(hex_color: str):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


class FontManager:
    """Beheert geuploade lettertypes: kopieert ze naar een eigen map zodat
    de app ze ook na herstart nog kan vinden."""

    def __init__(self):
        base_dir = os.path.join(os.path.expanduser("~"), ".font_text_exporter", "fonts")
        os.makedirs(base_dir, exist_ok=True)
        self.storage_dir = base_dir
        self.fonts = {}  # naam -> pad
        self._load_existing()

    def _load_existing(self):
        for fname in os.listdir(self.storage_dir):
            if fname.lower().endswith((".ttf", ".otf")):
                path = os.path.join(self.storage_dir, fname)
                self.fonts[os.path.splitext(fname)[0]] = path

    def add_font(self, source_path: str) -> str:
        fname = os.path.basename(source_path)
        dest = os.path.join(self.storage_dir, fname)
        if os.path.abspath(source_path) != os.path.abspath(dest):
            shutil.copyfile(source_path, dest)
        name = os.path.splitext(fname)[0]
        self.fonts[name] = dest
        return name

    def get_path(self, name: str) -> str:
        return self.fonts.get(name)


class FontTextExporterApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("900x600")
        self.root.minsize(760, 520)

        self.font_manager = FontManager()
        self.text_color = (0, 0, 0)
        self.bg_color = (255, 255, 255)
        self.transparent_bg = tk.BooleanVar(value=False)

        self._build_ui()
        self._refresh_font_list()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(2, weight=1)

        # -- Fontbeheer --------------------------------------------------
        font_frame = ttk.LabelFrame(main, text="Lettertype", padding=10)
        font_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        font_frame.columnconfigure(1, weight=1)

        ttk.Button(font_frame, text="Font uploaden...", command=self.upload_font).grid(
            row=0, column=0, padx=(0, 10)
        )

        self.font_var = tk.StringVar()
        self.font_combo = ttk.Combobox(font_frame, textvariable=self.font_var, state="readonly")
        self.font_combo.grid(row=0, column=1, sticky="ew")
        self.font_combo.bind("<<ComboboxSelected>>", lambda e: self.update_preview())

        ttk.Label(font_frame, text="Grootte:").grid(row=0, column=2, padx=(10, 4))
        self.size_var = tk.IntVar(value=48)
        size_spin = ttk.Spinbox(
            font_frame, from_=8, to=400, textvariable=self.size_var, width=6,
            command=self.update_preview,
        )
        size_spin.grid(row=0, column=3)
        size_spin.bind("<KeyRelease>", lambda e: self.update_preview())

        # -- Kleuren -------------------------------------------------------
        color_frame = ttk.Frame(font_frame)
        color_frame.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(10, 0))

        ttk.Button(color_frame, text="Tekstkleur...", command=self.pick_text_color).pack(side="left")
        self.text_color_swatch = tk.Canvas(color_frame, width=24, height=24, bg="#000000", highlightthickness=1)
        self.text_color_swatch.pack(side="left", padx=(6, 20))

        ttk.Button(color_frame, text="Achtergrondkleur...", command=self.pick_bg_color).pack(side="left")
        self.bg_color_swatch = tk.Canvas(color_frame, width=24, height=24, bg="#ffffff", highlightthickness=1)
        self.bg_color_swatch.pack(side="left", padx=(6, 20))

        ttk.Checkbutton(
            color_frame, text="Transparante achtergrond (PNG/SVG)",
            variable=self.transparent_bg, command=self.update_preview,
        ).pack(side="left")

        # -- Tekstinvoer -----------------------------------------------
        text_frame = ttk.LabelFrame(main, text="Tekst", padding=10)
        text_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        text_frame.columnconfigure(0, weight=1)

        self.text_box = tk.Text(text_frame, height=5, wrap="word", font=("Segoe UI", 11))
        self.text_box.grid(row=0, column=0, sticky="ew")
        self.text_box.insert("1.0", "Typ hier je tekst...")
        self.text_box.bind("<KeyRelease>", lambda e: self.update_preview())

        # -- Voorbeeld ----------------------------------------------------
        preview_frame = ttk.LabelFrame(main, text="Voorbeeld", padding=10)
        preview_frame.grid(row=2, column=0, columnspan=2, sticky="nsew")
        preview_frame.rowconfigure(0, weight=1)
        preview_frame.columnconfigure(0, weight=1)

        self.preview_canvas = tk.Canvas(preview_frame, bg="#d9d9d9")
        self.preview_canvas.grid(row=0, column=0, sticky="nsew")
        self._preview_imgtk = None

        # -- Exportknoppen -----------------------------------------------
        export_frame = ttk.Frame(main, padding=(0, 10, 0, 0))
        export_frame.grid(row=3, column=0, columnspan=2, sticky="ew")

        ttk.Button(export_frame, text="Opslaan als...", command=self.export_dialog).pack(side="right")

    # -------------------------------------------------------------- events
    def upload_font(self):
        path = filedialog.askopenfilename(
            title="Kies een lettertype",
            filetypes=[("Lettertypes", "*.ttf *.otf"), ("Alle bestanden", "*.*")],
        )
        if not path:
            return
        try:
            name = self.font_manager.add_font(path)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Kon lettertype niet laden:\n{exc}")
            return
        self._refresh_font_list(select=name)
        self.update_preview()

    def _refresh_font_list(self, select: str = None):
        names = sorted(self.font_manager.fonts.keys())
        self.font_combo["values"] = names
        if select and select in names:
            self.font_var.set(select)
        elif names and not self.font_var.get():
            self.font_var.set(names[0])

    def pick_text_color(self):
        result = colorchooser.askcolor(color=self._rgb_to_hex(self.text_color))
        if result and result[1]:
            self.text_color = hex_to_rgb(result[1])
            self.text_color_swatch.configure(bg=result[1])
            self.update_preview()

    def pick_bg_color(self):
        result = colorchooser.askcolor(color=self._rgb_to_hex(self.bg_color))
        if result and result[1]:
            self.bg_color = hex_to_rgb(result[1])
            self.bg_color_swatch.configure(bg=result[1])
            self.update_preview()

    @staticmethod
    def _rgb_to_hex(rgb):
        return "#%02x%02x%02x" % rgb

    # ------------------------------------------------------------- render
    def _current_font_path(self):
        name = self.font_var.get()
        if not name:
            return None
        return self.font_manager.get_path(name)

    def _get_text(self):
        return self.text_box.get("1.0", "end-1c")

    def render_image(self) -> Image.Image:
        font_path = self._current_font_path()
        if not font_path:
            raise ValueError("Upload eerst een lettertype (.ttf of .otf).")

        text = self._get_text() or " "
        size = max(1, int(self.size_var.get()))
        pil_font = ImageFont.truetype(font_path, size)

        lines = text.split("\n") or [" "]
        tmp = Image.new("RGBA", (10, 10))
        draw = ImageDraw.Draw(tmp)

        widths = []
        line_height = int(size * 1.3)
        for line in lines:
            probe = line if line else " "
            bbox = draw.textbbox((0, 0), probe, font=pil_font)
            widths.append(bbox[2] - bbox[0])

        max_width = max(widths) if widths else size
        total_height = line_height * len(lines)

        width = max_width + PADDING * 2
        height = total_height + PADDING * 2

        transparent = self.transparent_bg.get()
        mode = "RGBA"
        bg = (0, 0, 0, 0) if transparent else (*self.bg_color, 255)

        img = Image.new(mode, (max(width, 1), max(height, 1)), bg)
        draw = ImageDraw.Draw(img)

        y = PADDING
        for line in lines:
            draw.text((PADDING, y), line, font=pil_font, fill=(*self.text_color, 255))
            y += line_height

        return img

    def update_preview(self):
        try:
            img = self.render_image()
        except Exception:
            return

        canvas_w = max(self.preview_canvas.winfo_width(), 200)
        canvas_h = max(self.preview_canvas.winfo_height(), 200)

        preview = img.copy()
        preview.thumbnail((canvas_w - 20, canvas_h - 20))

        # checkerboard voor transparantie
        if preview.mode == "RGBA":
            checker = Image.new("RGBA", preview.size, (255, 255, 255, 255))
            tile = 10
            cdraw = ImageDraw.Draw(checker)
            for yy in range(0, preview.size[1], tile):
                for xx in range(0, preview.size[0], tile):
                    if (xx // tile + yy // tile) % 2 == 0:
                        cdraw.rectangle([xx, yy, xx + tile, yy + tile], fill=(230, 230, 230, 255))
            checker.alpha_composite(preview)
            preview = checker

        self._preview_imgtk = ImageTk.PhotoImage(preview)
        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(canvas_w // 2, canvas_h // 2, image=self._preview_imgtk)

    # ------------------------------------------------------------- export
    def export_dialog(self):
        if not self._current_font_path():
            messagebox.showwarning(APP_TITLE, "Upload eerst een lettertype.")
            return

        path = filedialog.asksaveasfilename(
            title="Opslaan als",
            defaultextension=".png",
            filetypes=[
                ("PNG-afbeelding", "*.png"),
                ("JPEG-afbeelding", "*.jpg *.jpeg"),
                ("SVG-vectorafbeelding", "*.svg"),
                ("PDF-document", "*.pdf"),
            ],
        )
        if not path:
            return

        ext = os.path.splitext(path)[1].lower()
        try:
            if ext == ".png":
                self.export_png(path)
            elif ext in (".jpg", ".jpeg"):
                self.export_jpeg(path)
            elif ext == ".svg":
                self.export_svg(path)
            elif ext == ".pdf":
                self.export_pdf(path)
            else:
                messagebox.showerror(APP_TITLE, f"Onbekende extensie: {ext}")
                return
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Exporteren mislukt:\n{exc}")
            return

        messagebox.showinfo(APP_TITLE, f"Opgeslagen als:\n{path}")

    def export_png(self, path):
        img = self.render_image()
        img.save(path, "PNG")

    def export_jpeg(self, path):
        img = self.render_image()
        if img.mode == "RGBA":
            bg = Image.new("RGB", img.size, self.bg_color if not self.transparent_bg.get() else (255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            img = bg
        img.save(path, "JPEG", quality=95)

    def export_svg(self, path):
        font_path = self._current_font_path()
        with open(font_path, "rb") as f:
            font_b64 = base64.b64encode(f.read()).decode("ascii")
        ext = os.path.splitext(font_path)[1].lower()
        fmt = "truetype" if ext == ".ttf" else "opentype"

        text = self._get_text() or " "
        size = max(1, int(self.size_var.get()))
        lines = text.split("\n")

        pil_font = ImageFont.truetype(font_path, size)
        tmp = Image.new("RGBA", (10, 10))
        draw = ImageDraw.Draw(tmp)
        widths = []
        line_height = int(size * 1.3)
        for line in lines:
            probe = line if line else " "
            bbox = draw.textbbox((0, 0), probe, font=pil_font)
            widths.append(bbox[2] - bbox[0])
        max_width = max(widths) if widths else size

        width = max_width + PADDING * 2
        height = line_height * len(lines) + PADDING * 2

        color_hex = self._rgb_to_hex(self.text_color)
        transparent = self.transparent_bg.get()
        bg_rect = "" if transparent else (
            f'<rect x="0" y="0" width="{width}" height="{height}" fill="{self._rgb_to_hex(self.bg_color)}"/>'
        )

        tspans = ""
        y = PADDING + int(size * 0.9)
        for line in lines:
            escaped = (
                line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            )
            tspans += f'<tspan x="{PADDING}" y="{y}">{escaped}</tspan>'
            y += line_height

        svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<defs>
<style>
@font-face {{
  font-family: "UploadedFont";
  src: url(data:font/{fmt};charset=utf-8;base64,{font_b64}) format("{fmt}");
}}
text {{
  font-family: "UploadedFont";
  font-size: {size}px;
  fill: {color_hex};
  white-space: pre;
}}
</style>
</defs>
{bg_rect}
<text>{tspans}</text>
</svg>'''

        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)

    def export_pdf(self, path):
        if not REPORTLAB_OK:
            raise RuntimeError("ReportLab is niet geinstalleerd.")

        font_path = self._current_font_path()
        text = self._get_text() or " "
        size = max(1, int(self.size_var.get()))
        lines = text.split("\n")

        font_name = "UploadedFont"
        try:
            pdfmetrics.registerFont(TTFont(font_name, font_path))
        except Exception:
            font_name = "Helvetica"

        pil_font = ImageFont.truetype(font_path, size)
        tmp = Image.new("RGBA", (10, 10))
        draw = ImageDraw.Draw(tmp)
        widths = []
        line_height_px = size * 1.3
        for line in lines:
            probe = line if line else " "
            bbox = draw.textbbox((0, 0), probe, font=pil_font)
            widths.append(bbox[2] - bbox[0])
        max_width_px = max(widths) if widths else size

        page_w = (max_width_px + PADDING * 2) * PX_TO_PT
        page_h = (line_height_px * len(lines) + PADDING * 2) * PX_TO_PT

        c = pdf_canvas.Canvas(path, pagesize=(max(page_w, 10), max(page_h, 10)))

        if not self.transparent_bg.get():
            c.setFillColorRGB(*(v / 255 for v in self.bg_color))
            c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

        c.setFont(font_name, size * PX_TO_PT)
        c.setFillColorRGB(*(v / 255 for v in self.text_color))

        y = page_h - PADDING * PX_TO_PT - size * PX_TO_PT * 0.8
        for line in lines:
            c.drawString(PADDING * PX_TO_PT, y, line)
            y -= line_height_px * PX_TO_PT

        c.save()


def main():
    root = tk.Tk()
    app = FontTextExporterApp(root)
    root.after(200, app.update_preview)
    root.bind("<Configure>", lambda e: app.update_preview())
    root.mainloop()


if __name__ == "__main__":
    main()
