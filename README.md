# pbi-grid

A declarative layout engine for Power BI reports in PBIR format.

Define report layouts in YAML using a 12-column grid and generate a complete `.Report` folder automatically. Visual positions are computed from row heights and column spans — no manual coordinate editing.

```yaml
package: govbr

report:
  name: MyReport
  source: ./MyReport.Report   # existing report — preserves bindings and filters

canvas:
  width: 1280
  height: 720

shared:
  components:
    page_header:
      span: 12
      component: header
      title: "My Report"
      subtitle: "Organization Name"

pages:
  - id: home_page_id
    display_name: Home
    rows:
      - id: header
        height: 64
        cols:
          - ref: page_header
      - id: content
        height: 656
        cols:
          - span: 12
            visual: textbox
```

---

## Requirements

- Python 3.11+
- [PyYAML](https://pypi.org/project/PyYAML/)

---

## Setup

```bash
git clone <repo-url>
cd pbi-grid
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows
pip install -e .
```

---

## Usage

### Generate a report

```bash
pbi-grid generate --layout path/to/layout.yaml --output output/MyReport
```

Produces a `.Report` folder. When `report.source` is set, visual data (bindings, formatting, filters) is preserved from the source report — only positions change.

### Extract a layout from an existing report

```bash
pbi-grid extract --report path/to/MyReport.Report --output path/to/layout.yaml
```

Reads an existing `.Report` folder and generates a layout YAML. Each visual is identified by its 20-char PBIR name. Use as the starting point for managing a report with pbi-grid.

### Merge extract — preserve existing page configs

```bash
pbi-grid extract --report path/to/MyReport.Report --merge path/to/layout.yaml
```

Re-extracts without overwriting pages already present in the YAML. Useful when adding new pages to an existing report.

### Debug grid overlay

```bash
pbi-grid generate --layout path/to/layout.yaml --output output/MyReport --debug
```

Renders a visual debug layer on every page: each grid cell gets a semi-transparent blue rectangle and an orange label showing component name and span (e.g. `header 12c`, `menu 2c×3r`). Use to validate layout boundaries before connecting real data.

![debug overlay](docs/debug-overlay.png)

---

## Typical workflow

1. Extract a starting layout from an existing report:
   ```bash
   pbi-grid extract --report MyReport.Report --output layout.yaml
   ```
2. Edit `layout.yaml` — set spans, row heights, components, and `ref:` links.
3. Validate visually with `--debug`.
4. Generate the final report:
   ```bash
   pbi-grid generate --layout layout.yaml --output output/MyReport
   ```

---

## Layout YAML reference

### Top-level keys

```yaml
package: govbr           # Theme package: default | govbr (optional)

report:
  name: MyReport         # Output .Report folder name (default: layout filename stem)
  source: ./MyReport.Report  # Source report for visual data preservation (optional)

canvas:
  width: 1280            # Canvas width in Power BI units (default: 1280)
  height: 720            # Canvas height (default: 720)
  gutter: 0              # Gap between grid cells in units (default: 0)

shared:
  components:            # Named reusable column definitions — referenced via ref:
    my_component:
      span: 2
      component: menu
      ...

pages:
  - id: <pbir-page-id>   # 20-char hex PBIR page ID (drives the output folder name)
    display_name: Home   # Label shown in the Power BI page tabs
    rows: [...]
```

**Page IDs** must be stable 20-char hex strings. Use the existing PBIR folder name (from `extract`) or any deterministic hex string for new pages.

### Rows and columns

```yaml
rows:
  - id: content
    height: 120          # Row height in canvas units
    cols:
      - span: 4          # Column span (1–12)
        visual: barChart # Power BI visual type — creates a bare visual
      - span: 4
        name: a1b2c3d4e5f6a7b8c9d0  # PBIR visual identity — repositions an existing visual
      - span: 4
        component: menu  # pbi-grid built-in component
        rowspan: 3       # Extend across N rows vertically (default: 1)
      - ref: nav_menu    # Expand a shared component definition inline
        rowspan: 2       # Local overrides take precedence over the shared definition
```

**`name` vs `visual`**

| Field | When to use |
|-------|-------------|
| `name` | Reposition an existing visual from the source report. The engine places that visual at the computed cell. |
| `visual` | Create a new bare visual of the given Power BI type. |

### Column span → width (1280 canvas)

| `span` | Width (units) |
|--------|--------------|
| 1 | 106.67 |
| 2 | 213.33 |
| 3 | 320.00 |
| 4 | 426.67 |
| 6 | 640.00 |
| 8 | 853.33 |
| 10 | 1066.67 |
| 12 | 1280.00 |

### Shared components and `ref:`

Define a column once and reuse it across pages. Local keys alongside `ref:` override the shared definition.

```yaml
shared:
  components:
    nav_menu:
      span: 2
      component: menu
      orientation: vertical
      items:
        - page: Home
        - page: Details

pages:
  - id: page1_id
    display_name: Home
    rows:
      - id: content
        height: 480
        cols:
          - ref: nav_menu
            rowspan: 2       # local override — nav_menu definition has no default rowspan
          - span: 10
            visual: barChart
      - id: table
        height: 240
        cols:
          - span: 10
            visual: tableEx
      - id: footer
        height: 200
        cols:
          - ref: page_footer  # full width — placed outside the nav_menu rowspan
```

---

## Components

### `header`

Full-width header bar: background rectangle, title, optional subtitle, and an optional accent stripe at the bottom.

```yaml
- span: 12
  component: header
  title: "My Report"
  subtitle: "Organization Name"   # optional
```

| Visual | Type | Description |
|--------|------|-------------|
| background | `shape` | Colored rectangle (`header.background_color`) |
| title | `actionButton` | Main title text |
| subtitle | `actionButton` | Secondary label (only when `subtitle:` is set) |
| accent bar | `shape` | Bottom stripe (`header.accent_color`, `header.accent_height`) |

---

### `menu`

Navigation menu where each item is an `actionButton` that navigates to the target page.

**Menu height is content-driven**, not rowspan-driven: the background rectangle sizes to the number of items × `menu.item_height` (token). The `rowspan` controls grid space reservation, not the visual height.

**Flat menu:**

```yaml
- span: 2
  component: menu
  orientation: vertical
  items:
    - page: Home
      description: "Landing page"
    - page: Details
      description: "Detailed breakdown"
```

**Two-level menu (group headers + child items):**

Items with a nested `items:` list render as non-clickable section headers; children render as indented navigation buttons.

```yaml
- span: 2
  component: menu
  orientation: vertical
  items:
    - page: Overview
      description: "Summary"
    - page: By Theme
      items:
        - page: Topic A
          description: "Topic A data"
        - page: Topic B
          description: "Topic B data"
```

---

### `footer`

Full-width footer bar: background, optional top divider stripe, optional logo, site-map link columns, and a legal text bar at the bottom.

> **Layout tip:** place the footer row **outside** the `nav_menu` rowspan so it spans all 12 columns. Set `rowspan` as a local override on the content row, not in the shared component definition.

```yaml
- span: 12
  component: footer
  logo_path: "govbr.png"    # filename relative to the theme dir (optional)
  logo_height: 40           # px — overrides tokens footer.logo_height (optional)
  legal: "License and usage terms."
  links:
    - title: "CATEGORY"
      items:
        - label: "Link label"
          url: "https://example.com"
        - label: "Another link"
          url: "https://example.com"
    - title: "CATEGORY"
      items:
        - label: "Link label"
          url: "https://example.com"
```

**Logo** (`logo_path`) references a PNG in the active theme directory (`themes/{package}/`). The file is automatically copied to `StaticResources/RegisteredResources/` and registered in `report.json`. Omit `logo_path` to render the footer without a logo.

**Footer layout (top to bottom):**

```
┌── top divider stripe (divider_height px) ────────────────┐
│ logo (logo_width × logo_height)                           │
├── link columns (full width, remaining height) ────────────┤
│ CATEGORY      CATEGORY      CATEGORY                      │
│  link          link          link                         │
│  ...           ...           ...                          │
├── 1px separator ──────────────────────────────────────────┤
│ Legal text                         (legal_height px)      │
└───────────────────────────────────────────────────────────┘
```

**Minimum footer height** = `divider_height + logo_height + (items + 1) × item_height + 1 + legal_height`

| Visual | Type | Description |
|--------|------|-------------|
| background | `shape` | Full-width rectangle (`footer.background_color`) |
| top divider | `shape` | Accent stripe (`footer.divider_color`) |
| logo | `image` | PNG from theme dir (`RegisteredResources`) |
| column title × N | `actionButton` | Category header, bold, no action |
| link × M | `actionButton` | Site-map link, opens web URL |
| separator | `shape` | 1px line above legal bar |
| legal text | `actionButton` | License/terms text, no action |

---

## Themes

Themes control component colors and assets. Select one with `package:` in the layout YAML.

```yaml
package: govbr
```

| Theme | Description |
|-------|-------------|
| `default` | Neutral — no brand identity. Gray tones throughout. |
| `govbr` | Brazilian federal government — [Padrão Digital de Governo](https://www.gov.br/ds/home). Navy/white/blue palette. |

**govbr preview:**

![govbr theme preview](themes/govbr/preview.PNG)

Each theme lives under `themes/{name}/` and provides:
- `tokens.yaml` — design tokens (colors, sizes, font sizes per component)
- `layouts/` — ready-to-use layout YAML templates

### Tokens (`tokens.yaml`)

Tokens are the source of truth for all component colors and dimensions. Component props in the layout YAML (e.g. `logo_height`, `logo_path`) override the corresponding token value when set.

```yaml
header:
  background_color: "#FFFFFF"
  title_color: "#071D41"
  title_font_size: 14        # pt
  subtitle_color: "#1351B4"
  subtitle_font_size: 10
  accent_color: "#1351B4"
  accent_height: 2           # px

footer:
  background_color: "#071D41"
  divider_color: "#FFFFFF"
  divider_height: 4          # px
  logo_path: "govbr.png"     # filename relative to theme dir
  logo_width: 165            # px
  logo_height: 60            # px
  title_color: "#FFFFFF"
  title_font_size: 10
  link_color: "#C9D4E3"
  link_font_size: 9
  item_height: 24            # px per row (title + each link)
  legal_color: "#A8B5C3"
  legal_font_size: 9
  legal_height: 44           # px

menu:
  item_height: 48            # px per item
  header:
    font_color: "#071D41"
  item:
    font_color_default: "#1351B4"
    font_color_selected: "#FFFFFF"
    fill_color_default: "#F8F8F8"
    fill_color_selected: "#0C326F"
    outline_color: "#1351B4"
```

---

## Project structure

```
pbi-grid/
├── src/
│   ├── models/            # PBIR domain models (Visual, Page, Report)
│   ├── grid/
│   │   ├── schema.py      # YAML parser → LayoutSpec
│   │   ├── engine.py      # LayoutSpec → Report model
│   │   ├── extractor.py   # .Report folder → layout YAML
│   │   └── renderer.py    # Report model → PBIR files on disk
│   ├── components/
│   │   ├── header.py      # HeaderComponent
│   │   ├── menu.py        # MenuComponent
│   │   └── footer.py      # FooterComponent
│   ├── packages.py        # Theme loader (tokens + assets)
│   └── cli.py             # CLI entry point
├── themes/
│   ├── default/
│   └── govbr/
├── examples/
│   └── sample_theme_govbr/
└── pyproject.toml
```

---

## License

MIT