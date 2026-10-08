# PaperFlow

PaperFlow is a desktop PDF crop-and-stitch tool. Select a vertical section from each source page, arrange multiple PDFs into one continuous strip, adjust where the output pages break, and export the result as a PDF.

## Requirements

- Python 3.10 or newer
- Tkinter (included with most standard Python installations)
- PyMuPDF
- Pillow

## Install and run

From the repository folder, open PowerShell and run:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install PyMuPDF Pillow
python app.py
```

If PowerShell does not recognize `py`, use `python` in its place when creating the virtual environment:

```powershell
python -m venv .venv
```

On Windows, install Python from [python.org](https://www.python.org/downloads/) and make sure its Tcl/Tk support is included. If you already have a Python environment, install the two packages into that environment and run `python app.py` from the repository folder.

## Quick start

1. Click **Add PDF** and select a PDF.
2. On each page, drag vertically over the part you want to keep. The selection spans the full page width.
3. Leave a page untouched to keep it whole, or use **Clear crop** to remove its crop.
4. Use **Next** and **Previous** to move through the document. On the last page, **Next** changes to **Preview & export**.
5. In the preview, adjust page breaks if needed and click **Export PDF**.
6. Choose a destination and filename for the finished PDF.

## Cropping and selecting pages

### Keep a section of a page

Drag from the top to the bottom of the section to keep. The crop keeps the full page width and removes the areas above and below the selection. The direction of the drag does not matter.

Selections are saved as you navigate away from a page. To change a selection, return to that page and drag again. Click **Clear crop** to restore the full page.

### Keep a whole page

Do not draw a selection on the page. An untouched page is included in full.

### Exclude a page

Click **Skip page** to exclude the current page. Skipped pages are marked in the page editor and do not appear in the layout preview or exported PDF. Click **Include page** to restore a skipped page.

### Navigate

- Click **Previous** or **Next**.
- Enter a 1-based page number and click **Go**, or press **Enter** in the page-number field.
- When the page canvas has focus, use **Left Arrow** and **Right Arrow** to move between pages.
- Press **Ctrl+O** to open a PDF.

## Working with multiple PDFs

To add another PDF before exporting, click **Add PDF** and choose a file. When a PDF is already open or the project already contains pages, the app asks whether to append the new PDF to the current output, start a new project, or cancel. Choosing append keeps the current document's crops and skipped pages, including pages you have not navigated to yet.

You can also click **Append PDF** in the layout preview. The app returns to the page editor to crop the additional document; when you reach its last page, the preview includes the earlier and newly added pages in sequence.

## Adjusting the output layout

The preview displays all included page sections as one long strip, with cut lines dividing it into output pages. Page breaks are added automatically based on the selected page size and margin. The preview indicates when a segment is taller than the usable page area.

- **Move a cut:** drag a cut line up or down.
- **Add a cut:** double-click the desired position on the strip.
- **Remove one cut:** right-click near its line.
- **Remove every cut:** click **Remove all cuts**. The strip will export as a single segment, split into pages only if necessary to fit.
- **Zoom:** use **+** and **−** in the preview toolbar.
- **Scroll:** use the mouse wheel or the scrollbar.
- **Export:** click **Export PDF**, then select the destination and filename.

## Export settings

Click **Export settings** in the main window to change:

- **Page size:** A4, Letter, or Custom.
- **Margin (px):** margin used for automatic page breaks and the corresponding print margin in the exported PDF.
- **PDF DPI:** resolution used to render source pages. Higher values can improve detail but use more memory and can create larger output PDFs.
- **Preview scale:** initial zoom level for the layout preview.
- **Custom width and height (px):** pixel dimensions used for the custom working canvas.

The default settings are A4, a 60-pixel margin, 300 DPI, and a 22% preview scale. Settings apply to the current run and are not saved as a profile.

Choosing **Custom** sets the working canvas dimensions and exported paper size. Custom pixel dimensions are converted to PDF points at 300 pixels per inch. The export margin is scaled from the canvas width so the preview and PDF use matching page-break capacity.

## How exported PDFs are made

Source pages are rendered to images, cropped, and assembled into image-based PDF pages. This preserves the visual appearance of the selected areas, but text is not retained as selectable/searchable PDF text. The source files are not modified.

Very large or high-resolution documents can take longer to render and may use substantial memory. If a page preview cannot be rendered, try reducing **PDF DPI** in **Export settings**.

## Troubleshooting

- **`No module named 'pymupdf'` or `No module named 'PIL'`:** activate the intended environment and run `python -m pip install PyMuPDF Pillow`.
- **Tkinter is unavailable:** install a Python distribution with Tcl/Tk support, then retry `python app.py`.
- **A PDF cannot be opened:** make sure the file is a readable PDF and contains at least one page.
- **A page preview fails:** reduce the PDF DPI and try again. Very large source pages may require a lower value.
- **No pages are exported:** include at least one page and ensure the preview contains a non-empty segment before exporting.
