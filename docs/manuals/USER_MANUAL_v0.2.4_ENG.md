# MIRA User Manual

**Mass spectrometry Imaging & Review App**
**Version**: 0.2.4
**Applies to**: MIRA v0.2.4 (features up to and including ROI Spectrum, Line Profile, and Shift+wheel channel navigation)

> This is a plain-text/Markdown working manual covering everything implemented through v0.2.4. A polished, screenshot-illustrated user guide will be produced separately for the official release.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Supported File Formats](#2-supported-file-formats)
3. [Installation & Launching](#3-installation--launching)
4. [Main Window Layout](#4-main-window-layout)
5. [Opening a File](#5-opening-a-file)
6. [Ion Image Navigation](#6-ion-image-navigation)
7. [Mouse Controls Reference](#7-mouse-controls-reference)
8. [Brightness & Contrast](#8-brightness--contrast)
9. [Colormap](#9-colormap)
10. [Spectrum Panels](#10-spectrum-panels)
11. [ROI Region Spectrum (Shift+drag)](#11-roi-region-spectrum-shiftdrag)
12. [Line Profile (Ctrl+drag)](#12-line-profile-ctrldrag)
13. [Channel Binning](#13-channel-binning)
14. [TIC Image](#14-tic-image)
15. [Normalization](#15-normalization)
16. [Image Export](#16-image-export)
17. [Preferences](#17-preferences)
18. [Menu & Toolbar Reference](#18-menu--toolbar-reference)
19. [Known Limitations](#19-known-limitations)
20. [Version History Summary](#20-version-history-summary)

---

## 1. Introduction

MIRA is a standalone desktop viewer for Mass Spectrometry Imaging (MSI) data. It lets you browse ion images channel by channel, inspect spectra at individual pixels or over regions, measure spatial intensity profiles, and export publication-ready images — all without needing a Python environment (once packaged as a `.app`/`.exe`).

---

## 2. Supported File Formats

| Format | Extensions | Notes |
|---|---|---|
| imzML | `.imzML` (+ matching `.ibd`) | Both **Continuous** and **Processed** modes are supported |
| Multi-channel TIFF | `.tif`, `.tiff` | CYX / ZYX / YX layouts; channel axis auto-detected via `tifffile` |

For imzML files, the matching `.ibd` binary file must be present in the **same folder** as the `.imzML` file — it is loaded automatically.

---

## 3. Installation & Launching

See `README.md` in the project root for full installation instructions (source run, macOS `.app` build, Windows `.exe` build). In short:

- **From source**: `pip install -r requirements.txt` then `python main.py`
- **macOS**: run `build_mac.sh` to produce `MIRA.app`
- **Windows**: run `build_win.bat` locally, or download the `.exe` artifact built by GitHub Actions

---

## 4. Main Window Layout

```
┌───────────────────────────────────────────────────────┐
│  Menubar: File | Edit | View | Help                    │
│  Toolbar: [Open] [TIC Image] [Line Profile] [Zoom Reset]│
├────────────────────────────┬───────────────────────────┤
│                            │   Global Spectrum          │
│      Ion Image             ├───────────────────────────┤
│   (QGraphicsView canvas)   │   Pixel / ROI Spectrum     │
│                            │                            │
├────────────────────────────┴───────────────────────────┤
│  Controls: Channel slider · m/z input · Bin (Da) ·      │
│            Brightness/Contrast · Colormap · Normalize   │
├──────────────────────────────────────────────────────── ┤
│  Line Profile dock (bottom, hidden by default —          │
│  opens automatically the first time you draw a line)    │
└───────────────────────────────────────────────────────┘
```

- The image view and spectrum panels sit in a resizable horizontal split (drag the divider to resize).
- The Line Profile panel is a dockable Qt panel: you can drag its title bar to move it, float it as its own window, or close it — see [Section 12](#12-line-profile-ctrldrag).

---

## 5. Opening a File

1. `File → Open File…` (or `Ctrl+O`).
2. Choose an `.imzML`, `.tif`, or `.tiff` file.
3. **For large imzML files** (channel count above the configured threshold, default **5,000** — see [Preferences](#17-preferences)): a **Large File — Spectral Resolution** dialog appears, offering:
   - **Full resolution** — load every channel as-is (may be slow to render/navigate).
   - **Bin at `X` Da** — reduce the effective channel count by averaging m/z values into fixed-width bins before loading. A live preview shows the estimated resulting channel count.
4. A progress dialog is shown while the file loads in the background (the UI stays responsive).
5. Once loaded, the status bar shows image dimensions, channel count, current mode, and (if applicable) the load-time bin width used.

Opening a new file automatically clears any previously drawn ROI box and line profile (their pixel coordinates may no longer be valid at the new image size).

---

## 6. Ion Image Navigation

| Control | Action |
|---|---|
| **Channel slider** (bottom panel) | Drag to scrub through m/z channels / TIFF channels |
| **m/z SpinBox** | Type an m/z value and press Enter → jumps to the nearest channel |
| **Mouse wheel** (over image) | Zoom in / out, centered on the cursor |
| **Shift + mouse wheel** | Step to the next (+1) or previous (−1) channel without changing zoom |
| **Left-click drag** | Pan the image |
| **Double-click** | Reset zoom to fit the image in the view |

For TIFF files, the channel axis has no physical m/z meaning, so labels switch to plain **channel index** ("Ch") instead of m/z.

---

## 7. Mouse Controls Reference

Complete summary of every mouse gesture on the image canvas:

| Gesture | Action |
|---|---|
| Wheel scroll | Zoom in/out (centered on cursor) |
| Shift + Wheel scroll | Step m/z channel (up = +1, down = −1) |
| Left-click drag | Pan (move image) |
| Shift + Left-click | Select a single pixel → show its spectrum + yellow crosshair |
| Shift + Left-click drag | Draw an ROI box → show mean spectrum of enclosed pixels (see [Section 11](#11-roi-region-spectrum-shiftdrag)) |
| Ctrl + Left-click drag | Draw a line → show spatial intensity profile along it (see [Section 12](#12-line-profile-ctrldrag)) |
| Right-click drag (up/down) | Adjust brightness (shift window center) |
| Right-click drag (left/right) | Adjust contrast (scale window width) |
| Double-click | Reset zoom |

**Design note**: `Shift` is always used for *selection* (pixel/ROI/channel), and `Ctrl` is always used for *measurement* (line profile). Both drag gestures are active at all times — there is no separate "mode" to toggle on/off; a plain left-click drag with no modifier always pans, regardless of what else you've drawn.

---

## 8. Brightness & Contrast

Two equivalent ways to adjust the displayed intensity window (`vmin`/`vmax`):

1. **Min / Max spinboxes** in the controls panel — type exact values.
2. **Right-click drag** on the image (ITK-SNAP style):
   - Drag **up/down** → shifts brightness (window center).
   - Drag **left/right** → scales contrast (window width).
3. **Auto button** — automatically sets `vmin`/`vmax` to the 2nd–98th percentile of the *currently displayed* channel's intensity values.

All three methods stay in sync — adjusting one updates the others.

---

## 9. Colormap

Choose from the **Colormap** dropdown in the controls panel:

| Name | Description |
|---|---|
| `gray` | Standard grayscale |
| `viridis` | Perceptually uniform purple → blue → teal → green → yellow |
| `hot` | Black → red → orange → yellow → white |
| `inferno` | Black → purple → orange → yellow |

`viridis`, `hot`, and `inferno` are built-in approximations (no `matplotlib` dependency required).

---

## 10. Spectrum Panels

The right-hand side shows two stacked plots, both rendered as **stem plots** (one vertical line per m/z peak, no connecting lines or markers):

1. **Global Spectrum** — sum of intensities across *all* pixels, computed once per file load. A red dashed vertical line marks the currently selected channel.
2. **Pixel / ROI Spectrum** — updates based on your most recent selection:
   - **Shift+click** a pixel → shows that pixel's raw spectrum, labeled `Pixel Spectrum (x=.., y=..)`.
   - **Shift+drag** an ROI box → shows the mean spectrum of the enclosed pixels, labeled `ROI Spectrum (x: c0–c1, y: r0–r1)` (see [Section 11](#11-roi-region-spectrum-shiftdrag)).

Clicking anywhere on either spectrum plot jumps the viewer to that m/z channel (same as typing it into the m/z spinbox).

---

## 11. ROI Region Spectrum (Shift+drag)

**What it does**: lets you select a rectangular region on the ion image and view the **mean spectrum of every pixel inside it**, instead of just a single pixel.

**How to use it**:
1. Hold `Shift` and left-click-drag a box over the region of interest on the image.
2. While dragging, a semi-transparent yellow rectangle overlay follows your cursor in real time.
3. Release the mouse button:
   - If the box you drew is essentially a single point (less than ~2 px in both directions), MIRA treats it as a normal **Shift+click** and shows the single-pixel spectrum instead (with the yellow crosshair, not a box).
   - Otherwise, the ROI box stays drawn on the image, and the Pixel/ROI Spectrum panel updates to show the **mean spectrum** of all pixels inside the box, labeled `ROI Spectrum (x: c0–c1, y: r0–r1)`.
4. Draw a new ROI (or Shift+click a single pixel) at any time to replace the current one — only one ROI is kept active at a time in this version.

**Notes**:
- The ROI spectrum is a **raw mean** (not normalized) — the Normalize dropdown only affects the *displayed image*, not spectrum values, for consistency with the single-pixel spectrum.
- Opening a new file clears any existing ROI overlay.

---

## 12. Line Profile (Ctrl+drag)

**What it does**: lets you draw a straight line across the ion image and see how intensity (at the current channel) varies **spatially** along that line.

**How to use it**:
1. Hold `Ctrl` and left-click-drag a line across the image, in any direction.
2. While dragging, a cyan line overlay follows your cursor in real time.
3. Release the mouse button:
   - If the line is shorter than ~2 px, it is discarded (treated as an accidental click).
   - Otherwise, the line is finalized, its profile is computed, and the **Line Profile** dock panel at the bottom of the window opens automatically (if it wasn't already visible) showing a plot of **Distance (px)** on the x-axis vs. **Intensity** on the y-axis.
4. Draw a new line at any time to replace the current one — only one line is kept active at a time in this version.

**Automatic behavior**:
- The profile **recomputes automatically** whenever you change the channel, normalization mode, or bin width — you don't need to redraw the line.
- The `Line Profile` toolbar button and the `View → Line Profile` menu item are two views of the **same toggle** — checking/unchecking it only shows or hides the dock panel; it does **not** enable or disable the Ctrl+drag gesture itself, which is always available.
- If you close the dock with its title-bar **X** button, the toolbar/menu checkbox automatically unchecks itself. Drawing a new line will reopen it and re-check the box.
- The dock can be dragged to a different edge of the window or "floated" as its own window, like any standard Qt dock widget.
- Opening a new file clears the current line and hides its overlay (though the dock panel itself stays wherever you left it).

---

## 13. Channel Binning

MIRA supports two independent kinds of m/z binning:

### 13.1 View-time Binning ("Bin (Da)")

- Located in the controls panel next to the m/z SpinBox.
- Set a bin width in Da (default `0` = disabled, single-channel mode).
- When set to a value > 0, the displayed ion image becomes the **mean** (or **sum**) of all channels whose m/z falls within `± (bin width / 2)` of the currently selected m/z.
- Toggle **Mean vs. Sum** aggregation via `View → Bin Mode → Mean / Sum`.
- This only affects the *displayed image* — spectra shown in the side panels are unaffected.

### 13.2 Load-time Binning (for large files)

- Applies only to imzML files whose channel count exceeds your configured threshold (default 5,000 — see [Preferences](#17-preferences)).
- Shown as a dialog at file-open time (see [Section 5](#5-opening-a-file)): choose full resolution or bin at a fixed Da width *before* the file is fully loaded.
- This reduces memory usage and dramatically improves rendering/navigation speed for very high-resolution raw imzML files.
- The status bar shows the load-time bin width that was applied, if any.

---

## 14. TIC Image

`View → Show TIC Image` (or the **TIC Image** toolbar button) displays the **Total Ion Current** image — the per-pixel sum of intensities across *all* channels — useful as a tissue/sample outline reference independent of any single m/z channel.

---

## 15. Normalization

The **Normalize** dropdown in the controls panel offers:

| Mode | Description |
|---|---|
| `none` | Raw intensity values (default) |
| `TIC` | Normalize each pixel by its total ion current |
| `RMS` | Normalize each pixel by its root-mean-square intensity |
| `Median` | Normalize each pixel by its median intensity |

Normalization affects only the **displayed image**; the Global/Pixel/ROI spectrum panels always show raw (un-normalized) values for reproducibility.

---

## 16. Image Export

`File → Export Image…` (`Ctrl+Shift+S`) saves exactly what's currently on screen (current channel/bin, colormap, brightness/contrast) to a file.

**Options**:
- **Format**: PNG, JPG, or TIFF.
- **Scale bar** (optional): toggle on, then choose:
  - **Unit**: µm, nm, or px.
  - **Length**: the scale bar's length in the chosen unit.
  - **Pixel size**: auto-filled from imzML metadata when available (editable if not, or for TIFF files); used to convert physical units to pixels.
  - **Position**: bottom-right or bottom-left.
- Export resolution matches the native image pixel dimensions (no upsampling).

---

## 17. Preferences

`Edit → Preferences…` currently exposes:

| Setting | Description | Default |
|---|---|---|
| **Large-file channel threshold** | If an imzML file's channel count exceeds this value, the Load-time Binning dialog is shown at open time (see [Section 13.2](#132-load-time-binning-for-large-files)) | 5,000 channels |

Preferences are stored via `QSettings` and persist across sessions.

---

## 18. Menu & Toolbar Reference

### File
| Item | Shortcut | Action |
|---|---|---|
| Open File… | `Ctrl+O` | Open an imzML or TIFF file |
| Export Image… | `Ctrl+Shift+S` | Save the current view as PNG/JPG/TIFF |
| Quit | `Ctrl+Q` | Close MIRA |

### Edit
| Item | Action |
|---|---|
| Preferences… | Open the Preferences dialog |

### View
| Item | Action |
|---|---|
| Show TIC Image | Display the Total Ion Current image |
| Reset Zoom | `Ctrl+0` — fit the image to the view |
| Line Profile | Toggle visibility of the Line Profile dock panel |
| Bin Mode → Mean / Sum | Choose the aggregation mode for view-time channel binning |

### Help
| Item | Action |
|---|---|
| About MIRA… | Show version, credits, and affiliation |

### Toolbar
`[Open]  [TIC Image]  [Line Profile]  [Zoom Reset]`

---

## 19. Known Limitations

- The m/z direct-navigation control is a **SpinBox only** — there is no dropdown list of all channels. With imzML files often containing thousands to tens of thousands of channels, a flat list would be impractical; typing the m/z value directly (or using load-time binning to reduce channel count) is the intended workflow.
- Only **one** ROI box and **one** line profile can be active at a time in this version (multi-region comparison is planned for a future release).
- `viridis` and `inferno` colormaps are hand-tuned approximations, not exact matplotlib equivalents.
- Processed-mode imzML files build their shared m/z axis from the union of all pixel m/z values, which can be slow for very large datasets.
- Lazy loading (files > 500 MB) re-reads from disk on every pixel/ROI/line query — a fast SSD is recommended for large files.

---

## 20. Version History Summary

| Version | Highlights |
|---|---|
| v0.1 | Initial release: imzML viewer, ion image browsing, spectrum display, normalization, TIC image |
| v0.2.1 | Stem-plot spectra, m/z direct input, channel bin size, image export |
| v0.2.2 | Load-time spectral binning, multi-channel TIFF support, Windows build groundwork |
| v0.2.3 | Standalone Windows `.exe` distribution via GitHub Actions |
| **v0.2.4** | **ROI region spectrum (Shift+drag), Line profile (Ctrl+drag), Shift+wheel channel navigation** |

For full technical details of each release, see `CHANGELOG.md` in the project root.
