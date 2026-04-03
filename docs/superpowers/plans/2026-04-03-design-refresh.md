# Design Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dark Plexamp-inspired theme with a light Soft Modern design (lavender-white background, indigo accent, Plus Jakarta Sans font).

**Architecture:** Pure CSS + one HTML line change. All component logic, layout, and JavaScript remain unchanged. Most colors are driven by CSS custom properties in `:root`, so updating those variables propagates everywhere. A second pass fixes ~30 hardcoded dark hex values scattered in modal overlays, the library view, and a few one-off rules.

**Tech Stack:** Vanilla CSS custom properties, Google Fonts (Plus Jakarta Sans)

---

## File Map

| File | Change |
|---|---|
| `frontend/index.html` | Swap DM Sans → Plus Jakarta Sans font import (1 line) |
| `frontend/style.css` | Replace `:root` variables + fix hardcoded dark values + enhance components |

---

### Task 1: Update font import in index.html

**Files:**
- Modify: `frontend/index.html:8` (the DM Sans `<link>` tag)

- [ ] **Step 1: Replace the font link tag**

In `frontend/index.html`, find:
```html
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,100..1000;1,9..40,100..1000&display=swap" rel="stylesheet">
```
Replace with:
```html
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400&display=swap" rel="stylesheet">
```

- [ ] **Step 2: Verify**

Open `http://localhost:5765` in a browser. The font should change immediately — Plus Jakarta Sans is slightly rounder and friendlier than DM Sans.

- [ ] **Step 3: Commit**

```bash
git add frontend/index.html
git commit -m "style: swap DM Sans for Plus Jakarta Sans"
```

---

### Task 2: Replace :root CSS variables

The `:root` block is at lines 1–54 of `frontend/style.css`. Replacing it cascades the new palette across ~95% of all rules.

**Files:**
- Modify: `frontend/style.css:1-54`

- [ ] **Step 1: Replace the entire :root block**

Find (lines 1–54, the full existing `:root` block):
```css
/* MediaSage Styles - Plexamp Aesthetic */

:root {
    /* Colors - Plexamp Dark Theme */
    --bg-primary: #1a1a1a;
    --bg-secondary: #242424;
    --bg-tertiary: #2d2d2d;
    --bg-elevated: #2d2d2d;
    --bg-hover: #363636;
    --accent: #e5a00d;
    --accent-hover: #f0b020;
    --text-primary: #ffffff;
    --text-secondary: #a0a0a0;
    --text-muted: #9a9a9a;
    --border: #3a3a3a;
    --error: #e95c59;
    --success: #43a047;
    --error-toast: #c62828;
    --success-toast: #2e7032;
    --warning: #fb8c00;

    /* Spacing */
    --spacing-xs: 4px;
    --spacing-sm: 8px;
    --spacing-md: 16px;
    --spacing-lg: 24px;
    --spacing-xl: 32px;

    /* Border Radius */
    --radius: 6px;
    --radius-sm: 4px;
    --radius-md: 8px;
    --radius-lg: 12px;
    --radius-full: 9999px;

    /* Typography - DM Sans per Plex brand guidelines */
    --font-family: "DM Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    --font-size-sm: 0.875rem;
    --font-size-base: 1rem;
    --font-size-lg: 1.25rem;
    --font-size-xl: 1.5rem;
    --font-size-2xl: 2rem;
    --font-size-3xl: 2.25rem;
    --text-body: #E0E0E0;

    /* Transitions */
    --transition-fast: 150ms ease;
    --transition-normal: 250ms ease;

    /* Results layout */
    --results-footer-height: 40px;
    --detail-panel-width: 300px;
    --detail-panel-width-narrow: 240px;
}
```

Replace with:
```css
/* CrateMind Styles - Soft Modern Light Theme */

:root {
    /* Colors - Soft Modern Light */
    --bg-primary: #f7f5ff;      /* lavender-white page background */
    --bg-secondary: #ffffff;     /* cards, panels, inputs */
    --bg-tertiary: #f0eeff;      /* subtle hover backgrounds */
    --bg-elevated: #ffffff;      /* elevated surfaces */
    --bg-hover: #e8e3ff;         /* hover state */
    --bg-app: #f7f5ff;
    --bg-surface: #ffffff;
    --bg-subtle: #faf8ff;

    --accent: #7c3aed;
    --accent-hover: #6d28d9;
    --accent-dark: #6d28d9;
    --accent-light: #ede9fe;
    --accent-border: #c4b5fd;
    --accent-muted: #8b5cf6;

    --text-primary: #1e1b4b;
    --text-secondary: #4b5563;
    --text-muted: #9ca3af;
    --text-label: #8b5cf6;
    --text-body: #374151;

    --border: #ede9fe;
    --border-input: #c4b5fd;

    --error: #e11d48;
    --success: #059669;
    --error-toast: #be123c;
    --success-toast: #047857;
    --warning: #d97706;
    --heart-active: #e11d48;

    /* Spacing */
    --spacing-xs: 4px;
    --spacing-sm: 8px;
    --spacing-md: 16px;
    --spacing-lg: 24px;
    --spacing-xl: 32px;

    /* Border Radius - rounder for Soft Modern */
    --radius: 8px;
    --radius-sm: 6px;
    --radius-md: 12px;
    --radius-lg: 16px;
    --radius-full: 9999px;

    /* Typography - Plus Jakarta Sans */
    --font-family: "Plus Jakarta Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    --font-size-sm: 0.875rem;
    --font-size-base: 1rem;
    --font-size-lg: 1.25rem;
    --font-size-xl: 1.5rem;
    --font-size-2xl: 2rem;
    --font-size-3xl: 2.25rem;

    /* Transitions */
    --transition-fast: 150ms ease;
    --transition-normal: 250ms ease;

    /* Results layout */
    --results-footer-height: 40px;
    --detail-panel-width: 300px;
    --detail-panel-width-narrow: 240px;
}
```

- [ ] **Step 2: Verify**

Reload the browser. The page should now be lavender-white with indigo accents. Typography is Plus Jakarta Sans. Most elements will look correct immediately.

- [ ] **Step 3: Commit**

```bash
git add frontend/style.css
git commit -m "style: replace :root palette with Soft Modern indigo light theme"
```

---

### Task 3: Fix hardcoded dark colors in modal overlays

Several full-screen overlays use hardcoded `rgba(26, 26, 26, ...)` or `rgba(0, 0, 0, ...)` backgrounds that won't be fixed by the variable swap. Find and replace each one.

**Files:**
- Modify: `frontend/style.css` (scattered rules, ~6 locations)

- [ ] **Step 1: Fix loading overlay background**

Find:
```css
.loading-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(26, 26, 26, 0.95);
```
Replace `background: rgba(26, 26, 26, 0.95);` with:
```css
    background: rgba(247, 245, 255, 0.92);
```

- [ ] **Step 2: Fix success modal overlay**

Find:
```css
.success-modal {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(26, 26, 26, 0.95);
```
Replace `background: rgba(26, 26, 26, 0.95);` with:
```css
    background: rgba(247, 245, 255, 0.92);
```

- [ ] **Step 3: Fix sync modal overlay**

Find:
```css
.sync-modal {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(26, 26, 26, 0.98);
```
Replace `background: rgba(26, 26, 26, 0.98);` with:
```css
    background: rgba(247, 245, 255, 0.95);
```

- [ ] **Step 4: Fix step-loading overlay**

Find:
```css
.step-loading-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(26, 26, 26, 0.95);
```
Replace `background: rgba(26, 26, 26, 0.95);` with:
```css
    background: rgba(247, 245, 255, 0.92);
```

- [ ] **Step 5: Fix modal-overlay**

Find:
```css
.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(26, 26, 26, 0.95);
```
Replace `background: rgba(26, 26, 26, 0.95);` with:
```css
    background: rgba(247, 245, 255, 0.92);
```

- [ ] **Step 6: Fix file browser overlay**

Find:
```css
.file-browser-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.7);
```
Replace `background: rgba(0, 0, 0, 0.7);` with:
```css
    background: rgba(30, 27, 75, 0.4);
```

- [ ] **Step 7: Fix results-header-left border**

Find:
```css
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
```
Replace with:
```css
    border-bottom: 1px solid var(--border);
```

- [ ] **Step 8: Fix narrative text color**

Find:
```css
.narrative-text {
    color: rgba(255, 255, 255, 0.5);
```
Replace with:
```css
.narrative-text {
    color: var(--text-secondary);
```

- [ ] **Step 9: Fix file browser selected entry**

Find:
```css
.file-browser-entry.selected { background: rgba(229, 160, 13, 0.15); }
```
Replace with:
```css
.file-browser-entry.selected { background: rgba(124, 58, 237, 0.1); }
```

- [ ] **Step 10: Fix album art shadow**

Find:
```css
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
```
Replace with:
```css
    box-shadow: 0 8px 32px rgba(109, 40, 217, 0.15);
```

- [ ] **Step 11: Fix save-mode-dropdown shadow**

Find:
```css
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
```
Replace with:
```css
    box-shadow: 0 4px 12px rgba(109, 40, 217, 0.15);
```

- [ ] **Step 12: Fix nav dropdown menu shadow**

Find:
```css
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
```
Replace with:
```css
    box-shadow: 0 8px 24px rgba(109, 40, 217, 0.12);
```

- [ ] **Step 13: Verify**

Check in browser: open loading state, success modal, file browser. All should show a soft lavender-tinted overlay instead of near-black.

- [ ] **Step 14: Commit**

```bash
git add frontend/style.css
git commit -m "style: fix hardcoded dark overlay and shadow colors"
```

---

### Task 4: Fix hardcoded colors in experimental warning and library view

The `.experimental-warning` block and the entire Library View section (~lines 3813–4039) have hardcoded dark hex values that bypass CSS variables.

**Files:**
- Modify: `frontend/style.css` (experimental-warning block + library view section)

- [ ] **Step 1: Fix experimental-warning block**

Find:
```css
.experimental-warning {
    background: #3d2a00;
    border: 1px solid #fb8c00;
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 16px;
    font-size: 0.875rem;
    line-height: 1.4;
}

.experimental-warning strong {
    color: #fb8c00;
    display: block;
    margin-bottom: 4px;
}

.experimental-warning p {
    color: #a0a0a0;
    margin: 0;
}

.experimental-warning a,
.experimental-warning a:link,
.experimental-warning a:visited {
    color: #e5a00d !important;
    text-decoration: underline !important;
    text-decoration-color: #e5a00d !important;
    text-underline-offset: 2px;
}

.experimental-warning a:hover,
.experimental-warning a:active {
    color: #f0b020 !important;
    text-decoration-color: #f0b020 !important;
}
```

Replace with:
```css
.experimental-warning {
    background: #fffbeb;
    border: 1px solid var(--warning);
    border-radius: var(--radius-md);
    padding: 12px 16px;
    margin-bottom: 16px;
    font-size: 0.875rem;
    line-height: 1.4;
}

.experimental-warning strong {
    color: var(--warning);
    display: block;
    margin-bottom: 4px;
}

.experimental-warning p {
    color: var(--text-secondary);
    margin: 0;
}

.experimental-warning a,
.experimental-warning a:link,
.experimental-warning a:visited {
    color: var(--accent) !important;
    text-decoration: underline !important;
    text-decoration-color: var(--accent) !important;
    text-underline-offset: 2px;
}

.experimental-warning a:hover,
.experimental-warning a:active {
    color: var(--accent-hover) !important;
    text-decoration-color: var(--accent-hover) !important;
}
```

- [ ] **Step 2: Fix library tabs**

Find:
```css
.library-tabs {
  display: flex;
  gap: 2px;
  background: #111;
  padding: 3px;
  border-radius: 8px;
  width: fit-content;
  margin-bottom: 16px;
}

.library-tab {
  background: transparent;
  border: none;
  color: #888;
  padding: 6px 18px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.library-tab.active {
  background: #e5a00d;
  color: #000;
  font-weight: 600;
}
```

Replace with:
```css
.library-tabs {
  display: flex;
  gap: 2px;
  background: var(--bg-tertiary);
  padding: 3px;
  border-radius: var(--radius-md);
  width: fit-content;
  margin-bottom: 16px;
}

.library-tab {
  background: transparent;
  border: none;
  color: var(--text-muted);
  padding: 6px 18px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  cursor: pointer;
  font-family: var(--font-family);
  transition: background 0.15s, color 0.15s;
}

.library-tab.active {
  background: var(--accent);
  color: #fff;
  font-weight: 600;
}
```

- [ ] **Step 3: Fix library controls and search**

Find:
```css
.library-search-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: #555;
  pointer-events: none;
}

.library-search {
  width: 100%;
  background: #111;
  border: 1px solid #333;
  border-radius: 6px;
  padding: 7px 10px 7px 32px;
  font-size: 13px;
  color: #ddd;
  box-sizing: border-box;
}

.library-search:focus {
  outline: none;
  border-color: #555;
}
```

Replace with:
```css
.library-search-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  pointer-events: none;
}

.library-search {
  width: 100%;
  background: var(--bg-surface);
  border: 1.5px solid var(--accent-border);
  border-radius: var(--radius-sm);
  padding: 7px 10px 7px 32px;
  font-size: 13px;
  color: var(--text-primary);
  font-family: var(--font-family);
  box-sizing: border-box;
}

.library-search:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.12);
}
```

- [ ] **Step 4: Fix library toggle**

Find:
```css
.lib-toggle-track {
  width: 30px;
  height: 17px;
  background: #333;
  border-radius: 9px;
  position: relative;
  transition: background 0.2s;
  flex-shrink: 0;
}

.lib-toggle-track::after {
  content: '';
  position: absolute;
  width: 13px;
  height: 13px;
  background: #666;
  border-radius: 50%;
  top: 2px;
  left: 2px;
  transition: transform 0.2s, background 0.2s;
}

.lib-toggle-input:checked + .lib-toggle-track {
  background: #2a1f00;
  border: 1px solid #e5a00d;
}

.lib-toggle-input:checked + .lib-toggle-track::after {
  transform: translateX(13px);
  background: #e5a00d;
}

.lib-toggle-text {
  font-size: 12px;
  color: #888;
}
```

Replace with:
```css
.lib-toggle-track {
  width: 30px;
  height: 17px;
  background: var(--bg-hover);
  border-radius: 9px;
  position: relative;
  transition: background 0.2s;
  flex-shrink: 0;
}

.lib-toggle-track::after {
  content: '';
  position: absolute;
  width: 13px;
  height: 13px;
  background: var(--text-muted);
  border-radius: 50%;
  top: 2px;
  left: 2px;
  transition: transform 0.2s, background 0.2s;
}

.lib-toggle-input:checked + .lib-toggle-track {
  background: var(--accent-light);
  border: 1px solid var(--accent);
}

.lib-toggle-input:checked + .lib-toggle-track::after {
  transform: translateX(13px);
  background: var(--accent);
}

.lib-toggle-text {
  font-size: 12px;
  color: var(--text-muted);
}
```

- [ ] **Step 5: Fix lib-loading**

Find:
```css
.lib-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #666;
  font-size: 13px;
  padding: 24px 0;
}
```

Replace with:
```css
.lib-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-muted);
  font-size: 13px;
  padding: 24px 0;
}
```

- [ ] **Step 6: Fix lib-card**

Find:
```css
.lib-card {
  display: flex;
  align-items: center;
  gap: 12px;
  background: #1a1a1a;
  border: 1px solid #2a2a2a;
  border-radius: 7px;
  padding: 9px 13px;
  transition: border-color 0.15s;
}

.lib-card.is-favorite {
  border-color: #e5a00d;
  background: #1e1e1e;
}
```

Replace with:
```css
.lib-card {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 9px 13px;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.lib-card:hover {
  box-shadow: 0 2px 8px rgba(109, 40, 217, 0.08);
}

.lib-card.is-favorite {
  border-color: var(--accent-border);
  background: var(--accent-light);
}
```

- [ ] **Step 7: Fix lib-heart**

Find:
```css
.lib-heart {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 20px;
  line-height: 1;
  color: #444;
  padding: 0;
  flex-shrink: 0;
  transition: color 0.15s, transform 0.1s;
}

.lib-heart:hover {
  transform: scale(1.15);
}

.lib-card.is-favorite .lib-heart {
  color: #e5a00d;
}
```

Replace with:
```css
.lib-heart {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 20px;
  line-height: 1;
  color: var(--accent-border);
  padding: 0;
  flex-shrink: 0;
  transition: color 0.15s, transform 0.1s;
}

.lib-heart:hover {
  transform: scale(1.15);
  color: var(--heart-active);
}

.lib-card.is-favorite .lib-heart {
  color: var(--heart-active);
}
```

- [ ] **Step 8: Fix lib-card text**

Find:
```css
.lib-card-title {
  color: #ddd;
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.lib-card.is-favorite .lib-card-title {
  color: #fff;
}
```

Replace with:
```css
.lib-card-title {
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.lib-card.is-favorite .lib-card-title {
  color: var(--accent);
}
```

- [ ] **Step 9: Fix lib-card-subtitle, badge, track count, footer**

Find:
```css
.lib-card-subtitle {
  color: #555;
  font-size: 11px;
  margin-top: 1px;
}

.lib-badge-new {
  background: #1a3a1a;
  color: #4caf50;
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 3px;
  margin-left: 6px;
  vertical-align: middle;
  letter-spacing: 0.03em;
}

.lib-track-count {
  color: #555;
  font-size: 12px;
  flex-shrink: 0;
  margin-left: auto;
}

.lib-footer {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: #555;
  padding-top: 8px;
  border-top: 1px solid #222;
}

.lib-fav-count {
  color: #e5a00d;
}
```

Replace with:
```css
.lib-card-subtitle {
  color: var(--text-muted);
  font-size: 11px;
  margin-top: 1px;
}

.lib-badge-new {
  background: #dcfce7;
  color: #059669;
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 3px;
  margin-left: 6px;
  vertical-align: middle;
  letter-spacing: 0.03em;
}

.lib-track-count {
  color: var(--text-muted);
  font-size: 12px;
  flex-shrink: 0;
  margin-left: auto;
}

.lib-footer {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-muted);
  padding-top: 8px;
  border-top: 1px solid var(--border);
}

.lib-fav-count {
  color: var(--accent);
}
```

- [ ] **Step 10: Verify**

Open the Library view in the browser. Cards should be white with indigo borders, the heart icon should be indigo, favorites highlighted correctly.

- [ ] **Step 11: Commit**

```bash
git add frontend/style.css
git commit -m "style: fix hardcoded dark colors in experimental warning and library view"
```

---

### Task 5: Enhance component styles

Add shadows, gradient button, input focus ring, nav pill styles, header shadow, and scrollbar styling per the spec.

**Files:**
- Modify: `frontend/style.css` (multiple sections)

- [ ] **Step 1: Add header shadow**

Find:
```css
.header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--spacing-md) 0;
    border-bottom: 1px solid var(--border);
    margin-bottom: var(--spacing-lg);
}
```

Replace with:
```css
.header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--spacing-md) 0;
    border-bottom: 1px solid var(--border);
    margin-bottom: var(--spacing-lg);
    box-shadow: 0 1px 4px rgba(109, 40, 217, 0.06);
}
```

- [ ] **Step 2: Update nav button active/inactive style**

Find:
```css
.nav-btn.active {
    color: var(--accent);
    background: var(--bg-secondary);
}
```

Replace with:
```css
.nav-btn.active {
    color: #fff;
    background: var(--accent);
    border-radius: var(--radius-full);
}
```

- [ ] **Step 3: Gradient primary button**

Find:
```css
.btn-primary {
    background: var(--accent);
    color: var(--bg-primary);
}

.btn-primary:hover {
    background: var(--accent-hover);
}
```

Replace with:
```css
.btn-primary {
    background: linear-gradient(90deg, var(--accent), var(--accent-dark));
    color: #fff;
    box-shadow: 0 3px 10px rgba(109, 40, 217, 0.28);
}

.btn-primary:hover {
    background: linear-gradient(90deg, var(--accent-dark), #5b21b6);
    box-shadow: 0 4px 14px rgba(109, 40, 217, 0.36);
}
```

- [ ] **Step 4: Update input focus ring**

Find:
```css
input[type="text"]:focus,
input[type="password"]:focus,
textarea:focus,
select:focus {
    outline: 2px solid var(--accent);
    outline-offset: -1px;
    border-color: var(--accent);
}
```

Replace with:
```css
input[type="text"]:focus,
input[type="password"]:focus,
textarea:focus,
select:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.12);
}
```

- [ ] **Step 5: Update input base style**

Find:
```css
input[type="text"],
input[type="password"],
textarea,
select {
    width: 100%;
    padding: var(--spacing-sm) var(--spacing-md);
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    color: var(--text-primary);
    font-size: var(--font-size-base);
    font-family: var(--font-family);
    transition: border-color var(--transition-fast);
}
```

Replace with:
```css
input[type="text"],
input[type="password"],
textarea,
select {
    width: 100%;
    padding: var(--spacing-sm) var(--spacing-md);
    background: var(--bg-subtle);
    border: 1.5px solid var(--accent-border);
    border-radius: var(--radius-md);
    color: var(--text-primary);
    font-size: var(--font-size-base);
    font-family: var(--font-family);
    transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
```

- [ ] **Step 6: Update select dropdown arrow color**

Find:
```css
    background-image: url("data:image/svg+xml,%3Csvg width='12' height='8' viewBox='0 0 12 8' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M1 1.5L6 6.5L11 1.5' stroke='%23a0a0a0' stroke-width='1.5' stroke-linecap='round' fill='none'/%3E%3C/svg%3E");
```

Replace with:
```css
    background-image: url("data:image/svg+xml,%3Csvg width='12' height='8' viewBox='0 0 12 8' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M1 1.5L6 6.5L11 1.5' stroke='%238b5cf6' stroke-width='1.5' stroke-linecap='round' fill='none'/%3E%3C/svg%3E");
```

- [ ] **Step 7: Add playlist track card shadow**

Find:
```css
.playlist-track {
    display: flex;
    align-items: center;
    gap: var(--spacing-md);
    padding: var(--spacing-sm);
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: background var(--transition-fast), border-left var(--transition-fast);
    border-left: 3px solid transparent;
}

.playlist-track:hover {
    background: var(--bg-tertiary);
}
```

Replace with:
```css
.playlist-track {
    display: flex;
    align-items: center;
    gap: var(--spacing-md);
    padding: var(--spacing-sm);
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: background var(--transition-fast), border-left var(--transition-fast), box-shadow var(--transition-fast);
    border-left: 3px solid transparent;
    box-shadow: 0 1px 4px rgba(109, 40, 217, 0.07);
}

.playlist-track:hover {
    background: var(--bg-tertiary);
    box-shadow: 0 4px 16px rgba(109, 40, 217, 0.13);
}
```

- [ ] **Step 8: Update chip selected state**

Find:
```css
.chip.selected {
    background: var(--accent);
    color: var(--bg-primary);
}
```

Replace with:
```css
.chip.selected {
    background: var(--accent-light);
    color: var(--accent);
    border-color: var(--accent-border);
    border-width: 1.5px;
}
```

- [ ] **Step 9: Update option-pill selected state (recommendation view)**

Find:
```css
.option-pill.selected {
    background: var(--accent);
    color: var(--bg-primary);
    border-color: var(--accent);
    font-weight: 600;
}
```

Replace with:
```css
.option-pill.selected {
    background: var(--accent-light);
    color: var(--accent);
    border-color: var(--accent-border);
    font-weight: 600;
}
```

- [ ] **Step 10: Update scrollbar to light theme**

Find:
```css
::-webkit-scrollbar-track {
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
}

::-webkit-scrollbar-thumb {
    background: var(--bg-hover);
    border-radius: var(--radius-md);
}

::-webkit-scrollbar-thumb:hover {
    background: var(--text-muted);
}
```

Replace with:
```css
::-webkit-scrollbar-track {
    background: var(--bg-tertiary);
    border-radius: var(--radius-md);
}

::-webkit-scrollbar-thumb {
    background: var(--accent-border);
    border-radius: var(--radius-md);
}

::-webkit-scrollbar-thumb:hover {
    background: var(--accent-muted);
}
```

- [ ] **Step 11: Verify**

Reload the app. Check:
- Primary buttons have indigo gradient with shadow
- Inputs have lavender border and indigo focus ring
- Track cards have subtle shadow and lift on hover
- Active chips show indigo-light fill
- Scrollbars are indigo-tinted

- [ ] **Step 12: Commit**

```bash
git add frontend/style.css
git commit -m "style: add shadows, gradient button, input focus ring, pill nav, and scrollbar"
```

---

### Task 6: Final pass — remaining hardcoded dark values

A few isolated hardcoded values remain.

**Files:**
- Modify: `frontend/style.css`

- [ ] **Step 1: Fix success-icon border (was dark bg color)**

Find:
```css
.success-icon::after {
    content: '';
    width: 20px;
    height: 32px;
    border: 4px solid var(--bg-primary);
    border-top: none;
    border-left: none;
    transform: rotate(45deg) translateY(-4px);
}
```

Replace with:
```css
.success-icon::after {
    content: '';
    width: 20px;
    height: 32px;
    border: 4px solid #fff;
    border-top: none;
    border-left: none;
    transform: rotate(45deg) translateY(-4px);
}
```

- [ ] **Step 2: Fix setup-warning-fix background**

Find:
```css
.setup-warning-fix {
    font-family: monospace;
    background: var(--bg-tertiary);
    padding: var(--spacing-xs) var(--spacing-sm);
    border-radius: var(--radius-sm);
    word-break: break-all;
}
```

This already uses `var(--bg-tertiary)` so it will pick up the new color. No change needed — skip.

- [ ] **Step 3: Fix rec-mode-btn active state (was using --bg-primary which was dark)**

Find:
```css
.rec-mode-btn.active {
    background: var(--accent);
    color: var(--bg-primary);
    font-weight: 600;
}
```

Replace with:
```css
.rec-mode-btn.active {
    background: var(--accent);
    color: #fff;
    font-weight: 600;
}
```

- [ ] **Step 4: Fix step circle active/completed text color**

Find:
```css
.step.active .step-circle {
    background: var(--accent);
    color: var(--bg-primary);
    border-color: var(--accent);
}

.step.completed .step-circle {
    background: var(--accent);
    color: var(--bg-primary);
    border-color: var(--accent);
    font-size: 0;
}
```

Replace with:
```css
.step.active .step-circle {
    background: var(--accent);
    color: #fff;
    border-color: var(--accent);
}

.step.completed .step-circle {
    background: var(--accent);
    color: #fff;
    border-color: var(--accent);
    font-size: 0;
}
```

- [ ] **Step 5: Fix filter chip selected state (recommendation view)**

Find:
```css
.filter-chip.selected {
    background: var(--accent);
    color: var(--bg-primary);
    font-weight: 600;
}
```

Replace with:
```css
.filter-chip.selected {
    background: var(--accent-light);
    color: var(--accent);
    border: 1.5px solid var(--accent-border);
    font-weight: 600;
}
```

- [ ] **Step 6: Fix btn-primary disabled state**

Find:
```css
.btn-primary:disabled {
    background: var(--text-muted);
    cursor: not-allowed;
}
```

Replace with:
```css
.btn-primary:disabled {
    background: var(--bg-hover);
    color: var(--text-muted);
    box-shadow: none;
    cursor: not-allowed;
}
```

- [ ] **Step 7: Final full visual verification**

Navigate through all views and check:
1. Home / welcome screen — light background, indigo accents
2. Playlist generation wizard — all steps, filter chips, track list
3. Results view — track cards with shadow, sidebar panel
4. Album recommendation view — step progress, questions, results
5. Library view — tabs, search, cards, hearts, toggles
6. Settings view — form inputs, status indicators
7. Setup wizard — step cards, status indicators
8. Modals — loading overlay, success modal, file browser (all light-tinted)

- [ ] **Step 8: Commit**

```bash
git add frontend/style.css
git commit -m "style: final pass — fix remaining hardcoded dark colors across all views"
```
