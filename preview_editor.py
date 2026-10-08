import tkinter as tk
from tkinter import filedialog, messagebox

import pymupdf
from PIL import Image, ImageTk

from config import ExportSettings
from utils import ensure_parent_dir, format_height_status


class LayoutPreviewDialog:
    def __init__(self, parent, snippets, app_reference, prev_strip_height=0, settings: ExportSettings | None = None):
        self.top = tk.Toplevel(parent)
        self.top.title("Master Flow Preview & Page Break Editor")
        self.top.geometry("1250x900")
        self.top.configure(bg="#1f2933")

        self.snippets = list(snippets)
        self.app_ref = app_reference
        self.settings = settings or ExportSettings()

        self.A4_W = self.settings.page_width_px
        self.A4_H = self.settings.page_height_px
        self.MARGIN = self.settings.margin_px
        self.USABLE_H = self.settings.usable_height_px

        original_snippets = self.snippets
        original_total_h = sum(img.height for img in original_snippets)
        normalized_snippets = []
        for img in original_snippets:
            if img.width == self.A4_W:
                normalized_snippets.append(img)
            else:
                resized_h = max(1, round(img.height * self.A4_W / img.width))
                normalized_snippets.append(
                    img.resize((self.A4_W, resized_h), Image.Resampling.LANCZOS)
                )

        def rescale_y(y):
            y = max(0, min(y, original_total_h))
            old_top = 0
            new_top = 0
            for old_img, new_img in zip(original_snippets, normalized_snippets):
                old_bottom = old_top + old_img.height
                new_bottom = new_top + new_img.height
                if y <= old_bottom:
                    return new_top + round((y - old_top) * new_img.height / old_img.height)
                old_top = old_bottom
                new_top = new_bottom
            return new_top

        if self.app_ref.saved_split_y is not None:
            self.app_ref.saved_split_y = sorted(
                {
                    rescale_y(y)
                    for y in self.app_ref.saved_split_y
                    if 0 < y < original_total_h
                }
            )
        prev_strip_height = rescale_y(prev_strip_height)
        self.snippets = normalized_snippets
        self.app_ref.all_snippets = self.snippets

        total_h = sum(img.height for img in self.snippets)
        self.master_strip = Image.new("RGB", (self.A4_W, total_h), (255, 255, 255))
        curr_y = 0
        for img in self.snippets:
            self.master_strip.paste(img, (0, curr_y))
            curr_y += img.height

        if self.app_ref.saved_split_y is not None and len(self.app_ref.saved_split_y) > 0:
            self.split_y = [y for y in self.app_ref.saved_split_y if y < self.master_strip.height]
            last_cut = max(self.split_y) if self.split_y else 0
            pos = max(prev_strip_height, last_cut) + self.USABLE_H
            while pos < self.master_strip.height:
                if pos not in self.split_y:
                    self.split_y.append(pos)
                pos += self.USABLE_H
            self.split_y.sort()
        else:
            self.split_y = []
            pos = self.USABLE_H
            while pos < self.master_strip.height:
                self.split_y.append(pos)
                pos += self.USABLE_H

        self.preview_scale = self.settings.preview_scale
        self.drag_index = None
        self._build_ui()
        self.redraw_canvas()

    def _build_ui(self):
        toolbar = tk.Frame(self.top, bg="#17212b", pady=10, padx=14)
        toolbar.pack(fill=tk.X, side=tk.TOP)

        lbl_info = tk.Label(
            toolbar,
            text="PREVIEW   Drag a cut to move it  ·  Double-click to add  ·  Right-click to remove",
            font=("Segoe UI", 9, "bold"),
            fg="#dbeafe",
            bg="#17212b",
        )
        lbl_info.pack(side=tk.LEFT, padx=5)

        self.zoom_label = tk.Label(toolbar, text="", font=("Segoe UI", 9, "bold"), fg="#cbd5e1", bg="#17212b")
        self.zoom_label.pack(side=tk.RIGHT, padx=8)
        tk.Button(
            toolbar, text="−", command=lambda: self.change_zoom(-0.02),
            font=("Segoe UI", 12, "bold"), bg="#374151", fg="white", relief=tk.FLAT, width=3,
        ).pack(side=tk.RIGHT, padx=2)
        tk.Button(
            toolbar, text="+", command=lambda: self.change_zoom(0.02),
            font=("Segoe UI", 12, "bold"), bg="#374151", fg="white", relief=tk.FLAT, width=3,
        ).pack(side=tk.RIGHT, padx=2)

        btn_clear = tk.Button(
            toolbar,
            text="Remove all cuts",
            command=self.remove_all_cuts,
            font=("Segoe UI", 9, "bold"),
            bg="#7f1d1d",
            fg="white",
            relief=tk.FLAT,
            padx=8,
            pady=4,
        )
        btn_clear.pack(side=tk.LEFT, padx=10)

        btn_append = tk.Button(
            toolbar,
            text="＋ Append PDF",
            command=self.append_another_pdf,
            font=("Segoe UI", 10, "bold"),
            bg="#2563eb",
            fg="white",
            relief=tk.FLAT,
            padx=10,
            pady=5,
        )
        btn_append.pack(side=tk.RIGHT, padx=5)

        btn_export = tk.Button(
            toolbar,
            text="Export PDF",
            command=self.export_pdf,
            font=("Segoe UI", 10, "bold"),
            bg="#059669",
            fg="white",
            relief=tk.FLAT,
            padx=15,
            pady=5,
        )
        btn_export.pack(side=tk.RIGHT, padx=5)

        summary = tk.Frame(self.top, bg="#eaf0f6", padx=14, pady=7)
        summary.pack(fill=tk.X)
        self.summary_label = tk.Label(summary, text="", font=("Segoe UI", 9, "bold"), fg="#334155", bg="#eaf0f6")
        self.summary_label.pack(side=tk.LEFT)
        tk.Label(
            summary,
            text="Wheel to scroll",
            font=("Segoe UI", 9),
            fg="#64748b",
            bg="#eaf0f6",
        ).pack(side=tk.RIGHT)

        frame = tk.Frame(self.top, bg="#202b36")
        frame.pack(fill=tk.BOTH, expand=True)

        self.v_scroll = tk.Scrollbar(frame, orient=tk.VERTICAL)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas = tk.Canvas(frame, bg="#202b36", yscrollcommand=self.v_scroll.set, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.v_scroll.config(command=self.canvas.yview)

        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", self._on_mousewheel)
        self.canvas.bind("<Button-5>", self._on_mousewheel)

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<Button-3>", self.on_right_click)

    def _on_mousewheel(self, event):
        if hasattr(event, "delta"):
            delta = event.delta
        else:
            delta = 120 if event.num == 4 else -120
        self.canvas.yview_scroll(int(-delta / 120), "units")

    def change_zoom(self, amount):
        self.preview_scale = max(0.08, min(0.5, self.preview_scale + amount))
        self.redraw_canvas()

    def save_cuts_to_app(self):
        self.app_ref.saved_split_y = list(self.split_y)

    def redraw_canvas(self):
        self.canvas.delete("all")
        self.save_cuts_to_app()

        display_w = max(1, int(self.A4_W * self.preview_scale))
        display_h = max(1, int(self.master_strip.height * self.preview_scale))
        self.zoom_label.config(text=f"{int(self.preview_scale * 100)}%")

        resized = self.master_strip.resize((display_w, display_h), Image.Resampling.BILINEAR)
        self.tk_preview = ImageTk.PhotoImage(resized)

        self.canvas_x0 = 80
        self.canvas_y0 = 30

        self.canvas.create_rectangle(
            self.canvas_x0 - 5,
            self.canvas_y0 - 5,
            self.canvas_x0 + display_w + 5,
            self.canvas_y0 + display_h + 5,
            fill="#000000",
            outline="",
        )

        self.canvas.create_image(self.canvas_x0, self.canvas_y0, anchor=tk.NW, image=self.tk_preview)

        cuts = [0] + sorted(self.split_y) + [self.master_strip.height]
        self.summary_label.config(
            text=f"{len(cuts) - 1} output pages  ·  {len(self.split_y)} manual cuts  ·  {self.settings.page_dims_label}"
        )
        self.hud_boxes = []

        for i in range(len(cuts) - 1):
            top_px = cuts[i]
            bot_px = cuts[i + 1]
            chunk_h = bot_px - top_px

            top_cy = self.canvas_y0 + int(top_px * self.preview_scale)

            fill_ratio = (chunk_h / self.USABLE_H) * 100
            is_overflow = chunk_h > self.USABLE_H

            hud_bg = "#d63031" if is_overflow else "#2d3436"
            hud_fg = "#ff7675" if is_overflow else "#00cec9"

            page_lbl_id = self.canvas.create_text(
                self.canvas_x0 - 45,
                top_cy + 20,
                text=f"Page {i + 1}",
                font=("Segoe UI", 11, "bold"),
                fill=hud_fg,
            )

            hud_x = self.canvas_x0 + display_w + 20
            hud_y = top_cy + 10

            status_str = " ⚠️ BLEEDS TO NEXT PAGE!" if is_overflow else " ✅ Fits on Page"
            hud_msg = (
                f"Page {i + 1} Capacity:\n"
                f"• Height: {format_height_status(chunk_h, self.USABLE_H)}\n"
                f"• Status:{status_str}"
            )

            bg_id = self.canvas.create_rectangle(
                hud_x,
                hud_y,
                hud_x + 230,
                hud_y + 75,
                fill=hud_bg,
                outline=hud_fg,
                width=2,
            )
            text_id = self.canvas.create_text(
                hud_x + 10,
                hud_y + 37,
                anchor=tk.W,
                text=hud_msg,
                font=("Consolas", 9, "bold"),
                fill="white",
            )

            self.hud_boxes.append((bg_id, text_id, page_lbl_id))

        self.line_ids = []
        for idx, s_y in enumerate(self.split_y):
            cy = self.canvas_y0 + int(s_y * self.preview_scale)
            l_id = self.canvas.create_line(
                self.canvas_x0 - 15,
                cy,
                self.canvas_x0 + display_w + 15,
                cy,
                fill="#ff7675",
                width=4,
                dash=(8, 4),
            )
            self.canvas.create_text(
                self.canvas_x0 + display_w + 10,
                cy - 10,
                anchor=tk.W,
                text=f"Cut {idx + 1} (Right-click to delete)",
                font=("Segoe UI", 9, "bold"),
                fill="#ff7675",
            )
            self.line_ids.append(l_id)

        self.canvas.config(scrollregion=(0, 0, display_w + 350, display_h + 100))

    def on_press(self, event):
        canvas_y = self.canvas.canvasy(event.y)
        for idx, s_y in enumerate(self.split_y):
            cy = self.canvas_y0 + int(s_y * self.preview_scale)
            if abs(canvas_y - cy) < 14:
                self.drag_index = idx
                break

    def on_drag(self, event):
        if self.drag_index is None:
            return

        canvas_y = self.canvas.canvasy(event.y)
        new_strip_y = int((canvas_y - self.canvas_y0) / self.preview_scale)

        min_y = self.split_y[self.drag_index - 1] + self.settings.safe_margin if self.drag_index > 0 else self.settings.safe_margin
        max_y = self.split_y[self.drag_index + 1] - self.settings.safe_margin if self.drag_index < len(self.split_y) - 1 else self.master_strip.height - self.settings.safe_margin
        if min_y > max_y:
            return

        clamped_y = max(min_y, min(new_strip_y, max_y))
        self.split_y[self.drag_index] = clamped_y
        self.redraw_canvas()

    def on_release(self, event):
        self.drag_index = None

    def on_double_click(self, event):
        canvas_y = self.canvas.canvasy(event.y)
        click_strip_y = int((canvas_y - self.canvas_y0) / self.preview_scale)
        canvas_x = self.canvas.canvasx(event.x)
        cut_index = next((i for i, cut in enumerate(self.split_y) if cut >= click_strip_y), len(self.split_y))
        min_y = self.split_y[cut_index - 1] + self.settings.safe_margin if cut_index > 0 else self.settings.safe_margin
        max_y = self.split_y[cut_index] - self.settings.safe_margin if cut_index < len(self.split_y) else self.master_strip.height - self.settings.safe_margin

        if (
            self.canvas_x0 <= canvas_x <= self.canvas_x0 + int(self.A4_W * self.preview_scale)
            and min_y < click_strip_y < max_y
        ):
            self.split_y.append(click_strip_y)
            self.split_y.sort()
            self.redraw_canvas()

    def on_right_click(self, event):
        canvas_y = self.canvas.canvasy(event.y)
        for idx, s_y in enumerate(self.split_y):
            cy = self.canvas_y0 + int(s_y * self.preview_scale)
            if abs(canvas_y - cy) < 14:
                del self.split_y[idx]
                self.redraw_canvas()
                break

    def remove_all_cuts(self):
        self.split_y = []
        self.redraw_canvas()

    def append_another_pdf(self):
        self.save_cuts_to_app()
        if self.app_ref.open_pdf(append=True):
            self.top.destroy()

    def export_pdf(self):
        cuts = [0] + sorted(self.split_y) + [self.master_strip.height]
        output_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")])
        if not output_path:
            return

        out_pdf = pymupdf.open()
        A4_PTS_W = self.settings.output_page_width_pts
        A4_PTS_H = self.settings.output_page_height_pts
        MARGIN_PTS = self.settings.output_margin_pts
        USABLE_PTS_H = A4_PTS_H - (2 * MARGIN_PTS)
        max_segment_px = max(1, int(self.A4_W * (USABLE_PTS_H / A4_PTS_W)))
        one_page_height_px = max(1, int(self.A4_W * (A4_PTS_H / A4_PTS_W)))

        total_pages_created = 0
        try:
            for i in range(len(cuts) - 1):
                top_y = cuts[i]
                bot_y = cuts[i + 1]
                if bot_y <= top_y:
                    continue

                chunk = self.master_strip.crop((0, top_y, self.A4_W, bot_y))
                if chunk.width <= 0 or chunk.height <= 0:
                    continue

                source_h = chunk.height
                offset_y = 0
                segment_limit = one_page_height_px if source_h <= one_page_height_px else max_segment_px
                while offset_y < source_h:
                    seg_h = min(segment_limit, source_h - offset_y)
                    seg = chunk.crop((0, offset_y, chunk.width, offset_y + seg_h))
                    seg_bytes = seg.tobytes("raw", "RGB")
                    seg_pix = pymupdf.Pixmap(pymupdf.csRGB, seg.width, seg.height, seg_bytes, False)

                    page = out_pdf.new_page(width=A4_PTS_W, height=A4_PTS_H)
                    fit_scale = min(A4_PTS_W / seg.width, USABLE_PTS_H / seg.height)
                    draw_w = seg.width * fit_scale
                    draw_h = seg.height * fit_scale
                    left = (A4_PTS_W - draw_w) / 2
                    top = (A4_PTS_H - draw_h) / 2
                    rect = pymupdf.Rect(left, top, left + draw_w, top + draw_h)
                    page.insert_image(rect, pixmap=seg_pix)
                    total_pages_created += 1
                    offset_y += seg_h

            if total_pages_created == 0:
                messagebox.showwarning("Warning", "No pages were exported.")
                return

            output_path = ensure_parent_dir(output_path)
            out_pdf.save(output_path)
        except Exception as exc:
            messagebox.showerror("Export failed", f"The PDF could not be saved.\n\n{exc}")
            return
        finally:
            out_pdf.close()

        messagebox.showinfo("Success", f"PDF compiled successfully!\nTotal Pages: {total_pages_created}\nSaved to:\n{output_path}")
        self.top.destroy()
