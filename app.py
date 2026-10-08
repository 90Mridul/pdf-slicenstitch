import math
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pymupdf
from PIL import Image, ImageTk

from config import ExportSettings
from preview_editor import LayoutPreviewDialog


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, settings: ExportSettings):
        super().__init__(parent)
        self.title("Customize export settings")
        self.geometry("420x420")
        self.settings = settings
        self.transient(parent)
        self.grab_set()

        tk.Label(self, text="Page size", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, padx=12, pady=(12, 4))
        self.page_size = tk.StringVar(value=settings.page_size)
        tk.OptionMenu(self, self.page_size, *settings.page_size_options()).pack(fill=tk.X, padx=12)

        tk.Label(self, text="Margin (px)", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, padx=12, pady=(12, 4))
        self.margin = tk.StringVar(value=str(settings.margin_px))
        tk.Entry(self, textvariable=self.margin).pack(fill=tk.X, padx=12)

        tk.Label(self, text="PDF DPI", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, padx=12, pady=(12, 4))
        self.dpi = tk.StringVar(value=str(settings.pdf_dpi))
        tk.Entry(self, textvariable=self.dpi).pack(fill=tk.X, padx=12)

        tk.Label(self, text="Preview scale", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, padx=12, pady=(12, 4))
        self.preview_scale = tk.StringVar(value=str(settings.preview_scale))
        tk.Entry(self, textvariable=self.preview_scale).pack(fill=tk.X, padx=12)

        tk.Label(self, text="Custom width (px)", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, padx=12, pady=(12, 4))
        self.custom_width = tk.StringVar(value=str(settings.custom_page_size[0]))
        tk.Entry(self, textvariable=self.custom_width).pack(fill=tk.X, padx=12)

        tk.Label(self, text="Custom height (px)", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, padx=12, pady=(12, 4))
        self.custom_height = tk.StringVar(value=str(settings.custom_page_size[1]))
        tk.Entry(self, textvariable=self.custom_height).pack(fill=tk.X, padx=12)

        actions = tk.Frame(self)
        actions.pack(fill=tk.X, padx=12, pady=16)

        tk.Button(actions, text="Apply", command=self.apply_settings, bg="#00b894", fg="white", relief=tk.FLAT, padx=10, pady=6).pack(side=tk.RIGHT)
        tk.Button(actions, text="Cancel", command=self.destroy, bg="#636e72", fg="white", relief=tk.FLAT, padx=10, pady=6).pack(side=tk.RIGHT, padx=(0, 8))

    def apply_settings(self):
        try:
            margin = float(self.margin.get())
            dpi = float(self.dpi.get())
            preview_scale = float(self.preview_scale.get())
            custom_width = float(self.custom_width.get())
            custom_height = float(self.custom_height.get())
            if not all(math.isfinite(value) for value in (margin, dpi, preview_scale, custom_width, custom_height)):
                raise ValueError
            page_size = self.page_size.get()
            if page_size not in self.settings.page_size_options():
                raise ValueError
            margin_px = max(10, int(margin))
            pdf_dpi = max(72, int(dpi))
            preview_scale = max(0.1, min(1.0, preview_scale))
            custom_size = (max(100, int(custom_width)), max(100, int(custom_height)))
            page_height = {"A4": 3508, "Letter": 3100, "Custom": custom_size[1]}[page_size]
            if margin_px * 2 >= page_height:
                raise ValueError
        except (ValueError, OverflowError):
            messagebox.showerror(
                "Invalid settings",
                "Enter valid numbers and leave some usable page height by keeping the margin below half the page height.",
            )
            return

        self.settings.margin_px = margin_px
        self.settings.pdf_dpi = pdf_dpi
        self.settings.preview_scale = preview_scale
        self.settings.update_custom_size(*custom_size)
        self.settings.apply_page_size(page_size)
        self.destroy()


class MultiPDFMasterCropper:
    def __init__(self, root):
        self.root = root
        self.root.title("Continuous Multi-PDF Flow Builder & Layout Editor")
        self.root.geometry("1100x850")
        self.root.configure(bg="#1f2933")

        self.settings = ExportSettings()
        self.pdf_doc = None
        self.pdf_path = ""
        self.current_page_num = 0
        self.total_pages = 0

        self.all_snippets = []
        self.current_pdf_snippet_start = 0
        self.current_pdf_crops = {}
        self.skipped_pages = set()
        self.saved_split_y = None

        self.scale_factor = 1.0
        self.start_y = None
        self.current_y = None
        self.rect_id = None
        self.page_number_var = tk.StringVar(value="1")
        self.status_var = tk.StringVar(value="Open a PDF to get started.")
        self.progress_var = tk.DoubleVar(value=0)
        self._build_ui()
        self.root.bind("<Control-o>", lambda event: self.open_pdf())
        self.page_entry.bind("<Return>", lambda event: self.go_to_page())
        self.canvas.bind("<Left>", lambda event: self.prev_page())
        self.canvas.bind("<Right>", lambda event: self.next_page())

    def _build_ui(self):
        self.root.option_add("*Font", ("Segoe UI", 10))
        header = tk.Frame(self.root, bg="#17212b", padx=20, pady=14)
        header.pack(fill=tk.X)

        title_area = tk.Frame(header, bg="#17212b")
        title_area.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(title_area, text="PaperFlow", font=("Segoe UI", 19, "bold"), fg="#f5f7fa", bg="#17212b").pack(anchor=tk.W)
        tk.Label(
            title_area,
            text="Crop PDF pages into a continuous, print-ready document",
            font=("Segoe UI", 9),
            fg="#aab7c4",
            bg="#17212b",
        ).pack(anchor=tk.W, pady=(2, 0))

        self.btn_settings = tk.Button(
            header,
            text="⚙  Export settings",
            command=self.open_settings,
            font=("Segoe UI", 10, "bold"),
            bg="#374151",
            fg="white",
            activebackground="#4b5563",
            activeforeground="white",
            relief=tk.FLAT,
            padx=14,
            pady=9,
            cursor="hand2",
        )
        self.btn_settings.pack(side=tk.RIGHT, padx=(12, 0))
        self.btn_open = tk.Button(
            header,
            text="＋  Add PDF",
            command=self.open_pdf,
            font=("Segoe UI", 10, "bold"),
            bg="#2563eb",
            fg="white",
            activebackground="#1d4ed8",
            activeforeground="white",
            relief=tk.FLAT,
            padx=16,
            pady=9,
            cursor="hand2",
        )
        self.btn_open.pack(side=tk.RIGHT)

        workflow = tk.Frame(self.root, bg="#263442", padx=20, pady=10)
        workflow.pack(fill=tk.X)
        self.lbl_step = tk.Label(
            workflow,
            text="STEP 1  Open a PDF     →     STEP 2  Drag to crop pages     →     STEP 3  Preview and export",
            font=("Segoe UI", 10, "bold"),
            fg="#dbeafe",
            bg="#263442",
        )
        self.lbl_step.pack(side=tk.LEFT)
        self.lbl_page = tk.Label(workflow, text="No document", font=("Segoe UI", 10), fg="#b7c5d3", bg="#263442")
        self.lbl_page.pack(side=tk.RIGHT)

        controls = tk.Frame(self.root, bg="#f3f6fa", padx=16, pady=10)
        controls.pack(fill=tk.X)
        self.btn_prev = tk.Button(
            controls, text="← Previous", command=self.prev_page, state=tk.DISABLED,
            bg="white", fg="#243447", relief=tk.GROOVE, padx=12, pady=6, cursor="hand2",
        )
        self.btn_prev.pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(controls, text="Page", bg="#f3f6fa", fg="#526273").pack(side=tk.LEFT)
        self.page_entry = tk.Entry(controls, textvariable=self.page_number_var, width=5, justify=tk.CENTER)
        self.page_entry.pack(side=tk.LEFT, padx=5)
        self.btn_go = tk.Button(
            controls, text="Go", command=self.go_to_page, state=tk.DISABLED,
            bg="white", fg="#243447", relief=tk.GROOVE, padx=10, pady=5, cursor="hand2",
        )
        self.btn_go.pack(side=tk.LEFT, padx=(0, 12))
        self.btn_next = tk.Button(
            controls, text="Next →", command=self.next_page, state=tk.DISABLED,
            bg="#059669", fg="white", activebackground="#047857", activeforeground="white",
            relief=tk.FLAT, padx=14, pady=6, cursor="hand2",
        )
        self.btn_next.pack(side=tk.LEFT)

        separator = tk.Frame(controls, width=1, bg="#d7dee7")
        separator.pack(side=tk.LEFT, fill=tk.Y, padx=14, pady=2)
        self.btn_recrop = tk.Button(
            controls, text="Clear crop", command=self.recrop_current_page, state=tk.DISABLED,
            bg="white", fg="#374151", relief=tk.GROOVE, padx=10, pady=6, cursor="hand2",
        )
        self.btn_recrop.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_skip = tk.Button(
            controls, text="Skip page", command=self.toggle_skip_page, state=tk.DISABLED,
            bg="white", fg="#b45309", relief=tk.GROOVE, padx=10, pady=6, cursor="hand2",
        )
        self.btn_skip.pack(side=tk.LEFT)
        self.lbl_count = tk.Label(controls, text="0 crops saved", font=("Segoe UI", 9, "bold"), fg="#526273", bg="#f3f6fa")
        self.lbl_count.pack(side=tk.RIGHT)

        self.progress = ttk.Progressbar(self.root, variable=self.progress_var, maximum=100, mode="determinate")
        self.progress.pack(fill=tk.X)

        canvas_frame = tk.Frame(self.root, bg="#202b36", padx=18, pady=18)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(canvas_frame, bg="#202b36", cursor="crosshair", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self._show_welcome()

        footer = tk.Frame(self.root, bg="#17212b", padx=18, pady=8)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        self.lbl_status = tk.Label(footer, textvariable=self.status_var, font=("Segoe UI", 9), fg="#dbeafe", bg="#17212b")
        self.lbl_status.pack(side=tk.LEFT)
        tk.Label(footer, text="Ctrl+O Open  ·  ← / → Navigate  ·  Enter Go to page", font=("Segoe UI", 8), fg="#9aa9b8", bg="#17212b").pack(side=tk.RIGHT)

    def _show_welcome(self):
        self.canvas.delete("all")
        width = max(self.canvas.winfo_width(), 700)
        height = max(self.canvas.winfo_height(), 450)
        center_x, center_y = width // 2, height // 2
        self.canvas.create_text(center_x, center_y - 48, text="Start with a PDF", font=("Segoe UI", 22, "bold"), fill="#f1f5f9")
        self.canvas.create_text(
            center_x, center_y,
            text="Open a document, drag vertically over a page to keep only that section,\nthen use Preview & Export when you reach the last page.",
            font=("Segoe UI", 11), fill="#bdc9d5", justify=tk.CENTER,
        )
        self.canvas.create_text(center_x, center_y + 62, text="Tip: leave the crop untouched to keep the whole page.", font=("Segoe UI", 9), fill="#7dd3fc")

    def open_settings(self):
        SettingsDialog(self.root, self.settings)

    def open_pdf(self, append=None):
        if append is None and (self.pdf_doc is not None or self.all_snippets):
            append = messagebox.askyesnocancel(
                "Add another PDF?",
                "Append the selected PDF to the current output?\n\n"
                "Yes: append to this project\n"
                "No: start a new project\n"
                "Cancel: keep working here",
            )
            if append is None:
                return False

        file_path = filedialog.askopenfilename(
            title="Choose a PDF to crop",
            filetypes=[("PDF documents", "*.pdf")],
        )
        if not file_path:
            return False

        try:
            new_doc = pymupdf.open(file_path)
            if not new_doc or len(new_doc) == 0:
                new_doc.close()
                messagebox.showerror("Cannot open PDF", "This PDF does not contain any pages.")
                return False
        except Exception as exc:
            messagebox.showerror("Cannot open PDF", f"The selected file could not be opened.\n\n{exc}")
            return False

        if append and self.pdf_doc is not None:
            self.save_current_crop_state()
            try:
                current_snippets = self.render_cropped_snippets()
            except Exception as exc:
                new_doc.close()
                messagebox.showerror(
                    "Could not prepare preview",
                    f"The current PDF could not be added to the output.\n\n{exc}",
                )
                return False
            self.all_snippets = (
                self.all_snippets[: self.current_pdf_snippet_start] + current_snippets
            )

        if self.pdf_doc is not None:
            self.pdf_doc.close()
        if not append:
            self.all_snippets = []
            self.saved_split_y = None
        self.pdf_path = file_path
        self.pdf_doc = new_doc
        self.total_pages = len(self.pdf_doc)
        self.current_page_num = 0
        self.current_pdf_snippet_start = len(self.all_snippets)
        self.current_pdf_crops = {}
        self.skipped_pages = set()

        self.btn_recrop.config(state=tk.NORMAL)
        self.btn_skip.config(state=tk.NORMAL)
        self.btn_go.config(state=tk.NORMAL)
        self.load_page(0)
        return True

    def go_to_page(self):
        if self.pdf_doc is None:
            return
        try:
            page_num = int(self.page_number_var.get()) - 1
        except ValueError:
            messagebox.showerror("Invalid page", "Enter a whole-number page between 1 and the document's last page.")
            self.page_entry.focus_set()
            self.page_entry.selection_range(0, tk.END)
            return
        if not 0 <= page_num < self.total_pages:
            messagebox.showerror("Page out of range", f"Choose a page from 1 to {self.total_pages}.")
            self.page_entry.focus_set()
            self.page_entry.selection_range(0, tk.END)
            return
        self.save_current_crop_state()
        self.current_page_num = page_num
        self.load_page(page_num)

    def _render_page_pixmap(self, page, clip=None, dpi=None):
        requested_dpi = int(dpi if dpi is not None else self.settings.pdf_dpi)
        candidate_dpis = []
        for scale in (1.0, 0.75, 0.5, 0.35, 0.2, 0.1):
            cand = max(72, int(requested_dpi * scale))
            if cand not in candidate_dpis:
                candidate_dpis.append(cand)

        last_error = None
        for candidate_dpi in candidate_dpis:
            try:
                if clip is None:
                    pix = page.get_pixmap(dpi=candidate_dpi)
                else:
                    pix = page.get_pixmap(clip=clip, dpi=candidate_dpi)
                if pix.width <= 0 or pix.height <= 0:
                    continue
                if pix.width > 30000 or pix.height > 30000:
                    raise pymupdf.mupdf.FzErrorLimit("Overly large image")
                return pix
            except pymupdf.mupdf.FzErrorLimit as exc:
                last_error = exc
                continue
            except Exception as exc:
                raise exc

        if last_error is not None:
            raise last_error
        raise RuntimeError(f"Failed to render page preview at any DPI from {candidate_dpis}")

    def load_page(self, page_num):
        self.canvas.delete("all")
        self.rect_id = None
        self.start_y = None
        self.current_y = None

        page = self.pdf_doc[page_num]
        try:
            pix = self._render_page_pixmap(page)
        except Exception as exc:
            messagebox.showerror(
                "Page could not be displayed",
                f"Could not render page {page_num + 1}.\n\n{exc}",
            )
            self.status_var.set("Page preview failed. Try a lower DPI in Export settings.")
            return
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        canvas_width = max(self.canvas.winfo_width(), 800)
        canvas_height = max(self.canvas.winfo_height(), 600)

        img_width, img_height = img.size
        ratio = min(canvas_width / img_width, canvas_height / img_height)

        new_width = int(img_width * ratio)
        new_height = int(img_height * ratio)

        resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        self.tk_img = ImageTk.PhotoImage(resized_img)

        self.scale_factor = page.rect.height / new_height
        self.displayed_img_width = new_width
        self.displayed_img_height = new_height

        self.img_x0 = (canvas_width - new_width) // 2
        self.img_y0 = (canvas_height - new_height) // 2

        self.canvas.create_image(self.img_x0, self.img_y0, anchor=tk.NW, image=self.tk_img)

        if page_num in self.skipped_pages:
            self.btn_skip.config(text="✅ Include Page", bg="#00b894", fg="white")
            self.canvas.create_rectangle(
                self.img_x0,
                self.img_y0,
                self.img_x0 + new_width,
                self.img_y0 + new_height,
                fill="#d63031",
                stipple="gray50",
            )
            self.canvas.create_text(
                canvas_width // 2,
                canvas_height // 2,
                text="SKIPPED PAGE",
                font=("Segoe UI", 24, "bold"),
                fill="white",
            )
        else:
            self.btn_skip.config(text="🚫 Skip Page", bg="#fdcb6e", fg="#2d3436")
            if page_num in self.current_pdf_crops:
                c_data = self.current_pdf_crops[page_num]
                top_canvas = (c_data["top"] / self.scale_factor) + self.img_y0
                bot_canvas = (c_data["bottom"] / self.scale_factor) + self.img_y0

                x0 = self.img_x0
                x1 = self.img_x0 + self.displayed_img_width
                self.rect_id = self.canvas.create_rectangle(
                    x0,
                    top_canvas,
                    x1,
                    bot_canvas,
                    outline="#00cec9",
                    width=3,
                    fill="#00cec9",
                    stipple="gray25",
                )

        status_text = f"Page {page_num + 1} of {self.total_pages} ({os.path.basename(self.pdf_path)})"
        if page_num in self.skipped_pages:
            status_text += " [SKIPPED]"
            self.status_var.set("This page is excluded. Use Include page to restore it.")
        else:
            status_text += " | Drag top-to-bottom to crop"
            self.status_var.set("Drag over the page to crop it. Leave it untouched to keep the full page.")

        self.lbl_page.config(text=status_text)
        self.lbl_count.config(text=f"{len(self.current_pdf_crops)} crops  ·  {len(self.skipped_pages)} skipped")
        self.page_number_var.set(str(page_num + 1))
        self.progress_var.set(((page_num + 1) / max(1, self.total_pages)) * 100)

        self.btn_prev.config(state=tk.NORMAL if page_num > 0 else tk.DISABLED)
        self.btn_go.config(state=tk.NORMAL)

        if page_num == self.total_pages - 1:
            self.btn_next.config(text="Preview & export →", bg="#7c3aed", fg="white")
        else:
            self.btn_next.config(text="Next →", bg="#059669", fg="white")

        self.btn_next.config(state=tk.NORMAL)
        self.btn_skip.config(text="Include page" if page_num in self.skipped_pages else "Skip page")

    def toggle_skip_page(self):
        if self.pdf_doc is None:
            return
        if self.current_page_num in self.skipped_pages:
            self.skipped_pages.remove(self.current_page_num)
            self.load_page(self.current_page_num)
        else:
            self.skipped_pages.add(self.current_page_num)
            if self.current_page_num in self.current_pdf_crops:
                del self.current_pdf_crops[self.current_page_num]
            if self.current_page_num < self.total_pages - 1:
                self.current_page_num += 1
                self.load_page(self.current_page_num)
            else:
                self.finish_current_pdf_and_preview()

    def on_button_press(self, event):
        if self.current_page_num in self.skipped_pages:
            return

        if (
            self.img_x0 <= event.x <= self.img_x0 + self.displayed_img_width
            and self.img_y0 <= event.y <= self.img_y0 + self.displayed_img_height
        ):
            self.start_y = event.y
            self.current_y = event.y
            if self.rect_id:
                self.canvas.delete(self.rect_id)
            x0 = self.img_x0
            x1 = self.img_x0 + self.displayed_img_width
            self.rect_id = self.canvas.create_rectangle(
                x0,
                self.start_y,
                x1,
                self.start_y,
                outline="#00cec9",
                width=3,
                fill="#00cec9",
                stipple="gray25",
            )

    def on_move_press(self, event):
        if self.current_page_num in self.skipped_pages or self.start_y is None or self.rect_id is None:
            return
        self.current_y = max(self.img_y0, min(event.y, self.img_y0 + self.displayed_img_height))
        x0 = self.img_x0
        x1 = self.img_x0 + self.displayed_img_width
        self.canvas.coords(self.rect_id, x0, self.start_y, x1, self.current_y)

    def recrop_current_page(self):
        if self.current_page_num in self.skipped_pages:
            return
        if self.rect_id:
            self.canvas.delete(self.rect_id)
            self.rect_id = None
        self.start_y = None
        self.current_y = None
        if self.current_page_num in self.current_pdf_crops:
            del self.current_pdf_crops[self.current_page_num]
        self.status_var.set("Crop cleared. This page will be kept in full.")
        self.lbl_count.config(text=f"{len(self.current_pdf_crops)} crops  ·  {len(self.skipped_pages)} skipped")

    def save_current_crop_state(self):
        if self.current_page_num in self.skipped_pages:
            return

        page = self.pdf_doc[self.current_page_num]
        if self.start_y is not None and self.current_y is not None and abs(self.start_y - self.current_y) > 5:
            canvas_top = min(self.start_y, self.current_y) - self.img_y0
            canvas_bottom = max(self.start_y, self.current_y) - self.img_y0
            top_pt = canvas_top * self.scale_factor
            bottom_pt = canvas_bottom * self.scale_factor
            self.current_pdf_crops[self.current_page_num] = {"top": top_pt, "bottom": bottom_pt}
        elif self.current_page_num not in self.current_pdf_crops:
            self.current_pdf_crops[self.current_page_num] = {"top": 0.0, "bottom": page.rect.height}

    def prev_page(self):
        self.save_current_crop_state()
        if self.current_page_num > 0:
            self.current_page_num -= 1
            self.load_page(self.current_page_num)

    def next_page(self):
        self.save_current_crop_state()
        if self.current_page_num < self.total_pages - 1:
            self.current_page_num += 1
            self.load_page(self.current_page_num)
        else:
            self.finish_current_pdf_and_preview()

    def finish_current_pdf_and_preview(self):
        prev_strip_height = sum(
            img.height for img in self.all_snippets[: self.current_pdf_snippet_start]
        )
        self.status_var.set("Preparing preview…")
        self.root.update_idletasks()
        self.save_current_crop_state()
        try:
            new_snippets = self.render_cropped_snippets()
        except Exception as exc:
            messagebox.showerror("Could not prepare preview", f"The PDF pages could not be converted into the preview.\n\n{exc}")
            self.status_var.set("Preview preparation failed.")
            return
        self.all_snippets = (
            self.all_snippets[: self.current_pdf_snippet_start] + new_snippets
        )
        if new_snippets:
            self.lbl_count.config(text=f"{len(self.all_snippets)} snippets in output")
        if not self.all_snippets:
            messagebox.showwarning("Warning", "No image snippets collected yet!")
            self.status_var.set("No pages selected for output.")
            return
        LayoutPreviewDialog(self.root, self.all_snippets, self, prev_strip_height, self.settings)

    def render_cropped_snippets(self):
        valid_pages = [p for p in range(self.total_pages) if p not in self.skipped_pages]
        if not valid_pages:
            return []

        snippets = []
        for p_idx in valid_pages:
            page = self.pdf_doc[p_idx]
            crop_info = self.current_pdf_crops.get(p_idx, {"top": 0.0, "bottom": page.rect.height})
            crop_rect = pymupdf.Rect(0, crop_info["top"], page.rect.width, crop_info["bottom"])

            pix = self._render_page_pixmap(page, clip=crop_rect, dpi=self.settings.pdf_dpi)
            crop_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            page_width_px = self.settings.page_width_px
            scale_w = page_width_px / float(page.rect.width)
            target_h = int(crop_rect.height * scale_w)
            resized = crop_img.resize((page_width_px, max(1, target_h)), Image.Resampling.LANCZOS)
            snippets.append(resized)
        return snippets


def main():
    root = tk.Tk()
    app = MultiPDFMasterCropper(root)
    root.mainloop()


if __name__ == "__main__":
    main()
