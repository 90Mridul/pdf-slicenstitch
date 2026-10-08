import os
import tkinter as tk
from tkinter import filedialog, messagebox
import pymupdf
from PIL import Image, ImageTk

class MultiPDFMasterCropper:
    def __init__(self, root):
        self.root = root
        self.root.title("Continuous Multi-PDF Flow Builder & Layout Editor")
        self.root.geometry("1100x850")

        self.pdf_doc = None
        self.pdf_path = ""
        self.current_page_num = 0
        self.total_pages = 0
        
        # Collection of all cropped snippets across all imported PDFs
        self.all_snippets = []  # List of PIL Images
        self.current_pdf_crops = {}
        self.skipped_pages = set()

        # PERSISTENT STORAGE: Stores manual page-break cut positions across preview opens
        self.saved_split_y = None

        self.scale_factor = 1.0
        self.start_y = None
        self.current_y = None
        self.rect_id = None

        self._build_ui()

    def _build_ui(self):
        toolbar = tk.Frame(self.root, bg="#1e272e", pady=10, padx=10)
        toolbar.pack(fill=tk.X, side=tk.TOP)

        btn_open = tk.Button(
            toolbar, text="📁 Open / Append PDF", command=self.open_pdf,
            font=("Segoe UI", 10, "bold"), bg="#0984e3", fg="white", relief=tk.FLAT, padx=12, pady=5
        )
        btn_open.pack(side=tk.LEFT, padx=5)

        self.btn_recrop = tk.Button(
            toolbar, text="↺ Re-crop", command=self.recrop_current_page,
            state=tk.DISABLED, font=("Segoe UI", 10, "bold"), bg="#d63031", fg="white", relief=tk.FLAT, padx=10, pady=5
        )
        self.btn_recrop.pack(side=tk.LEFT, padx=5)

        self.btn_skip = tk.Button(
            toolbar, text="🚫 Skip Page", command=self.toggle_skip_page,
            state=tk.DISABLED, font=("Segoe UI", 10, "bold"), bg="#fdcb6e", fg="#2d3436", relief=tk.FLAT, padx=10, pady=5
        )
        self.btn_skip.pack(side=tk.LEFT, padx=5)

        self.lbl_page = tk.Label(toolbar, text="No PDF Loaded", font=("Segoe UI", 11, "bold"), fg="white", bg="#1e272e")
        self.lbl_page.pack(side=tk.LEFT, expand=True)

        self.lbl_count = tk.Label(toolbar, text="Total Snippets: 0", font=("Segoe UI", 10, "bold"), fg="#00cec9", bg="#1e272e")
        self.lbl_count.pack(side=tk.RIGHT, padx=10)

        self.btn_prev = tk.Button(
            toolbar, text="← Prev", command=self.prev_page,
            state=tk.DISABLED, font=("Segoe UI", 10, "bold"), bg="#636e72", fg="white", relief=tk.FLAT, padx=10, pady=5
        )
        self.btn_prev.pack(side=tk.RIGHT, padx=5)

        self.btn_next = tk.Button(
            toolbar, text="Next →", command=self.next_page,
            state=tk.DISABLED, font=("Segoe UI", 10, "bold"), bg="#00b894", fg="white", relief=tk.FLAT, padx=10, pady=5
        )
        self.btn_next.pack(side=tk.RIGHT, padx=5)

        canvas_frame = tk.Frame(self.root, bg="#2d3436")
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(canvas_frame, bg="#2d3436", cursor="cross", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)

    def open_pdf(self):
        file_path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if not file_path:
            return

        self.pdf_path = file_path
        self.pdf_doc = pymupdf.open(self.pdf_path)
        self.total_pages = len(self.pdf_doc)
        self.current_page_num = 0
        self.current_pdf_crops = {}
        self.skipped_pages = set()

        self.btn_recrop.config(state=tk.NORMAL)
        self.btn_skip.config(state=tk.NORMAL)
        self.load_page(0)

    def load_page(self, page_num):
        self.canvas.delete("all")
        self.rect_id = None
        self.start_y = None
        self.current_y = None

        page = self.pdf_doc[page_num]

        pix = page.get_pixmap(dpi=120)
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
                self.img_x0, self.img_y0, 
                self.img_x0 + new_width, self.img_y0 + new_height,
                fill="#d63031", stipple="gray50"
            )
            self.canvas.create_text(
                canvas_width // 2, canvas_height // 2,
                text="SKIPPED PAGE", font=("Segoe UI", 24, "bold"), fill="white"
            )
        else:
            self.btn_skip.config(text="🚫 Skip Page", bg="#fdcb6e", fg="#2d3436")

            if page_num in self.current_pdf_crops:
                c_data = self.current_pdf_crops[page_num]
                top_canvas = (c_data['top'] / self.scale_factor) + self.img_y0
                bot_canvas = (c_data['bottom'] / self.scale_factor) + self.img_y0
                
                x0 = self.img_x0
                x1 = self.img_x0 + self.displayed_img_width
                self.rect_id = self.canvas.create_rectangle(
                    x0, top_canvas, x1, bot_canvas,
                    outline="#00cec9", width=3, fill="#00cec9", stipple="gray25"
                )

        status_text = f"Page {page_num + 1} of {self.total_pages} ({os.path.basename(self.pdf_path)})"
        if page_num in self.skipped_pages:
            status_text += " [SKIPPED]"
        else:
            status_text += " | Drag top-to-bottom to crop"
            
        self.lbl_page.config(text=status_text)
        self.lbl_count.config(text=f"Total Snippets: {len(self.all_snippets)}")
        
        self.btn_prev.config(state=tk.NORMAL if page_num > 0 else tk.DISABLED)

        if page_num == self.total_pages - 1:
            self.btn_next.config(text="👁️ Add to Strip & Preview", bg="#e17055", fg="white")
        else:
            self.btn_next.config(text="Next →", bg="#00b894", fg="white")
        
        self.btn_next.config(state=tk.NORMAL)

    def toggle_skip_page(self):
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

        if self.img_y0 <= event.y <= self.img_y0 + self.displayed_img_height:
            self.start_y = event.y
            if self.rect_id:
                self.canvas.delete(self.rect_id)
            
            x0 = self.img_x0
            x1 = self.img_x0 + self.displayed_img_width
            self.rect_id = self.canvas.create_rectangle(
                x0, self.start_y, x1, self.start_y,
                outline="#00cec9", width=3, fill="#00cec9", stipple="gray25"
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

    def save_current_crop_state(self):
        if self.current_page_num in self.skipped_pages:
            return

        page = self.pdf_doc[self.current_page_num]
        
        if self.start_y is not None and self.current_y is not None and abs(self.start_y - self.current_y) > 5:
            canvas_top = min(self.start_y, self.current_y) - self.img_y0
            canvas_bottom = max(self.start_y, self.current_y) - self.img_y0
            
            top_pt = canvas_top * self.scale_factor
            bottom_pt = canvas_bottom * self.scale_factor
            
            self.current_pdf_crops[self.current_page_num] = {'top': top_pt, 'bottom': bottom_pt}
        elif self.current_page_num not in self.current_pdf_crops:
            self.current_pdf_crops[self.current_page_num] = {'top': 0.0, 'bottom': page.rect.height}

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
        prev_strip_height = sum(img.height for img in self.all_snippets)

        new_snippets = self.render_cropped_snippets()
        if new_snippets:
            self.all_snippets.extend(new_snippets)
            self.lbl_count.config(text=f"Total Snippets: {len(self.all_snippets)}")

        if not self.all_snippets:
            messagebox.showwarning("Warning", "No image snippets collected yet!")
            return

        LayoutPreviewDialog(self.root, self.all_snippets, self, prev_strip_height)

    def render_cropped_snippets(self):
        valid_pages = [p for p in range(self.total_pages) if p not in self.skipped_pages]
        if not valid_pages:
            return []

        A4_WIDTH = 2480
        snippets = []

        for p_idx in valid_pages:
            page = self.pdf_doc[p_idx]
            crop_info = self.current_pdf_crops.get(p_idx, {'top': 0.0, 'bottom': page.rect.height})
            crop_rect = pymupdf.Rect(0, crop_info['top'], page.rect.width, crop_info['bottom'])

            pix = page.get_pixmap(clip=crop_rect, dpi=300)
            crop_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Keep aspect ratio based on page width
            scale_w = A4_WIDTH / float(page.rect.width)
            target_h = int(crop_rect.height * scale_w)
            
            resized = crop_img.resize((A4_WIDTH, target_h), Image.Resampling.LANCZOS)
            snippets.append(resized)

        return snippets


class LayoutPreviewDialog:
    """Master layout preview: drag cut lines, double-click to add a break, or right-click a line to remove it."""
    def __init__(self, parent, snippets, app_reference, prev_strip_height=0):
        self.top = tk.Toplevel(parent)
        self.top.title("Master Flow Preview & Page Break Editor")
        self.top.geometry("1250x900")

        self.snippets = snippets
        self.app_ref = app_reference

        self.A4_W = 2480
        self.A4_H = 3508
        self.MARGIN = 60
        self.USABLE_H = self.A4_H - (2 * self.MARGIN)

        # Build continuous master strip with constant width
        total_h = sum(img.height for img in self.snippets)
        self.master_strip = Image.new("RGB", (self.A4_W, total_h), (255, 255, 255))
        
        curr_y = 0
        for img in self.snippets:
            self.master_strip.paste(img, (0, curr_y))
            curr_y += img.height

        # Restore saved cut positions or generate initial defaults
        if self.app_ref.saved_split_y is not None and len(self.app_ref.saved_split_y) > 0:
            # Keep previous cut positions
            self.split_y = [y for y in self.app_ref.saved_split_y if y < self.master_strip.height]

            # Append default page breaks for any newly added content
            last_cut = max(self.split_y) if self.split_y else 0
            pos = max(prev_strip_height, last_cut) + self.USABLE_H
            while pos < self.master_strip.height:
                if pos not in self.split_y:
                    self.split_y.append(pos)
                pos += self.USABLE_H
            self.split_y.sort()
        else:
            # Calculate initial split positions for a fresh document
            self.split_y = []
            pos = self.USABLE_H
            while pos < self.master_strip.height:
                self.split_y.append(pos)
                pos += self.USABLE_H

        self.preview_scale = 0.22
        self.drag_index = None

        self._build_ui()
        self.redraw_canvas()

    def _build_ui(self):
        toolbar = tk.Frame(self.top, bg="#1e272e", pady=10, padx=10)
        toolbar.pack(fill=tk.X, side=tk.TOP)

        lbl_info = tk.Label(
            toolbar, 
            text="✂️ Drag lines to adjust | ➕ Double-click to ADD page break | 🗑️ Right-click line to REMOVE break", 
            font=("Segoe UI", 9, "bold"), fg="#74b9ff", bg="#1e272e"
        )
        lbl_info.pack(side=tk.LEFT, padx=5)

        btn_clear = tk.Button(
            toolbar, text="🗑️ Remove All Cut Lines", command=self.remove_all_cuts,
            font=("Segoe UI", 9, "bold"), bg="#d63031", fg="white", relief=tk.FLAT, padx=8, pady=4
        )
        btn_clear.pack(side=tk.LEFT, padx=10)

        btn_append = tk.Button(
            toolbar, text="➕ Add / Append PDF", command=self.append_another_pdf,
            font=("Segoe UI", 10, "bold"), bg="#0984e3", fg="white", relief=tk.FLAT, padx=10, pady=5
        )
        btn_append.pack(side=tk.RIGHT, padx=5)

        btn_export = tk.Button(
            toolbar, text="💾 Export Final PDF", command=self.export_pdf,
            font=("Segoe UI", 10, "bold"), bg="#00b894", fg="white", relief=tk.FLAT, padx=15, pady=5
        )
        btn_export.pack(side=tk.RIGHT, padx=5)

        frame = tk.Frame(self.top, bg="#2d3436")
        frame.pack(fill=tk.BOTH, expand=True)

        self.v_scroll = tk.Scrollbar(frame, orient=tk.VERTICAL)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas = tk.Canvas(frame, bg="#2d3436", yscrollcommand=self.on_scroll)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.v_scroll.config(command=self.canvas.yview)

        # Bind MouseWheel for scrolling
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<Button-3>", self.on_right_click)

    def _on_mousewheel(self, event):
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")
        else:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.update_sticky_hud()

    def on_scroll(self, *args):
        self.v_scroll.set(*args)
        self.update_sticky_hud()

    def update_sticky_hud(self):
        """Keep page count badges and HUDs tracking near the current view position."""
        view_top = self.canvas.canvasy(0)

        cuts = [0] + sorted(self.split_y) + [self.master_strip.height]

        for i in range(len(cuts) - 1):
            top_cy = self.canvas_y0 + int(cuts[i] * self.preview_scale)
            bot_cy = self.canvas_y0 + int(cuts[i+1] * self.preview_scale)

            sticky_y = max(top_cy + 10, min(view_top + 10, bot_cy - 80))

            if hasattr(self, 'hud_boxes') and i < len(self.hud_boxes):
                bg_id, text_id, page_lbl_id = self.hud_boxes[i]
                
                hud_x = self.canvas_x0 + int(self.A4_W * self.preview_scale) + 20
                self.canvas.coords(bg_id, hud_x, sticky_y, hud_x + 230, sticky_y + 75)
                self.canvas.coords(text_id, hud_x + 10, sticky_y + 37)
                self.canvas.coords(page_lbl_id, self.canvas_x0 - 45, max(top_cy + 20, min(view_top + 30, bot_cy - 20)))

    def save_cuts_to_app(self):
        """Save current cut line state back to the root application state."""
        self.app_ref.saved_split_y = list(self.split_y)

    def redraw_canvas(self):
        self.canvas.delete("all")
        self.save_cuts_to_app()

        display_w = int(self.A4_W * self.preview_scale)
        display_h = int(self.master_strip.height * self.preview_scale)

        resized = self.master_strip.resize((display_w, display_h), Image.Resampling.BILINEAR)
        self.tk_preview = ImageTk.PhotoImage(resized)

        self.canvas_x0 = 80
        self.canvas_y0 = 30

        # Draw background canvas shadow
        self.canvas.create_rectangle(
            self.canvas_x0 - 5, self.canvas_y0 - 5,
            self.canvas_x0 + display_w + 5, self.canvas_y0 + display_h + 5,
            fill="#000000", outline=""
        )

        # Draw master strip image
        self.canvas.create_image(self.canvas_x0, self.canvas_y0, anchor=tk.NW, image=self.tk_preview)

        cuts = [0] + sorted(self.split_y) + [self.master_strip.height]
        self.hud_boxes = []

        # Draw page labels & HUD info boxes
        for i in range(len(cuts) - 1):
            top_px = cuts[i]
            bot_px = cuts[i+1]
            chunk_h = bot_px - top_px

            top_cy = self.canvas_y0 + int(top_px * self.preview_scale)
            bot_cy = self.canvas_y0 + int(bot_px * self.preview_scale)

            fill_ratio = (chunk_h / self.USABLE_H) * 100
            is_overflow = chunk_h > self.USABLE_H

            hud_bg = "#d63031" if is_overflow else "#2d3436"
            hud_fg = "#ff7675" if is_overflow else "#00cec9"

            page_lbl_id = self.canvas.create_text(
                self.canvas_x0 - 45, top_cy + 20,
                text=f"Page {i+1}", font=("Segoe UI", 11, "bold"), fill=hud_fg
            )

            hud_x = self.canvas_x0 + display_w + 20
            hud_y = top_cy + 10
            
            status_str = " ⚠️ BLEEDS TO NEXT PAGE!" if is_overflow else " ✅ Fits on Page"
            hud_msg = f"Page {i+1} Capacity:\n• Height: {chunk_h} / {self.USABLE_H} px\n• Fill: {fill_ratio:.1f}%\n• Status:{status_str}"

            bg_id = self.canvas.create_rectangle(
                hud_x, hud_y, hud_x + 230, hud_y + 75,
                fill=hud_bg, outline=hud_fg, width=2
            )
            text_id = self.canvas.create_text(
                hud_x + 10, hud_y + 37, anchor=tk.W,
                text=hud_msg, font=("Consolas", 9, "bold"), fill="white"
            )

            self.hud_boxes.append((bg_id, text_id, page_lbl_id))

        # Draw red draggable/removable cut lines
        self.line_ids = []
        for idx, s_y in enumerate(self.split_y):
            cy = self.canvas_y0 + int(s_y * self.preview_scale)
            l_id = self.canvas.create_line(
                self.canvas_x0 - 15, cy, 
                self.canvas_x0 + display_w + 15, cy, 
                fill="#ff7675", width=4, dash=(8, 4)
            )
            self.canvas.create_text(
                self.canvas_x0 + display_w + 10, cy - 10, anchor=tk.W,
                text=f"Cut {idx + 1} (Right-click to delete)", font=("Segoe UI", 9, "bold"), fill="#ff7675"
            )
            self.line_ids.append(l_id)

        total_canvas_h = display_h + 100
        self.canvas.config(scrollregion=(0, 0, display_w + 350, total_canvas_h))
        self.update_sticky_hud()

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
        
        min_y = self.split_y[self.drag_index - 1] + 50 if self.drag_index > 0 else 50
        max_y = self.split_y[self.drag_index + 1] - 50 if self.drag_index < len(self.split_y) - 1 else self.master_strip.height - 50

        clamped_y = max(min_y, min(new_strip_y, max_y))
        self.split_y[self.drag_index] = clamped_y

        self.redraw_canvas()

    def on_release(self, event):
        self.drag_index = None

    def on_double_click(self, event):
        """Double click anywhere on the strip to ADD a page break line."""
        canvas_y = self.canvas.canvasy(event.y)
        click_strip_y = int((canvas_y - self.canvas_y0) / self.preview_scale)

        if 50 < click_strip_y < self.master_strip.height - 50:
            self.split_y.append(click_strip_y)
            self.split_y.sort()
            self.redraw_canvas()

    def on_right_click(self, event):
        """Right-click on or near any red cut line to DELETE it."""
        canvas_y = self.canvas.canvasy(event.y)
        for idx, s_y in enumerate(self.split_y):
            cy = self.canvas_y0 + int(s_y * self.preview_scale)
            if abs(canvas_y - cy) < 14:
                del self.split_y[idx]
                self.redraw_canvas()
                break

    def remove_all_cuts(self):
        """Removes all cut lines so everything combines onto one flow."""
        self.split_y = []
        self.redraw_canvas()

    def append_another_pdf(self):
        """Closes preview dialog and allows importing another PDF to append."""
        self.save_cuts_to_app()
        self.top.destroy()
        self.app_ref.open_pdf()

    def export_pdf(self):
        """Exports the layout with standard A4 point bounds to prevent zoomed views in viewers."""
        cuts = [0] + sorted(self.split_y) + [self.master_strip.height]

        output_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")])
        if not output_path:
            return

        out_pdf = pymupdf.open()

        # Standard A4 size in PDF points (72 points = 1 inch)
        A4_PTS_W = 595.0
        A4_PTS_H = 842.0
        MARGIN_PTS = 20.0
        USABLE_PTS_H = A4_PTS_H - (2 * MARGIN_PTS)

        for i in range(len(cuts) - 1):
            top_y = cuts[i]
            bot_y = cuts[i + 1]
            chunk_h = bot_y - top_y

            if chunk_h <= 0:
                continue

            chunk = self.master_strip.crop((0, top_y, self.A4_W, bot_y))

            # Convert PIL chunk to PyMuPDF Pixmap
            img_bytes = chunk.tobytes("raw", "RGB")
            pix = pymupdf.Pixmap(pymupdf.csRGB, chunk.width, chunk.height, img_bytes, False)

            # Proportional height in PDF points
            scaled_h_pts = (chunk.height / float(self.A4_W)) * A4_PTS_W

            # Handle normal page or multi-page overflow block
            sub_y_pts = 0.0
            while sub_y_pts < scaled_h_pts:
                sub_h_pts = min(USABLE_PTS_H, scaled_h_pts - sub_y_pts)

                # Create standardized A4 page
                page = out_pdf.new_page(width=A4_PTS_W, height=A4_PTS_H)

                # Insert sub-rect bounded cleanly inside standard A4 page limits
                rect = pymupdf.Rect(0, MARGIN_PTS, A4_PTS_W, MARGIN_PTS + sub_h_pts)
                page.insert_image(rect, pixmap=pix)

                sub_y_pts += USABLE_PTS_H

        if len(out_pdf) > 0:
            out_pdf.save(output_path)
            out_pdf.close()
            messagebox.showinfo("Success", f"PDF compiled successfully!\nTotal Pages: {len(out_pdf)}\nSaved to:\n{output_path}")
            self.top.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = MultiPDFMasterCropper(root)
    root.mainloop()
