# MIRA — Changelog

All notable changes to this project are documented here.  
Format: `[vX.Y] YYYY.MM.DD — Summary`

> **Version update checklist**
> 1. Add a new `## [vX.Y] YYYY.MM.DD — ...` entry below
> 2. Update the two variables at the top of `viewer/about_dialog.py`:
>    - `APP_VERSION = "X.Y"`
>    - `APP_UPDATED = "YYYY.MM.DD"`

---

## Roadmap

### v0.3.4 (done) — In-App English User Manual & Menu Cleanup
- [x] `Help → User Manual…` opens the bundled English Markdown in a read-only dialog
- [x] Platform-native Preferences placement and removal of the empty macOS Edit menu
- [x] Updated English/Korean repository manuals, project documentation, and MIRA branding

### v0.3.5 (done) — 4-Pane Colocalization & Favorite Channels
- [x] Synchronized Red/Green/Blue/Merge 2×2 colocalization view and full-grid export
- [x] Merge-only channel enable controls with always-visible tinted source panes
- [x] Per-file session favorite-channel toggle and Global Spectrum markers

### Future
- [ ] Vectorized bin image: compute bin images via direct numpy cube slicing instead of per-channel stacking

---

## [v0.3.5] 2026.09.03 — 4-Pane Colocalization & Favorite Channels

### New Features
- **Four-pane colocalization:** enabling Colocalization now shows synchronized Red, Green, Blue, and additive Merge panes in a fixed 2×2 layout
- **Favorite channels:** a `☆`/`★` control beside the m/z/Ch field bookmarks the current channel; a sorted Favorites dropdown jumps directly to any saved channel

### Changes
- R/G/B slots start enabled; clearing a checkbox removes that color only from Merge while its individually tinted pane remains visible
- Zoom, pan, pixel crosshairs, ROIs, and existing line overlays use matching source-image coordinates across all four panes
- Image export saves the unobstructed full 2×2 grid and places an optional scale bar inside the Merge pane
- Favorites are remembered per normalized file path in each MIRA window for the current application session, without `QSettings` persistence or cross-window sharing
- Favorite markers use orange short-dotted lines behind the blue Global Spectrum stems, clearly separated from the thicker pink current-channel line
- Updated the English/Korean manuals, README, architecture, and v0.3 planning documents for v0.3.5

---

## [v0.3.4] 2026.08.14 — In-App English User Manual & Menu Cleanup

### New Features
- Added a resizable, read-only `MIRA User Manual` dialog using Qt's built-in Markdown renderer, available before or after loading a data file
- Bundled only the current English manual with macOS and Windows applications; the Korean manual and version snapshots remain repository documentation

### Changes
- Removed the empty MIRA-specific Edit menu on macOS and explicitly placed Preferences in the native MIRA application menu
- Added `Settings → Preferences…` on Windows and Linux while preserving the existing File, View, and Help actions
- Updated the English and Korean manuals for all v0.3 features and created immutable v0.3.4 snapshots
- Rewrote README, ARCHITECTURE, and the v0.3 plan in English to match the shipped application
- Regenerated macOS and Windows app icons from `MIRA-LOGO_v1.png` and added the MIRA logo beside the title in About

---

## [v0.3.3] 2026.08.14 — Independent Multi-Window

### New Features
- **Independent windows**: `File → New Window` and the platform-standard New shortcut open a fully separate MIRA window with its own file, channel, zoom, normalization, ROI, line-profile, and RGB overlay state
- **Window lifecycle**: up to three MIRA windows can be open at once; a fourth request shows a `Window Limit` warning, and closing a window immediately frees a slot
- **Window identification**: successful file loads update the title to `MIRA — <filename>`; closing one window leaves the others running, while closing the last window exits the app

### Fixes
- Kept RGB display state and exported image data consistent across brightness, channel, TIC, and Bin Mode actions
- Made regular and RGB Auto brightness use the same view-time binned arrays as the images they adjust
- Preserved view-time binning after normalization changes so the image and all line profiles stay synchronized
- Reset stale pixel selections on file load and made ROI acceptance/rejection clear or preserve the crosshair and Pixel Spectrum together
- Prevented a window from closing while its background file-loading thread is still running

---

## [v0.3.2] 2026.08.12 — Multi-Ion Colocalization Overlay

### New Features
- **Colocalization overlay**: new checkable `Colocalization` toolbar button (next to TIC Image) and matching `View → Colocalization Overlay` menu item switch the ion image into an additive RGB composite view
- **Overlay Controls panel**: new panel (visible only while the overlay is active) with one row per R/G/B slot — a colored enable checkbox, an m/z (or Ch for TIFF) channel picker, and independent Min/Max spinboxes with an Auto (2%–98% percentile) button per channel
- Any combination of R/G/B channels can be enabled; overlapping high-intensity regions blend into yellow/cyan/magenta/white, matching the additive-RGB convention used by SpectViewer/BioMap/MSiReader
- `File → Export Image…` exports the on-screen RGB composite exactly as displayed, with no changes needed to the export path

### Notes
- Shift+click (pixel spectrum, F5) and Shift+drag (ROI, F11) keep working while the overlay is active, since both read the full per-pixel spectrum rather than depending on a single "current channel"; only Ctrl+drag (new line profile, F15) is disabled while the overlay is on, since a line profile needs one 2D array to sample
- While the overlay is active, the bottom `ControlsPanel` (channel slider/m-z/Bin/colormap/Normalize) is disabled as a whole — its last-set values, including `Bin (Da)`/Bin Mode and Normalize, still apply when fetching overlay channels
- R/G/B channel selections persist while toggling the overlay on/off for the same loaded file; opening a new file resets all three rows and turns the overlay off

---

## [v0.3.1] 2026.08.11 — Multi Line-Profile

### New Features
- **Multi line-profile**: Ctrl+drag now adds up to five simultaneous lines (instead of replacing the previous one), all drawn in the existing fixed cyan color with numbered image overlays for identification
- **Line profile popups**: each line opens its own independent, non-modal popup window showing the distance-vs-intensity plot plus the line's start/end pixel coordinates and total length; closing a popup deletes that line from the image
- **Clear button**: new toolbar action (next to Zoom Reset) and matching `View → Clear Annotations` menu item that removes every on-canvas annotation — all ROIs, the pixel crosshair, and all line profiles/popups — in a single click, without touching zoom, channel, or brightness

### Notes
- The old shared bottom "Line Profile" dock and its `View` toggle are removed entirely; popups replace it
- Every open popup auto-refreshes when the channel, normalization, or bin changes, exactly like the single-line behavior before it
- Opening a new file closes all open line-profile popups and clears every line overlay, mirroring the existing ROI reset behavior
- F5 single-pixel click and F11 multi-ROI comparison are unchanged

---

## [v0.3.0] 2026.08.07 — Multi-ROI Spectrum Comparison

### New Features
- **Multi-ROI comparison**: Shift+drag adds up to five rectangular ROIs using reusable, distinct-color slots with numbered image overlays
- **ROI panel**: view each ROI's slot, color, pixel count, visibility, and remove action
- **Overlaid ROI spectra**: compare visible ROI curves in their slot colors while retaining the independent single-pixel preview; the separate Global Spectrum plot remains available above
- **ROI intensity dropdown**: explicitly select `Mean per pixel` or `Total (sum of all pixels)` for both ROI display and CSV export
- **Spectrum CSV export**: export the raw Global Spectrum or all active ROI spectra (including coordinates) from the File menu

### Notes
- Existing Shift+click pixel spectra and Ctrl+drag line profiles remain unchanged
- Opening a new file clears all ROI state and restores mean-per-pixel display
- Lazy-loaded sparse imzML files now use the same rectangular ROI pixel count as full-load files, keeping mean/total values consistent across loading modes

---

## [v0.2.4] 2026.08.06 — ROI & Line Profile Analysis

### New Features
- **ROI region spectrum (Shift+drag)**: drag a box on the ion image to compute and display the mean spectrum of all enclosed pixels; releasing on a near-zero-size box falls back to the existing single-pixel selection
- **Line profile (Ctrl+drag)**: draw a line on the ion image to compute the spatial intensity profile along it (`skimage.measure.profile_line`); shown in a new dockable **Line Profile** panel (bottom dock, `View → Line Profile` or toolbar toggle controls visibility only — the gesture itself is always available). The panel opens automatically the first time a line is drawn, and the profile auto-recomputes whenever the channel, normalization, or bin changes
- **Shift+wheel channel step**: scroll with Shift held to move to the next/previous m/z channel; plain wheel scroll remains zoom, unchanged

### Notes
- The m/z ComboBox dropdown originally planned for F2 remains unimplemented by design — with channel counts reaching the thousands (the same reason load-time binning exists), a flat dropdown list would be impractical; the existing SpinBox direct-entry control is the intended replacement
- Independent multi-window comparison (opening multiple `MainWindow` instances) is deferred to `docs/plan/v0.3_plan.md` (F13) as a formal v0.3 feature

---

## [v0.2.3] 2026.08.04 — Windows Distribution

### Packaging
- **Standalone Windows executable**: PyInstaller now uses `--onefile` to produce `packaging/dist/MIRA.exe`
- **Fixed CI artifact upload**: the GitHub Actions workflow now uploads the actual single-file build output
- **Node.js 24 migration**: upgraded checkout, Python setup, and artifact upload actions to Node.js 24-compatible versions
- **Release documentation**: updated Windows tag and artifact download instructions for v0.2.3

---

## [v0.2.2] 2026.05.08 — Data Loading & Multi-platform

### New Features
- **Load-time spectral binning**: when opening large imzML files (channel count > threshold), a dialog offers full resolution or bin at X Da — dramatically reduces memory usage and rendering lag for raw high-resolution datasets
- **User-configurable threshold**: `Edit → Preferences…` exposes the large-file channel threshold (default: 5,000) via `QSettings`
- **Multi-channel TIFF support**: `File → Open File…` now accepts `.tif` / `.tiff` files (CYX / ZYX / YX formats via `tifffile`); channel axis auto-detected, pixel size read from XResolution tag if present
- **Windows build**: `build_win.bat` PyInstaller script + `assets/AppIcon.ico` + `.github/workflows/build-windows.yml` GitHub Actions CI for automatic `.exe` artifact on tag push

### Changes
- File open dialog renamed "Open File…" and extended to include `.tif` / `.tiff` filter alongside `.imzML`
- Spectrum x-axis label switches to "Channel" for TIFF files; controls panel label switches to "Ch"
- Status bar shows load-time bin width when binning was applied at open time

---

## [v0.2.1] 2026.05.08 — UX & Display Improvements

### Features
- **Spectrum stem plot**: replaced connected line plot with a stem-style display — one vertical line per m/z peak, no markers
- **m/z direct input**: added SpinBox (numeric entry) and ComboBox (list selection) to the controls panel for direct m/z navigation
- **Channel bin size**: `Bin (Da)` spinbox averages (or sums) all channels within ±(Da/2) of the current m/z — toggle Mean/Sum via `View → Bin Mode`
- **Image export**: `File → Export Image…` (Ctrl+Shift+S) — saves current view as PNG / JPG / TIFF with optional pixel-unit scale bar

---

## [v0.1] 2026.04.10 — Initial Release

**Initial release of MSI Viewer.**

### Features
- imzML format support (`.imzML` + `.ibd`), both Continuous and Processed modes
- Ion image browsing: m/z channel navigation via mouse wheel or slider
- Zoom / Pan: Ctrl+Wheel for zoom, left-click drag for pan, double-click to reset
- Brightness / Contrast: Min/Max spinbox or right-click drag (ITK-SNAP style)
- Auto brightness: 2%–98% percentile auto-adjustment per channel
- Colormap selection: gray / viridis / hot / inferno (built-in LUT, no matplotlib dependency)
- Global spectrum: sum of all pixels plotted in real time
- Pixel spectrum: live hover-position spectrum display
- Spectrum click: click on m/z position to jump to that channel
- TIC image: View → Show TIC Image
- Normalization: None / TIC / RMS / Median
- Large-file support: files > 500 MB use automatic lazy loading
- Background file loading with progress dialog (no UI freeze)
- macOS Retina display support
- macOS `.app` bundle packaging via PyInstaller

### Known Limitations
- viridis / inferno colormaps are approximations (no matplotlib dependency)
- Processed-mode m/z axis built from union of all pixel m/z values — slow on very large datasets
- Lazy loading (> 500 MB) triggers disk I/O on every hover event — fast SSD recommended

