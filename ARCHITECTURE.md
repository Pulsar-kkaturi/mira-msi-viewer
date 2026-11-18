# MIRA v0.3.5 Architecture

**Application:** MIRA — Mass spectrometry Imaging & Review App

**Version:** v0.3.5

**Updated:** 2026.09.03

This document describes the implementation that exists in MIRA v0.3.5. MIRA is a PyQt6 desktop application whose windows own independent data and UI state. `MainWindow` coordinates components through signals and slots; `MSIDataModel` remains independent of Qt.

## 1. Runtime Topology

```text
main.py
├── QApplication
├── _open_windows: list[MainWindow]       # strong-reference registry
├── create_window(requester=None)         # factory and three-window limit
└── MainWindow (one to three instances)
    ├── MSIDataModel
    ├── ImageViewer
    ├── SpectrumPanel
    │   └── ROIPanel
    ├── OverlayPanel
    ├── ControlsPanel
    ├── LineProfileDialog instances       # zero to five per MainWindow
    │   └── LineProfilePanel
    ├── ExportDialog / SettingsDialog
    ├── UserManualDialog
    └── AboutDialog
```

### Independent-window registry

`main.py` owns the module-level `_open_windows` list and `MAX_OPEN_WINDOWS = 3`. The registry has two purposes:

1. It keeps strong references to windows created from `File → New Window`, preventing Python garbage collection after the factory returns.
2. It enforces a maximum of three windows including the initial window.

`create_window()` constructs each `MainWindow`, connects `new_window_requested` back to the factory, connects `window_closed` to `_unregister_window()`, offsets the new window from the last one, registers it, and shows it. A fourth request produces a `Window Limit` warning.

Each `MainWindow` constructs its own model, views, ROI list, overlay settings, line-profile popups, loading thread, and channel/display state. No analysis state is shared between windows. `QSettings`-based preferences remain application-wide. A window refuses to close while its load thread is running, closes its owned line-profile dialogs on an accepted close, and then removes itself from the registry. Qt exits when the last top-level window closes.

## 2. Main Window Composition

```text
QMainWindow
├── native menu bar
├── toolbar: Open | TIC Image | Colocalization | Zoom Reset | Clear
├── horizontal splitter
│   ├── ImageViewer
│   └── SpectrumPanel
│       ├── Global Spectrum
│       └── Pixel/ROI Spectrum + auto-hiding ROIPanel
├── OverlayPanel                         # visible only in RGB mode
├── ControlsPanel
└── status bar
```

`viewer/main_window.py` is the orchestration layer. It owns authoritative ROI records, the active line-profile dialog map, overlay-mode state, the current channel and bin mode, and the asynchronous file-load lifecycle. Components do not directly manipulate one another; `MainWindow` receives signals, requests model data, and updates the relevant widgets.

Successful loading changes the window title from `MIRA` to `MIRA — <filename>`. Loading a new file resets ROIs, the pixel crosshair, line profiles, and RGB overlay state before initializing controls and spectra.

### Background loading

```text
MainWindow._open_file()
  ├── imzML pre-scan and optional load-time binning dialog
  ├── QProgressDialog
  └── QThread
      └── _LoadWorker.run()
          ├── MSIDataModel.load(path, bin_da)       # imzML
          └── MSIDataModel.load_tiff(path)          # TIFF

finished → MainWindow._on_load_finished()
error    → MainWindow._on_load_error()
```

The worker owns no UI. Completion and errors are delivered back to the GUI thread by Qt signals.

## 3. Data Model

`viewer/data_model.py` defines `MSIDataModel`, the non-Qt data layer for:

- imzML Continuous and Processed modes through pyimzML
- 2D or multi-channel TIFF through tifffile
- channel images, TIC images, pixel spectra, ROI spectra, and the global spectrum
- None, TIC, RMS, and Median normalization
- load-time and view-time spectral binning
- optional TIFF/imzML pixel-size metadata for scale bars

The public state includes `mz_array`, `shape`, `n_channels`, `mode`, and `norm_mode`.

### imzML axis and loading strategy

- Continuous mode uses the first spectrum's shared m/z axis.
- Processed mode builds a sorted union of all pixel m/z values.
- A pre-scan reports mode, estimated channel count, and m/z range before loading. When the channel count exceeds the configured threshold, the user may choose Da-based load-time binning.
- If the matching `.ibd` file is at most 500 MB, the model creates a float32 cube with shape `(H, W, N)`.
- Larger files remain lazy and reconstruct requested images from pyimzML spectra.

Load-time bins store center values in `mz_array`. Full-load and lazy paths both average raw values assigned to each bin. View-time binning is independent: `get_bin_image()` stacks normalized channel images inside ±(Bin/2) and applies Mean or Sum.

### TIFF representation

TIFF input is squeezed and normalized to a `(H, W, C)` float32 cube. A 2D image becomes a one-channel cube; for a four-dimensional input, the first leading slice is used. TIFF channels use numeric indices as the x-axis. When available, XResolution and ResolutionUnit metadata are converted to nm/pixel for image-export scale bars.

### Spectra and normalization

- `get_global_spectrum()` returns the raw sum across all pixels and caches it.
- `get_pixel_spectrum()` returns a raw spectrum at a 0-based row and column.
- `get_roi_spectrum()` returns a raw rectangular mean spectrum. In lazy sparse data, the geometric rectangle area remains the denominator so results match the zero-filled full cube.
- `get_channel_image()` applies the current normalization to the selected image.
- TIC is computed during full loading; RMS and Median coefficient maps are created lazily and cached.

Spectrum exports therefore use raw global/ROI spectral values, while rendered channel and line-profile images follow the selected normalization and view-time bin settings.

## 4. ImageViewer

`viewer/image_viewer.py` is a `QGraphicsView` with one active pixmap. It displays either one native-size channel image or one rasterized 2×2 colocalization canvas. Persistent graphics items cover the crosshair, five ROI slots, and five line slots; colocalization mode maintains four visual copies of each annotation while retaining one source-coordinate record.

### Single-channel rendering

```text
float image (H, W)
  → clip and scale with vmin/vmax
  → 8-bit LUT index
  → built-in gray/viridis/hot/inferno RGB LUT
  → QImage.Format_RGB888
  → QPixmap
```

The viridis and inferno LUTs are built-in approximations; matplotlib is not required.

### Four-pane colocalization rendering

`MainWindow` obtains all three display-channel arrays and applies each OverlayPanel Min/Max range independently. It creates permanently visible red-, green-, and blue-tinted RGB arrays plus an additive Merge array containing only enabled slots. `ImageViewer.set_colocalization_images()` places them in Red/Green/Blue/Merge order with a fixed gutter and no text over the image pixels.

The four panes are composed into one pixmap, so the existing `QGraphicsView` transform and scrollbars synchronize zoom and pan without cross-view signal forwarding. Scene-to-image translation identifies the pane, subtracts its offset, and clamps ROI drags to their starting pane. `get_rendered_image()` returns the full canvas; image export places an optional scale bar relative to the Merge-pane bounds.

### Interaction and annotations

- Wheel zooms around the pointer.
- `Shift + wheel` emits a channel-step request.
- Left-drag pans; double-click fits the image.
- Right-drag updates single-channel vmin/vmax.
- `Shift + click` emits `pixel_clicked` and displays a crosshair.
- `Shift + drag` emits an inclusive rectangular `roi_selected` range.
- `Ctrl + drag` allocates the first free line slot and samples the current 2D image with `skimage.measure.profile_line`.

ROI slot ownership is in `MainWindow`; `ImageViewer` renders the supplied coordinates. Line coordinates are owned by `ImageViewer`, which recomputes all active profiles whenever `set_image()` receives a changed channel, normalized image, or binned image.

Colocalization mode blocks only new line-profile drawing because no single intensity image represents the four-pane view. Pixel and ROI spectrum gestures remain active from every pane. Crosshairs, ROIs, and existing line overlays are placed at the same local coordinates in all panes. Right-drag display adjustment is ignored because each color slot has an independent range.

## 5. Spectrum, ROI, Overlay, and Controls

### SpectrumPanel and ROIPanel

`viewer/spectrum_panel.py` contains vertically split Global and Pixel/ROI pyqtgraph plots. Both use stem-style peak rendering and a dashed current-channel marker. The Global plot additionally owns a channel-indexed set of orange dotted `InfiniteLine` favorite markers. Favorite lines use a lower z-order than the blue spectrum stems, while the current-channel line stays above both. Clicking either plot emits the nearest channel index.

The lower plot has one base curve for a selected pixel plus keyed extra curves for active ROIs. `ROIPanel` appears only when ROIs exist and displays each slot's color, pixel count, visibility control, and remove action. It also selects Mean per pixel or Total; Total scales each cached mean spectrum by the ROI's geometric pixel count. Up to five fixed, reusable color slots are available.

`MainWindow` keeps the authoritative five-entry ROI list and updates the image overlays, ROI panel, spectrum curves, and export-action state together.

### OverlayPanel

`viewer/overlay_panel.py` supplies one row for each additive R/G/B slot:

- Merge-inclusion checkbox; individual tinted panes remain visible
- nearest m/z or TIFF channel selector
- independent Min and Max values
- Auto button using 2% nonzero / 98% overall percentiles

It is hidden outside colocalization mode. All slots start enabled. Toggling colocalization disables the normal ControlsPanel but retains its normalization and bin settings when source channel arrays are fetched.

### ControlsPanel

`viewer/controls_panel.py` provides:

- channel slider, direct m/z/channel input, current-channel `☆`/`★` toggle, and a sorted Favorites dropdown that emits the selected channel index
- view-time Bin (Da)
- single-channel Min, Max, and Auto controls
- colormap selection
- normalization selection

Its `_updating` guard prevents programmatic synchronization from recursively emitting user-change signals.

`MainWindow` is the favorite-state owner. Each window maps normalized absolute file paths to sets of channel indices. The map is memory-only, is reused when that window reopens the same path, and is neither persisted with `QSettings` nor shared with another window.

## 6. LineProfileDialog

`viewer/line_profile_dialog.py` wraps the reusable `LineProfilePanel` in a non-modal dialog. Each `MainWindow` maps line slots to at most five dialogs.

Creating a line:

1. `ImageViewer` allocates a free slot, stores endpoints, renders the numbered cyan line, and emits `line_added`.
2. `MainWindow` creates and cascade-positions a `LineProfileDialog`.
3. `ImageViewer` emits sampled distances/intensities through `line_profile_ready`.
4. `MainWindow` forwards the data to the matching dialog.

The dialog title identifies its slot, and its label shows endpoints and geometric pixel length. Closing the dialog emits its slot, causing `MainWindow` to remove the popup and `ImageViewer` to remove the corresponding line. Opening another file, clearing annotations, or closing the owner window closes all line dialogs.

## 7. UserManualDialog and Resource Resolution

`viewer/user_manual_dialog.py` implements the in-app English manual. It is a modal, read-only `QDialog` containing `QTextBrowser` and a Close button. The file is read as UTF-8 and passed directly to Qt's built-in:

```python
browser.setMarkdown(markdown)
```

No Markdown conversion package, PDF renderer, search panel, or table-of-contents widget is used.

The dialog resolves `USER_MANUAL_ENG.md` differently by runtime:

```text
source execution
  viewer/user_manual_dialog.py
  → parent of viewer/
  → <project-root>/USER_MANUAL_ENG.md

PyInstaller execution
  sys.frozen == True
  → sys._MEIPASS/USER_MANUAL_ENG.md
```

`MainWindow._show_user_manual()` catches file and Unicode errors and displays `User Manual Unavailable` instead of opening an empty dialog. The Korean manual remains repository documentation and is not exposed by the in-app menu.

`AboutDialog` uses the same source-versus-`_MEIPASS` pattern for the `assets/` directory.

## 8. Platform Menus

All platforms expose File, View, and Help functionality. The Preferences action uses `QAction.MenuRole.PreferencesRole`.

### macOS

MIRA does not create an Edit menu. The Preferences action is attached to File as an owning menu, then Qt moves it to the native MIRA application menu. About and Quit follow native Qt/macOS application-menu integration. The visible product menus are MIRA, File, View, and Help.

### Windows and Linux

MIRA creates an explicit Settings menu containing Preferences. The menu sequence is File, Settings, View, Help.

The functional actions are:

- **File:** New Window, Open File…, Export Image…, Export Global Spectrum…, Export ROI Spectra…, Quit
- **View:** Show TIC Image, Colocalization Overlay, Reset Zoom, Clear Annotations, Bin Mode → Mean/Sum
- **Help:** User Manual…, About MIRA…

## 9. PyInstaller Build and Resource Layout

`build_mac.sh` creates `packaging/dist/MIRA.app`. `build_win.bat` uses `--onefile` to create `packaging\dist\MIRA.exe`. Both collect pyimzML and pyqtgraph submodules and declare the runtime imports used by image, TIFF, and profile functionality.

Both builds add exactly these data resources:

```text
viewer/                    → viewer/
assets/                    → assets/
USER_MANUAL_ENG.md         → bundle root
```

The resulting runtime resource view is:

```text
sys._MEIPASS/
├── USER_MANUAL_ENG.md
├── viewer/
└── assets/
    ├── MIRA-LOGO_v1.png
    ├── AppIcon.icns
    ├── AppIcon.ico
    ├── ABEL_Logo1.png
    └── SNU_GSCST_ENG.png
```

The macOS build uses `assets/AppIcon.icns`; Windows uses `assets/AppIcon.ico`. `assets/MIRA-LOGO_v1.png` is also displayed in About MIRA. `USER_MANUAL_KOR.md`, `docs/manuals/`, development plans, and references are not bundled.

## 10. Primary Signal Flow

```text
ControlsPanel.channel_changed ─┐
SpectrumPanel.channel_selected ├─→ MainWindow._on_channel_changed()
ImageViewer.channel_step ──────┘       ├─→ MSIDataModel.get_channel/get_bin_image()
                                      ├─→ ImageViewer.set_image()
                                      ├─→ ControlsPanel.set_channel()
                                      └─→ SpectrumPanel.set_channel()

ImageViewer.pixel_clicked ─────────→ MSIDataModel.get_pixel_spectrum()
                                     └─→ SpectrumPanel.update_pixel()

ImageViewer.roi_selected ──────────→ MSIDataModel.get_roi_spectrum()
                                     └─→ MainWindow ROI state
                                         ├─→ ImageViewer overlays
                                         ├─→ ROIPanel
                                         └─→ SpectrumPanel ROI curves

ImageViewer.line_added ────────────→ MainWindow creates LineProfileDialog
ImageViewer.line_profile_ready ────→ matching LineProfileDialog.set_profile()

OverlayPanel.overlay_changed ──────→ MainWindow builds RGB array
                                     └─→ ImageViewer.set_colocalization_images()

ControlsPanel.favorite_toggle_requested
  → MainWindow file-scoped session state
      ├─→ ControlsPanel.set_favorite_state()
      └─→ SpectrumPanel.set_favorites()

ControlsPanel.favorite_channel_selected
  └─→ MainWindow._on_channel_changed()
```

## 11. Current Constraints

- Processed imzML builds a union m/z axis and can take significant time on large datasets.
- Lazy imzML access performs repeated spectrum reads and benefits from fast storage.
- View-time binning stacks channel images rather than slicing a full cube directly.
- Viridis and inferno are internal approximations.
- ROI shapes are rectangular, with a maximum of five.
- Line profiles have a maximum of five and use one shared display color.
- At most three independent MIRA windows can be open.
- RGB colocalization supports at most three additive slots and does not define a line profile for the composite.
- The in-app manual is English only and has no dedicated search or TOC UI.
