# UI Design Rules

## Theme
Use a premium dark creator-workstation style.

## Visual direction
- Dark-first interface.
- Dense but readable workstation layout.
- Premium editorial feel, not casual consumer-app chrome.
- Modular panels and tool surfaces should feel intentional, not floating randomly.
- Use restrained glow and glass only to reinforce hierarchy.

## Color rules
- Base the app on deep neutral backgrounds with cool-toned surfaces.
- Use one main accent system for primary actions and selection states.
- Reserve stronger saturation for important actions such as Generate, Export, or active focus.
- Keep warnings and destructive states clear, but avoid neon red/orange overload.
- Avoid rainbow accents and avoid default purple-heavy gradients.

## Typography rules
- Prioritize clarity under dense workflows.
- Use clear hierarchy for section labels, panel titles, controls, and supporting text.
- Hero text is acceptable only for major step headings, not inside tool panels.
- Favor strong section headers with restrained body copy.

## Spacing rules
- Keep workstation panels compact enough for serious use, but do not crowd controls.
- Prefer consistent interior spacing inside cards, toolbars, and side rails.
- Dense screens should still maintain visual breathing room between functional regions.

## Shape rules
- Rounded surfaces are acceptable, but keep them disciplined.
- Use medium-to-large radius selectively for major cards and media containers.
- Borders should remain subtle and cool.
- Shadows should support depth, not dominate the composition.

## Component rules
- Treat the app as a creator workstation with modular control surfaces.
- Group controls by workflow: inputs, generation actions, review surfaces, output surfaces.
- Primary actions must read immediately.
- Secondary actions should stay visible without competing.
- Cards should justify grouping or separation, not become the default for every row.

## Interaction rules
- Selection, active generation, and blocking states must be immediately legible.
- Progress UI must expose the active phase, not only a spinner.
- Hover states should be subtle and modern.
- Focus states must be visible and accessible.

## Screen-specific guidance

### Sidebar
- Sidebar should feel like a navigation rail for a workstation, not a marketing landing page.
- Active step state should be obvious with restrained emphasis.
- Use compact labels and calm section framing.

### Workspace panels
- Prefer multi-column workstation layouts on desktop when the task benefits from side-by-side review and controls.
- Let media previews dominate where appropriate, especially extraction and export screens.
- Keep utility controls close to the content they affect.

### Toolbar and action rows
- High-value actions should be easy to scan.
- Secondary actions can use quieter outline or ghost treatments.
- Avoid long rows of equally loud buttons.

### Render / export surfaces
- Export screens should feel heavier and more output-oriented than lightweight edit panes.
- Progress cards, logs, result preview, and fallback actions should read as one coordinated system.
- Preview surfaces should feel cinematic but still production-focused.

### Dialogs
- Use dialogs sparingly.
- Keep them scoped to one decision or one focused task.
- Avoid stuffing workstation-level editing flows into modals.

## Tokens
- Prefer token-based styling when adding or adjusting theme values.
- Keep surface, border, text, accent, status, and radius tokens aligned with the premium dark workstation direction.

## Avoid
- generic SaaS white-label layouts
- overly soft, playful editor styling
- flat single-surface screens with no hierarchy
- uncontrolled glow, blur, or glass everywhere
- giant empty spacing that wastes workstation real estate
- multiple competing accent colors
- decorative gradients that reduce readability
