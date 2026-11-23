# Using the TUI

The MUST TUI launches in a terminal and provides interactive access to telemetry parameters,
their metadata, and time-series plots.

Press `F1` at any time for an in-app help screen covering usage and the full list of keyboard
shortcuts — the same reference as the [Global Key Bindings](#global-key-bindings) section below,
generated from the app's own bindings so the two can't drift apart.

![MUSTApp TUI screenshot](images/mustapp-tui.png)

---

## Layout Overview

The interface is divided into six main areas:

```
┌──────────────────────────────────────────────────────────┐
│  Header                                                  │
├──────────────────────────────────────────────────────────┤
│  Search Input                              [Regex] □     │
├─────────────────┬────────────────────────────────────────┤
│                 │  Parameter Info  │  Parameter Metadata │
│  Parameter List ├──────────────────────────────────────  │
│                 │  Plot Controls                         │
│                 ├────────────────────────────────────────┤
│                 │  Plot                                  │
├─────────────────┴────────────────────────────────────────┤
│  Status Line (provider, connection, catalog, cache age)  │
├──────────────────────────────────────────────────────────┤
│  Footer (key bindings)                                   │
└──────────────────────────────────────────────────────────┘
```

---

## Panels

### Search Input

The search box at the top filters or navigates the parameter list as you type.

- **Filter mode** (default): The list is narrowed down to parameters whose name or description
  match the search text.  By default the search text is treated as a regular expression.
  Uncheck the **Regex** checkbox to switch to fuzzy matching instead.
- **Jump mode**: The best fuzzy match is highlighted in the alphabetically sorted list, with up to
  500 neighbouring parameters shown around it. Toggle jump mode with `Ctrl+J`.

The **Regex** checkbox (top-right of the search bar) switches between regex and fuzzy matching
while in filter mode.

The search checks the MIB name, the description shown in brackets in the list, and the MUST/PCF
extended description — each as its own field, so an anchored pattern like `^NC01_FRAME` matches
the bracketed description directly, not just where it happens to sit inside the full list entry.

The search runs once you pause typing for a moment, not on every keystroke, and a spinner covers
the parameter list while it's running. While a regular expression is incomplete or invalid (e.g.
an unclosed parenthesis), the list keeps showing the previous matches.

### Parameter List

The left panel lists all parameters retrieved from the MUST server for the configured data
provider.  Each entry is shown as:

```
MIBNAME [Description]
```

To keep the interface responsive, the list shows at most 500 parameters at a time out of however
many currently match. When there are more, the last entry reports how many are left out; select it
(or press **Enter** while it's highlighted) to load all of them — this can take a few seconds for a
very large, unfiltered list — or refine the search instead to narrow it down.

Scroll through the list with the arrow keys or the mouse. Press **Enter** (or click) to select
a parameter — this loads its MIB info, server metadata, and time-series data into the other panels.
Server data is loaded in the background, so the interface stays responsive. If you select another
parameter before the previous one has finished loading, the previous request is cancelled and only
the latest selection is loaded. A request is abandoned, and reported in a dialog, when the MUST
server sends no data for 30 seconds; slow transfers that keep receiving data are not interrupted.

### Parameter Info

The upper-centre panel shows technical details read from the **PCF file of the MIB** for the
selected parameter.

| Field | Description |
|---|---|
| `par_name` | MIB parameter name |
| `description` | Short mnemonic description |
| `description_2` | Extended description |
| `pid` | On-board identifier of the telemetry parameter |
| `unit` | Engineering unit mnemonic |
| `decim` | Number of decimal places to be used for displaying real values of this monitoring parameter |
| `ptc` | Parameter Type Code |
| `pfc` | Parameter Format Code |
| `width` | 'Padded' width of this parameter expressed in number of bits |
| `valid` | Name of the parameter to be used to determine the state validity of the parameter specified in this record |
| `related` | Name of monitoring parameter |
| `categ` | Calibration category: N=numeric, S=status, T=text |
| `natur` | Nature of the parameter: R=raw, D=dynamic OL, H=hardcoded, S=save synthetic, C=constant |
| `curtx` | Parameter calibration identification name |
| `inter` | Flag controlling extrapolation behavior |
| `uscon` | |
| `parval` | Raw value for a constant parameter |
| `subsys` | |
| `valpar` | Raw value for a validity parameter |
| `sptype` |  |
| `corr` | Flag that controls correlation of absolute time parameters |
| `obtid` | OBT ID |
| `darc` |  |
| `endian` | Endianness: 'B' or 'L' |

### Parameter Metadata

The upper-right panel shows live metadata fetched from the **MUST server** for the selected
parameter.

| Field | Description |
|---|---|
| `description` | Parameter mnemonic from the server |
| `data-type` | Data type (e.g. `UNSIGNED_SMALL_INT`) |
| `first-sample` | Timestamp of the earliest available sample |
| `last-sample` | Timestamp of the most recent available sample |
| `subsystem` | Subsystem (e.g. `TM`) |
| `id` | Internal parameter identifier |
| `unit` | Engineering unit |
| `parameter-type` | Parameter type |
| `name` | MIB name |
| `provider` | Data provider name |
| `plotted-samples` | Number of data points fetched for the current plot; `–` while unknown (computed locally, not from MUST) |

### Plot Controls

A toolbar between the info panels and the plot area:

| Control | Action |
|---|---|
| **Clear Plot** button | Remove all plotted traces |
| **Plot: TUI / Plot: Matplotlib** button | Toggle between the built-in TUI plot and an external Matplotlib window |
| **Range…** button (`F6`) | Pick a time range from presets, the selected parameter's data range, or recently used ranges |
| **Y Range** button | Set an explicit Y-axis minimum and maximum, or go back to auto-scaling |
| **Start → End** fields | Set the start and end time (UTC) for data retrieval and the plot x-axis |
| **Lock** checkbox | Keep the duration fixed: changing one end moves the other end along |

The **Range…** button (or `F6`, from anywhere on the main screen) opens a list to pick a time range
from, with Enter or a click (Escape cancels):

- **Presets**, relative to the moment the list is opened: last hour, last 6 hours, last 24 hours,
  last 3, 7 and 30 days, today (UTC midnight up to now) and yesterday (midnight to midnight).
- **Parameter data range**: the selected parameter's first and last sample, as reported by MUST.
  When there is no such range (no parameter selected yet, or it has no data), the entry says why and
  can't be selected.
- **Last hour/6 hours/24 hours/3, 7 and 30 days of data**: the same durations, but ending at the
  selected parameter's last sample instead of now, for a parameter that stopped reporting a while
  ago. The start is not clamped to the first sample, so for a parameter with less data than the
  chosen duration, the plot simply starts empty. Only shown when the parameter data range is available.
- **Recent**: the 10 most recently applied time ranges, however they were set (typed, picked from
  this list, …), except the current one.

The recent ranges are saved in `time_ranges.json` in the cache directory (see
[Environment](env.md)), and the app starts with the most recent one. The very first time, or when
that file is missing or unreadable, it starts with the last day up to now. A range is always
remembered as absolute start and end times: picking "Last 6 hours" today and restarting tomorrow
gives today's 6 hours again, not tomorrow's — pick the preset again for that.

By default the Y-axis auto-scales to fit whatever is currently plotted. The **Y Range** button opens
a small dialog with **Min** and **Max** fields (pre-filled with the currently plotted data's range,
or the active locked range if one is set) and three actions: **Apply** (validates that Min is less
than Max), **Auto** (clears the locked range immediately), and **Cancel**. Once a range is locked,
it stays in effect — across new parameter selections, time range reloads, and clearing the plot —
until you choose **Auto** again, for both the TUI and Matplotlib backends.

All times in must-tui are **UTC**: the time range fields, `now`/`today`, the presets, the plot's time
axis (both the TUI plot and the Matplotlib window) and the sample times, whatever your computer's
own timezone is.

Type a date-time as `YYYY-MM-DD HH:MM:SS`. Shorter forms are accepted too: `YYYY-MM-DD HH:MM`
(seconds 0) and `YYYY-MM-DD` (midnight). A field is applied when you press **Enter** or leave it
(e.g. with **Tab**); typing alone changes nothing. **Escape** leaves the field, committing a
pending valid edit first, the same as **Tab**.

Relative forms are also accepted, resolved against the current UTC time:

- `now`, `today`, `yesterday`, `tomorrow` — `today`/`yesterday`/`tomorrow` snap to UTC midnight;
  `now` keeps the current time, to the second.
- Any of those with a signed offset, e.g. `now-6h`, `tomorrow+1d`, `yesterday-3h`. The offset uses
  `w`eeks, `d`ays, `h`ours, `m`inutes and `s`econds, and they can be combined: `now-1d2h30m`.
- A bare offset such as `-2h30m` or `+1w` is relative to `now`. The sign is required (`6h` alone is
  rejected as ambiguous).
- `start` and `end` are the current time range's start and end (as they were before this edit), with
  or without an offset: `end-6h` in the start field gives the 6 hours up to the current end,
  `start+90m` in the end field the 90 minutes from the current start. An expression on the *other*
  end keeps that end where it is, even with **Lock** on; with Lock on, an expression on the field's
  own end (e.g. `start+1d` in the start field) moves the whole range, as any other edit would.

**↑ / ↓** step the date-time component the cursor is on (year, month, day, hour, minute, second) up
or down by one, directly in the field's text — without applying it, so pending edits are still only
applied on **Enter**/**Tab**/**Escape**. Stepping a relative expression first resolves it to an
absolute date-time, then steps it. Stepping the day/month clamps to the last valid day of the
resulting month (e.g. 31 Jan + 1 month → 28 Feb); stepping past year 1000 or 9999 does nothing.

If the text is not a valid date-time, or the start would not be before the end, the field turns red,
a notification explains why, and the time range stays as it was. Editing the field removes the red
mark.

When the time range changes, the x-axis moves to the new range and all plotted parameters are
fetched again for it. A notification shows when the reload starts and when it is done; parameters
without data in the new range are listed there and removed from the plot. Selecting a parameter
fetches and plots its data for the current time range.

### Plot

The lower-right area renders a time-series plot of the selected parameter(s).  Multiple
parameters can be overlaid — each new selection adds a trace without clearing previous ones.
The title lists every currently plotted parameter (`Parameter: X` for one, `Parameters: X, Y, …`
for several), each one colored to match its trace. The Matplotlib backend shows a real legend
instead; a legend in the TUI plot can crash the terminal plotting library in some situations, so
the title's coloring is used there instead.

To keep the terminal plot fast, each trace is drawn with at most 1000 points. Long series are
reduced by keeping the minimum and maximum of each time bucket, so spikes and dips remain
visible. The Matplotlib backend always shows the full-resolution data.

Fetching a parameter with many samples in the selected time range can take a while — data is
retrieved page by page (5000 samples per request, over one reused connection, to avoid one huge
request to the MUST server), and all of it is retrieved before anything is drawn. A spinner covers
the plot area while a selection or a time range change is being fetched, and the **Parameter
Metadata** panel's `plotted-samples` field shows the resulting point count once it's done. If a
single parameter's data in the selected range is extremely large (over 5,000,000 samples), a
notification reports that only the first part of it was loaded.

Use the **Clear Plot** button (or press `Ctrl+L`) to reset the plot.

The plot marker style can be cycled through four options (Braille, Standard Definition, High
Definition, Dot) with `F3`.

---

## Pan and Zoom in the Plot

Click the plot (or **Tab** to it) to give it focus; its keys then show in the footer:

| Key | Action |
|---|---|
| `←` / `→` | Move the time range back / forward by half its duration |
| `+` (or `=`) | Zoom in: half the duration, around the centre |
| `-` | Zoom out: double the duration, around the centre |
| `0` | Set the time range to the selected parameter's data range (its first to last sample) |
| `Ctrl+←` / `Ctrl+→` | Move the time range back / forward by a third of its duration |
| `Shift+←` / `Shift+→` | Move the time range back / forward by a quarter of its duration |
| `Ctrl+↑` / `Ctrl+↓` | Zoom in / out by a third: to 2/3 / 3/2 of the duration |
| `Shift+↑` / `Shift+↓` | Zoom in / out by a quarter: to 3/4 / 4/3 of the duration |

The smaller zoom steps use the arrow keys rather than `+`/`-`: terminals such as Ghostty use
`Ctrl` with `+`/`-` for their own font size, and `Shift` with `+`/`-` can't be told apart from a
plain `+` or `_` on most keyboard layouts. Zooming out by a step undoes zooming in by the same step.
The modifier keys are listed in the help (`F1`) but not in the footer, to keep it short.

The mouse wheel over the plot zooms too, in smaller steps (×1.25 per wheel event). Pan and zoom work in
whole seconds, down to a one-second range.

Each step moves the plot's time axis and the **Start → End** fields at once. About 0.3 s after the
last step, the new range is applied: the plotted parameters are fetched again for it, unless all of
their data for it was already loaded — zooming in, or panning/zooming back within the range fetched
before, then needs no fetch and just redraws the samples at full detail. Data that was cut short by
the sample limit is always fetched again. While pan/zoom fetches, the plot is not covered by the
loading spinner, so you can keep panning and zooming; a newer step cancels a fetch that is no longer
needed.

The plot draws a line between consecutive samples, also across a gap in the data, where it can look
like a slope that isn't in the data. Press `F7` to show the samples only. When zooming in without a
fetch, the nearest sample just outside the new range is kept, so a line crossing the edge is still
drawn. After a fetch, MUST returns only the samples inside the range, so such a line then starts at
the first sample inside it.

A pan/zoom session is remembered as one recent range (see **Range…**): the view you ended up with,
not every step on the way.

---

## Global Key Bindings

These bindings are available anywhere in the application. Every one of them is a `Ctrl`-combo or a
function key — none are bare letters, so none are ever swallowed by the search box as typed text,
regardless of where focus is:

| Key | Action |
|---|---|
| `F1` | Open this help |
| `Ctrl+Q` | Quit the application |
| `Ctrl+L` | Clear all traces from the plot |
| `Ctrl+Z` | Maximize the plot and its controls, hiding everything else; press again to restore |
| `Ctrl+J` | Toggle between **Filter** and **Jump** search mode |
| `F2` | Toggle plot backend between TUI (built-in) and Matplotlib |
| `F3` | Cycle plot marker style (Braille → SD → HD → Dot) |
| `F4` | Toggle light / dark mode |
| `F5` | Soft-refresh the parameter cache (fetches from server, keeps SQLite cache) |
| `Ctrl+R` | Hard-reset the parameter cache (wipes SQLite cache, then re-fetches) |
| `F6` | Choose a time range: presets, the selected parameter's data range, or a recently used range |
| `F7` | Toggle between lines connecting the samples and the samples only (points), in both plot backends |

Only the first four (`F1`, `Ctrl+Q`, `Ctrl+L`, `Ctrl+Z`) are shown in the footer, to keep it short;
the rest still work exactly the same, they're just not advertised there. The full table — generated
from the same bindings the app actually uses, so it can't go out of date — is always available by
pressing `F1`.

The status line above the footer shows the data provider, connection state, the number of
parameters currently loaded, and how long ago the parameter cache was last refreshed.

---

## Startup Screens

### Loading Screen

On startup the app shows a loading screen while it:

1. Authenticates with the MUST server.
2. Loads MIB parameter info from the bundled `pcf.dat`.
3. Fetches the parameter catalog.

If authentication fails the app offers the choice to **Abort** or continue in **offline mode**
(no server data, MIB browsing only).

### Main Screen

After loading, the main screen is shown with the parameter list.  The parameter catalog is
loaded from the local SQLite cache when available. A background refresh from the server runs at
startup only when the cache is missing or older than one day; press `F5` to refresh it at any time.

---

## Plot Backends

### TUI (default)

The built-in Textual plot renders directly in the terminal.  No graphical session is required.

### Matplotlib

Requires a graphical desktop session with a window manager.  When enabled, an external
Matplotlib window opens alongside the terminal and stays in sync with the time range and
parameter selections.  Switch back to the TUI backend with `F2` or the **Plot: TUI** button.
