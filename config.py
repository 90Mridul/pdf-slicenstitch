from dataclasses import dataclass, field


@dataclass
class ExportSettings:
    page_size: str = "A4"
    page_width_px: int = 2480
    page_height_px: int = 3508
    margin_px: int = 60
    output_page_width_pts: float = 595.0
    output_page_height_pts: float = 842.0
    output_margin_pts: float = 20.0
    pdf_dpi: int = 300
    preview_scale: float = 0.22
    dark_mode: bool = True
    accent_color: str = "#4dabf7"
    canvas_bg: str = "#1f2933"
    card_bg: str = "#2f3b46"
    button_text_color: str = "#ffffff"
    crop_outline_color: str = "#00cec9"
    cut_line_color: str = "#ff7675"
    page_label_color: str = "#74b9ff"
    safe_margin: int = 50
    enable_page_hud: bool = True
    show_single_page_bounds: bool = True
    page_title_prefix: str = "Past Paper"
    last_saved_directory: str = ""
    custom_page_size: tuple[int, int] = field(default_factory=lambda: (2480, 3508))

    def apply_page_size(self, page_size: str):
        self.page_size = page_size
        if page_size == "A4":
            self.page_width_px = 2480
            self.page_height_px = 3508
            self.output_page_width_pts = 595.0
            self.output_page_height_pts = 842.0
            self.custom_page_size = (2480, 3508)
        elif page_size == "Letter":
            self.page_width_px = 2400
            self.page_height_px = 3100
            self.output_page_width_pts = 612.0
            self.output_page_height_pts = 792.0
            self.custom_page_size = (2400, 3100)
        elif page_size == "Custom":
            self.page_width_px, self.page_height_px = self.custom_page_size
        else:
            self.page_width_px, self.page_height_px = self.custom_page_size

    def update_custom_size(self, width: int, height: int):
        self.custom_page_size = (max(100, width), max(100, height))
        if self.page_size == "Custom":
            self.page_width_px, self.page_height_px = self.custom_page_size

    @property
    def usable_height_px(self) -> int:
        return max(1, self.page_height_px - (2 * self.margin_px))

    @property
    def page_dims_label(self) -> str:
        if self.page_size == "Custom":
            return f"Custom {self.page_width_px} x {self.page_height_px}"
        return self.page_size

    @staticmethod
    def page_size_options() -> list[str]:
        return ["A4", "Letter", "Custom"]
