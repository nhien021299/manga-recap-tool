# UI Design Rules

## Theme
Use the "Midnight Studio" visual style.

## Visual direction
- Dark-first interface.
- Editorial and creator-tool feel.
- Calm, focused, premium.
- Minimal visual noise.
- Functional beauty over decorative flair.

## Color rules
- Use dark neutral backgrounds and slightly lighter surfaces.
- Use one primary accent color only.
- Use accent colors sparingly for actions, focus, and selected states.
- Avoid rainbow UIs or multiple competing accent colors.
- Keep destructive and warning colors muted, not neon.

## Typography rules
- Prioritize readability over personality.
- Use clear hierarchy with 3-4 text levels maximum.
- Avoid oversized hero text in tool screens.
- Use medium weight for important labels, regular for body text.

## Spacing rules
- Use generous spacing.
- Prefer consistent spacing scales.
- Avoid cramped toolbars and crowded sidebars.

## Shape rules
- Use medium radius, not overly round.
- Keep borders subtle.
- Use soft shadows sparingly.
- Prefer layering through contrast, not heavy effects.

## Component rules
- Panels, sidebars, and toolbars should feel modular.
- Keep actions grouped logically.
- Primary actions should stand out clearly.
- Secondary actions should be visually quiet.
- Use cards only when they improve grouping, not everywhere.

## Interaction rules
- Selected regions must be obvious.
- Hover states should be subtle.
- Drag handles must remain visible and usable.
- Focus states must be clear and accessible.

## Screen-specific guidance

### Sidebar
- Use a surface one step lighter than the app background.
- Keep borders light and cool.
- Use small section titles with restrained uppercase styling.
- Show selected items with muted accent emphasis, not neon fills.

### Toolbar
- Keep density compact but breathable.
- Prefer ghost or subtle icon buttons for secondary tools.
- Use a solid accent treatment for the primary action such as Extract.

### Canvas / Image viewport
- Keep the viewport darker than the sidebar so images remain the focal layer.
- Let images remain visually dominant.
- Make overlay box borders crisp with very light fills.
- Keep selection states obvious without high-glare color.

### Modal / Dialog
- Use dialogs only when truly needed.
- Keep padding generous.
- Make the primary CTA clear.
- Avoid overloading a single dialog with too much content.

### Lists / Scene suggestions
- Prefer line-based or row-based grouping before defaulting to cards.
- Make selected rows very clear.
- Avoid card-heavy layouts that compete with the image workspace.

## Tokens
- Use token-based styling only.
- Approved tokens:
  - `--background`
  - `--surface`
  - `--surface-2`
  - `--border`
  - `--text-primary`
  - `--text-secondary`
  - `--accent`
  - `--accent-foreground`
  - `--success`
  - `--warning`
  - `--danger`
  - `--radius-sm`
  - `--radius-md`
  - `--radius-lg`

## Avoid
- glossy gradients everywhere
- glassmorphism-heavy layouts
- overly playful illustrations
- loud color contrast in editor screens
- giant empty hero sections inside tool pages
- gradient purple-blue everywhere
- heavy shadows
- very large radius across the whole app
- multiple accent colors on the same screen
- display fonts that make tool UI harder to read
