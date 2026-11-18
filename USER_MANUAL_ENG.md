# MIRA User Manual

**Mass spectrometry Imaging & Review App**
**Version:** 0.3.5
**Updated:** 2026.09.03
**Applies to:** MIRA v0.3.5

MIRA is a standalone desktop viewer for Mass Spectrometry Imaging (MSI) data. It supports ion-image browsing, pixel and multi-ROI spectrum comparison, spatial line profiles, four-pane RGB colocalization, favorite-channel markers, and image or spectrum export.

---

## Table of Contents

1. [Supported Files and Launching](#1-supported-files-and-launching)
2. [Windows, Layout, and Titles](#2-windows-layout-and-titles)
3. [Opening Data](#3-opening-data)
4. [Ion Image Navigation](#4-ion-image-navigation)
5. [Mouse Controls](#5-mouse-controls)
6. [Brightness, Colormap, and Normalization](#6-brightness-colormap-and-normalization)
7. [Spectrum Panels](#7-spectrum-panels)
8. [Multi-ROI Comparison](#8-multi-roi-comparison)
9. [Line Profiles](#9-line-profiles)
10. [Four-Pane RGB Colocalization](#10-four-pane-rgb-colocalization)
11. [Channel Binning](#11-channel-binning)
12. [TIC Image](#12-tic-image)
13. [Exporting Images and Spectra](#13-exporting-images-and-spectra)
14. [Preferences](#14-preferences)
15. [Menus and Toolbar](#15-menus-and-toolbar)
16. [Built-in User Manual](#16-built-in-user-manual)
17. [Reset and File-Change Behavior](#17-reset-and-file-change-behavior)
18. [Known Limitations](#18-known-limitations)
19. [Version History](#19-version-history)

---

## 1. Supported Files and Launching

### Supported files

| Format | Extensions | Notes |
|---|---|---|
| imzML | `.imzML` with matching `.ibd` | Continuous and Processed modes |
| TIFF | `.tif`, `.tiff` | 2D or multi-channel data; the first Z/T slice is used for a 4D input |

The `.ibd` file for an imzML dataset must have the same base name and be in the same folder. TIFF channels are displayed as channel indices rather than physical m/z values.

### Launching

- From source: install `requirements.txt`, then run `python main.py`.
- macOS and Windows users can run a packaged application produced by the project build scripts.
- See `README.md` for current installation and build instructions.

---

## 2. Windows, Layout, and Titles

MIRA can keep up to **three independent main windows** open at once. Select `File → New Window` (`Ctrl+N` or the platform-equivalent standard New shortcut) to create another window. If three windows are already open, MIRA displays a warning instead.

Each window owns its own:

- loaded dataset and current channel;
- zoom, brightness, colormap, normalization, and bin settings;
- ROI selections and ROI display mode;
- line profiles and their popup windows;
- RGB colocalization state.

The main layout contains:

1. an ion-image canvas on the left;
2. Global Spectrum and Pixel/ROI Spectrum plots on the right;
3. an RGB overlay control panel that appears only while colocalization is active;
4. channel, favorite, brightness, colormap, normalization, and bin controls at the bottom.

Before a file is loaded, the title is `MIRA`. After a successful load, it becomes `MIRA — filename`, using the loaded file's base name. Each independent window updates its own title.

---

## 3. Opening Data

1. Select `File → Open File…` (`Ctrl+O`).
2. Choose an imzML or TIFF file.
3. For an imzML dataset above the configured channel threshold (default **5,000**), choose:
   - **Full resolution**, or
   - load-time binning at a fixed Da width.
4. MIRA loads the data in the background and shows progress.
5. The status bar reports dimensions, channel count, data mode, and load-time bin width when applicable.

Load-time binning averages raw m/z samples into fixed-width bins before normal viewing. For Processed imzML data, the pre-scan channel count is an estimate based on sampled pixels.

Opening a file in one window does not affect any other MIRA window.

---

## 4. Ion Image Navigation

| Control | Action |
|---|---|
| Channel slider | Move through m/z or TIFF channels |
| m/z / Ch field | Enter a value and confirm to jump to the nearest channel |
| ☆ / ★ | Add or remove the current channel from this file's session favorites |
| Favorites dropdown | Select any saved favorite and jump to it immediately |
| Mouse wheel | Zoom around the pointer |
| Shift + mouse wheel | Step to the previous/next channel without zooming |
| Left-drag | Pan |
| Double-click | Fit the image to the view |
| Spectrum-plot click | Jump to the nearest channel represented by the clicked x position |

The spectrum plots mark the current channel with a red dashed vertical line. During RGB colocalization there is no single representative channel, so slider input, Shift+wheel navigation, and spectrum-click navigation are disabled or ignored until the overlay is turned off.

---

## 5. Mouse Controls

| Gesture | Action |
|---|---|
| Left-drag | Pan the image |
| Shift + click | Select one pixel and show its raw spectrum with a yellow crosshair |
| Shift + left-drag | Add a rectangular ROI |
| Ctrl + left-drag | Add a line profile |
| Right-drag up/down | Shift brightness |
| Right-drag left/right | Change contrast |
| Wheel | Zoom |
| Shift + wheel | Step channels |
| Double-click | Reset zoom |

A Shift-drag smaller than about 2 pixels in both dimensions is treated as a pixel selection. A Ctrl-drag shorter than about 2 pixels is discarded.

Selection gestures are always available without a separate ROI or line mode. The exception is that new line profiles are blocked while RGB colocalization is active.

---

## 6. Brightness, Colormap, and Normalization

### Brightness and contrast

For a normal single-channel image, use:

- the **Min** and **Max** fields for exact display limits;
- right-drag vertically for brightness and horizontally for contrast;
- **Auto** to set Min from the 2nd percentile of nonzero values and Max from the 98th percentile of all values in the currently displayed channel or view-time bin.

These controls affect rendering, not the stored raw spectra.

### Colormap

The available single-channel colormaps are `gray`, `viridis`, `hot`, and `inferno`. The non-gray maps are built-in approximations and do not require matplotlib.

### Normalization

| Mode | Displayed image |
|---|---|
| `none` | Raw intensity |
| `TIC` | Divided by each pixel's total ion current |
| `RMS` | Divided by each pixel's root-mean-square intensity |
| `Median` | Divided by each pixel's median intensity |

Normalization affects channel images, view-time binned images, and line profiles computed from those displayed values. Global, pixel, and ROI spectra remain raw.

---

## 7. Spectrum Panels

The right side contains two resizable stem-plot panels:

- **Global Spectrum** is the raw sum across all pixels.
- **Pixel/ROI Spectrum** shows a selected pixel spectrum and any visible ROI spectra.

Shift-clicking a pixel updates the base Pixel Spectrum curve and places a crosshair. Adding an ROI clears that pixel curve and crosshair so the ROI comparison remains clear. Active ROI curves can then be compared together in the lower plot.

Clicking either plot selects the nearest channel when normal single-channel viewing is active.

### Favorite channel markers

Use the `☆` button beside the m/z/Ch field to bookmark the current channel. A bookmarked channel shows `★`, and every favorite is drawn as a short-dotted orange vertical line behind the blue Global Spectrum stems. The thicker pink dashed line remains the current-channel indicator.

The adjacent **Favorites** dropdown lists saved channels in ascending m/z/Ch order. Selecting an entry immediately uses the normal channel-navigation path. Up to 10 entries are visible at once; longer lists use a vertical scrollbar on every platform, including macOS. Favorites are stored per file in the current MIRA window for the lifetime of the application. Reopening the same path in that window restores its dropdown and markers; another window or a restarted application starts independently. Clicking a marker position also uses nearest-channel navigation. Favorites do not appear in the Pixel/ROI Spectrum and cannot be changed while colocalization disables the normal controls.

---

## 8. Multi-ROI Comparison

MIRA supports up to **five rectangular ROIs per main window**.

### Add and identify ROIs

1. Hold `Shift` and left-drag a rectangle.
2. MIRA assigns the first free slot, numbered 1–5.
3. The ROI appears with its slot color and number on the image.
4. A row appears above the lower spectrum plot with the slot color, pixel count, inclusive x/y bounds, a **Visible** checkbox, and a remove button.

The five slot colors are fixed. Removing an ROI frees that slot; the next ROI uses the first available slot. If all slots are occupied, a sixth ROI is rejected and the existing selections remain unchanged.

### Mean and Total

The **ROI intensity** selector controls all displayed and exported ROI curves:

- **Mean per pixel**: the raw mean spectrum of all pixels in each rectangle.
- **Total (sum of all pixels)**: the mean spectrum multiplied by the rectangle's pixel count.

This setting does not alter the Global Spectrum. ROI spectra are raw and are not affected by image normalization, brightness, colormap, or view-time binning.

### Visibility and removal

- Clear **Visible** to hide that ROI's rectangle and spectrum curve without deleting its data.
- Use the row's `✕` button to delete the ROI and free its slot.
- `Clear` or `View → Clear Annotations` removes every ROI at once.

---

## 9. Line Profiles

MIRA supports up to **five simultaneous line profiles per main window**.

1. Hold `Ctrl` and left-drag a line across the image.
2. MIRA assigns the first free line slot and draws a numbered cyan line.
3. A separate, **non-modal** `Line Profile N` popup opens. It shows endpoint coordinates, geometric length in pixels, and a Distance (px) versus Intensity plot.

Because the popup is non-modal, you can continue using the main window and compare all open line windows. Profile values are sampled from the displayed single-channel image and are automatically recomputed after channel, normalization, or view-time bin changes.

Closing a line-profile popup **deletes that line**, removes its overlay, and frees its slot. If five profiles are active, close one popup before drawing another.

Use the toolbar **Clear** button or `View → Clear Annotations` to close all line popups and delete all lines. Line profiles use independent popups and have no separate visibility toggle.

---

## 10. Four-Pane RGB Colocalization

Select the checkable toolbar action **Colocalization** or `View → Colocalization Overlay`. An **Overlay Controls (R/G/B)** panel appears.

The image canvas changes to a synchronized 2×2 publication-style layout:

```text
Red    | Green
Blue   | Merge
```

Each R, G, and B row has:

- a checkbox that includes or excludes the color channel from **Merge**;
- an m/z field, or a Ch field for TIFF, resolved to the nearest available channel;
- independent **Min** and **Max** display limits;
- **Auto**, which uses the selected channel's nonzero 2nd percentile for Min and all-value 98th percentile for Max.

All three rows start enabled. Each individual pane is independently scaled to 0–255 and remains visible in its red, green, or blue tint even when its checkbox is cleared. Enabled channels combine additively in Merge; if all three boxes are cleared, only Merge becomes black. Set meaningful limits with Max greater than Min; Auto is the recommended starting point.

### Behavior and constraints

- Zoom, pan, double-click reset, pixel crosshairs, ROIs, and existing line overlays are synchronized at the same source-image coordinates in all four panes.
- A pixel or ROI can be selected from any pane. A drag that crosses a pane boundary is clamped to the pane where it started.
- The regular channel, brightness, colormap, normalization, and bin controls are disabled while the overlay panel is active.
- The RGB rows still use the already selected normalization, view-time bin width, and Mean/Sum bin mode.
- Shift-click pixel spectra and Shift-drag ROIs remain available because they query full raw spectra.
- New Ctrl-drag line profiles are blocked because an RGB composite has no single intensity channel.
- Right-drag brightness/contrast and single-channel navigation do not apply.
- Existing line-profile popups remain open but do not represent the RGB composite.
- Image export saves the full 2×2 grid without pane text labels. An optional scale bar is placed in the Merge pane.
- `View → Show TIC Image` exits colocalization and displays the TIC image.
- Turning colocalization off restores the previous current channel in normal single-channel mode.

---

## 11. Channel Binning

MIRA has two independent binning stages.

### View-time binning

Set **Bin (Da)** in the bottom controls:

- `0` displays one channel.
- A positive width combines channels within `± width/2` around the selected m/z.
- `View → Bin Mode → Mean` averages those channels.
- `View → Bin Mode → Sum` adds them.

View-time binning affects displayed ion images, RGB source channels, and line profiles. It does not change Global, Pixel, or ROI spectra.

### Load-time binning

For imzML files above the Preferences threshold, the open dialog can reduce spectral resolution before the dataset is loaded. Load-time binning changes the loaded m/z axis and therefore all subsequent images and spectra.

---

## 12. TIC Image

Select `View → Show TIC Image` or the toolbar **TIC Image** action to display the per-pixel sum over all channels. MIRA applies automatic 2nd/98th percentile display limits.

Showing TIC exits RGB colocalization. Select a normal channel afterward to return to an ion image.

---

## 13. Exporting Images and Spectra

### Export Image

`File → Export Image…` (`Ctrl+Shift+S`) saves the currently rendered image as PNG, JPG, or TIFF. This includes the current single-channel colormap and display limits or the fixed-order Red/Green/Blue/Merge 2×2 colocalization grid without overlaid pane names.

An optional scale bar supports:

- units of µm, nm, or px;
- custom length and bottom-left/bottom-right position;
- metadata-derived pixel size when available, or manual entry.

Single-channel exports use the native data dimensions. A colocalization export uses four native-size panes separated by a small gutter; its scale bar is positioned inside Merge. Interactive ROI, crosshair, and line annotations are not painted into the export.

### Export Global Spectrum

`File → Export Global Spectrum…` writes a CSV with:

- `m/z` or `Channel` as the first column;
- `Global Intensity` as the raw sum across all pixels.

### Export ROI Spectra

`File → Export ROI Spectra…` is enabled when at least one ROI exists. It writes one x-axis column followed by one column per active ROI in slot order. Headers include ROI numbers and bounds. Values follow the current **Mean per pixel** or **Total** selection.

Hidden ROIs remain active and are included in the ROI CSV; remove an ROI to exclude it. MIRA appends `.csv` if needed.

---

## 14. Preferences

Preferences are available before or after loading data:

- **macOS:** `MIRA → Preferences…`
- **Windows/Linux:** `Settings → Preferences…`

The **Large-file channel threshold** controls when the spectral-resolution dialog appears for imzML data. The default is 5,000 channels, and the allowed setting range is 1,000–100,000. The value is stored between sessions.

---

## 15. Menus and Toolbar

### Platform menu layout

- **macOS:** `MIRA | File | View | Help`
- **Windows/Linux:** `File | Settings | View | Help`

macOS places Preferences, About, and Quit according to native application-menu conventions. Windows/Linux provides Preferences under Settings.

### File

| Item | Action |
|---|---|
| New Window | Open an independent MIRA window, up to three total |
| Open File… | Open imzML or TIFF |
| Export Image… | Save the current rendered image |
| Export Global Spectrum… | Save the raw global spectrum CSV |
| Export ROI Spectra… | Save active ROI spectra CSV |
| Quit | Close the current MIRA window |

### View

| Item | Action |
|---|---|
| Show TIC Image | Display the TIC image |
| Colocalization Overlay | Toggle RGB colocalization |
| Reset Zoom | Fit the image (`Ctrl+0`) |
| Clear Annotations | Delete all ROIs, pixel crosshair, and line profiles |
| Bin Mode → Mean / Sum | Choose view-time bin aggregation |

### Help

| Item | Action |
|---|---|
| User Manual… | Open the bundled English v0.3.5 manual |
| About MIRA… | Show product, version, update date, and affiliation |

### Toolbar

`[Open]  [TIC Image]  [Colocalization]  [Zoom Reset]  [Clear]`

The Colocalization toolbar action stays synchronized with its View-menu item. Clear performs the same annotation cleanup as `View → Clear Annotations`.

---

## 16. Built-in User Manual

`Help → User Manual…` opens this English Markdown manual in a read-only, resizable dialog. You can scroll, select, and copy text, then close the dialog with its Close button or window control.

The command is available even when no MSI file is loaded. Packaged MIRA applications include only the current English root manual; the Korean manual and historical snapshots remain repository documents.

---

## 17. Reset and File-Change Behavior

### Clear

Toolbar **Clear** and `View → Clear Annotations` remove:

- all ROI boxes and ROI spectra;
- the selected-pixel crosshair and pixel curve;
- all line overlays and line-profile popups.

They preserve the loaded file, current channel, zoom, brightness, colormap, normalization, bin settings, and RGB toggle state.

### Opening another file in the same window

A successful new load:

- clears ROIs, the pixel selection, and all line profiles;
- closes all line-profile popups;
- turns off RGB colocalization;
- resets ROI intensity mode to Mean per pixel;
- initializes the new dataset's controls, spectra, status, and window title.

Other main windows are unaffected.

Favorite channels are kept separately by normalized file path for the current application session. Reopening an earlier file in the same window restores its favorites; quitting MIRA discards them.

---

## 18. Known Limitations

- A maximum of three main windows, five ROIs per window, and five line profiles per window can be active.
- RGB colocalization supports exactly three additive color slots (R/G/B), with one nearest channel per slot and a fixed 2×2 layout.
- RGB colocalization does not create RGB-aware line profiles; draw lines in single-channel mode.
- Favorite channels are session-only and are not shared between windows.
- The m/z navigator is a numeric field, not a list of every channel.
- Processed imzML files build a shared axis from all observed m/z values and may load slowly.
- imzML binary data above 500 MB uses lazy access, which can make repeated image, ROI, or spectrum queries slower; an SSD is recommended.
- `viridis` and `inferno` are built-in approximations rather than exact matplotlib maps.

---

## 19. Version History

| Version | Highlights |
|---|---|
| v0.1 | Initial imzML viewer, spectra, normalization, and TIC |
| v0.2.1 | Stem spectra, direct m/z input, view-time binning, image export |
| v0.2.2 | Load-time binning and TIFF support |
| v0.2.3 | Standalone Windows distribution groundwork |
| v0.2.4 | ROI spectrum, line profile, Shift+wheel navigation |
| v0.3.0 | Up to five colored ROIs, Mean/Total comparison, ROI and Global CSV |
| v0.3.1 | Up to five non-modal line-profile popups and Clear Annotations |
| v0.3.2 | R/G/B colocalization with per-channel Min/Max/Auto |
| v0.3.3 | Up to three independent main windows and dynamic titles |
| v0.3.4 | Built-in English manual, platform-specific menu cleanup, and refreshed app branding and documentation |
| **v0.3.5** | **Synchronized Red/Green/Blue/Merge four-pane colocalization and per-file session favorite markers** |

For release details, see `CHANGELOG.md`.
