# Design Refresh — CrateMind

**Date:** 2026-04-03  
**Status:** Approved

## Summary

Replace the current dark Plexamp-inspired theme with a light, modern, and inviting design. The new direction is called **Soft Modern**: rounded corners, soft shadows, layered whites, and a clear indigo accent.

## Design Decisions

| Dimension | Current | New |
|---|---|---|
| Theme | Dark (#1a1a1a) | Light only (#f7f5ff lavender-white) |
| Dark Mode | — | None (removed) |
| Accent | Amber (#e5a00d) | Indigo/Violet (#7c3aed) |
| Font | DM Sans | Plus Jakarta Sans |
| Border radius | 6px (sharp) | 12–16px (rounded) |
| Shadows | None | Soft layered (rgba indigo) |

## Color Palette

```css
--bg-app:        #f7f5ff;   /* lavender-white page background */
--bg-surface:    #ffffff;   /* cards, panels, inputs */
--bg-subtle:     #faf8ff;   /* input fills, hover states */

--accent:        #7c3aed;   /* primary indigo */
--accent-dark:   #6d28d9;   /* gradient end, hover */
--accent-light:  #ede9fe;   /* chip backgrounds, tag fills */
--accent-border: #c4b5fd;   /* input borders, dividers */
--accent-muted:  #8b5cf6;   /* secondary text, sub-labels */

--text-primary:  #1e1b4b;   /* headings, track titles */
--text-secondary:#4b5563;   /* body text, prompts */
--text-muted:    #9ca3af;   /* metadata, durations */
--text-label:    #8b5cf6;   /* section labels (uppercase) */

--border:        #ede9fe;   /* panel dividers */
--border-input:  #c4b5fd;   /* focused/active inputs */

--error:         #e11d48;
--success:       #059669;
--warning:       #d97706;
--heart-active:  #e11d48;   /* favorited tracks */
```

## Typography

**Font:** [Plus Jakarta Sans](https://fonts.google.com/specimen/Plus+Jakarta+Sans)  
**Weights used:** 400, 500, 600, 700, 800  
**Import:**
```html
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400&display=swap" rel="stylesheet">
```

| Role | Size | Weight |
|---|---|---|
| Logo | 18px | 800 |
| Section heading | 15px | 700 |
| Body / track title | 13px | 600–700 |
| Secondary / sub | 12px | 500 |
| Labels (uppercase) | 10px | 700 |
| Metadata | 11px | 400–500 |

## Component Patterns

### Surfaces & Layout
- Page background: `--bg-app` (#f7f5ff)
- Header: `--bg-surface` with 1px `--border` bottom, `box-shadow: 0 1px 4px rgba(109,40,217,0.06)`
- Panels / cards: `--bg-surface` with `box-shadow: 0 1px 4px rgba(109,40,217,0.07)`
- Border radius: `12px` for cards/inputs, `16px` for modals, `20px` for pills/chips

### Navigation
- Active nav item: filled pill, `background: #7c3aed; color: #fff`
- Inactive nav item: transparent, `color: #6b7280`, hover `background: #f3f4f6`

### Inputs & Prompt Box
- Border: `1.5px solid #c4b5fd`
- Background: `#faf8ff`
- Border radius: `12px`
- Focus: border `#7c3aed`, `box-shadow: 0 0 0 3px rgba(124,58,237,0.12)`

### Buttons
- **Primary (Generate):** `background: linear-gradient(90deg, #7c3aed, #6d28d9)`, white text, `box-shadow: 0 3px 10px rgba(109,40,217,0.28)`, border-radius `8–10px`
- **Secondary (Save, etc.):** `background: #ede9fe; color: #7c3aed`, no shadow
- **Destructive:** `color: #e11d48`, background transparent or `#fff1f2`

### Filter Chips
- Active: `background: #ede9fe; color: #7c3aed; border: 1.5px solid #c4b5fd`
- Inactive: `background: #f9fafb; color: #9ca3af; border: 1.5px solid #e5e7eb`
- Border radius: `20px`

### Track Cards
- Background: `#fff`, border-radius `12px`
- Shadow: `0 1px 4px rgba(109,40,217,0.07)`
- Hover shadow: `0 4px 16px rgba(109,40,217,0.13)`
- Track number: `#d1d5db`, 11px
- Album art: `38×38px`, border-radius `8px`
- Heart icon: `#c4b5fd` (inactive) / `#e11d48` (active)

### Curator Narrative Card
- Background: `linear-gradient(135deg, #ede9fe, #f0fdf4)`
- Border: `1px solid #c4b5fd`
- Title label: indigo uppercase, 11px 700

### Section Labels
- 10px, 700 weight, `color: #8b5cf6`, `text-transform: uppercase`, `letter-spacing: 1px`

## Layout

The two-panel layout (filter sidebar left, track list right) is unchanged. Only visual styling changes.

- App max-width: 960px (unchanged)
- Left panel: 300px, `background: #fff`, right border `1px solid #ede9fe`
- Right panel: flex 1, `background: #f7f5ff`, padding 24px

## What Does NOT Change

- HTML structure and component hierarchy
- JavaScript logic
- Layout / panel widths
- Responsive breakpoints
- All functional behavior (filters, generation, saving playlists, library view, settings)

## Implementation Scope

1. Replace all CSS custom properties in `:root` with new palette
2. Update font import in `index.html` (DM Sans → Plus Jakarta Sans)
3. Update `--font-family` variable
4. Restyle components to match new patterns (border-radius, shadows, button styles, chips)
5. Remove any dark-mode-specific rules
6. Update focus ring to use new accent color
