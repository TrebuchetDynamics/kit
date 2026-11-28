# Dembrandt design references

Select only the topics needed for the requested outcome. Links written as
`[[topic]]` inside an upstream reference resolve to the corresponding entry
below, not to a host skill or another command.

## Brand & Visual Identity

- [brand-visual-language](../upstream/skills/brand-visual-language/PROTOCOL.md) — Shape language, icon style, typography tone
- [color-mode-and-theme](../upstream/skills/color-mode-and-theme/PROTOCOL.md) — Light vs dark vs combined, when to offer a theme selector
- [marketing-vs-product-system](../upstream/skills/marketing-vs-product-system/PROTOCOL.md) — What a marketing site and the product may differ on, and what is drift
- [algorithmic-color-palette](../upstream/skills/algorithmic-color-palette/PROTOCOL.md) — Derive states and brand-tinted greys from brand colours

## Design Tokens & Scales

- [modular-scale-typography](../upstream/skills/modular-scale-typography/PROTOCOL.md) — Ratio-based type scales, minimum sizes, context-aware usage
- [elevation-and-depth](../upstream/skills/elevation-and-depth/PROTOCOL.md) — Shadow scale, border-radius, card and modal patterns
- [surface-separation](../upstream/skills/surface-separation/PROTOCOL.md) — One separation strategy per surface; opacity as state, not tint
- [button-states](../upstream/skills/button-states/PROTOCOL.md) — Six states: rest, hover, active, focus, disabled, loading
- [component-family-consistency](../upstream/skills/component-family-consistency/PROTOCOL.md) — Buttons, inputs, pills: shared radius, colour, height
- [sizing-units](../upstream/skills/sizing-units/PROTOCOL.md) — px vs rem vs relative: which values move when the user enlarges text

## Layout & Structure

- [layout-paradigms-and-consistency](../upstream/skills/layout-paradigms-and-consistency/PROTOCOL.md) — Choose the layout paradigm that fits the content; reuse the page skeleton across screens
- [gestalt-ui-organisation](../upstream/skills/gestalt-ui-organisation/PROTOCOL.md) — Group related controls: proximity, similarity, common region
- [visual-emphasis-and-hierarchy](../upstream/skills/visual-emphasis-and-hierarchy/PROTOCOL.md) — One CTA per view, colour and size as emphasis
- [information-architecture](../upstream/skills/information-architecture/PROTOCOL.md) — Naming, mental models, data UI, confirm dialogs
- [ui-context-and-scope](../upstream/skills/ui-context-and-scope/PROTOCOL.md) — Hierarchy, breadcrumbs, colour regions, scope communication
- [responsive-paradigms](../upstream/skills/responsive-paradigms/PROTOCOL.md) — Mobile/tablet/desktop: nav, sections, sticky behaviour
- [ui-density](../upstream/skills/ui-density/PROTOCOL.md) — Match density to platform and user type
- [sticky-and-fixed-elements](../upstream/skills/sticky-and-fixed-elements/PROTOCOL.md) — Headers, bottom toolbars, z-index tokens
- [scroll-areas](../upstream/skills/scroll-areas/PROTOCOL.md) — Avoid inner scroll, one axis only, user-controlled

## Components & Interaction

- [real-world-metaphors](../upstream/skills/real-world-metaphors/PROTOCOL.md) — Cards, carousels, drawers: when to use and how
- [form-design](../upstream/skills/form-design/PROTOCOL.md) — Helper text, placeholder, validation, submit state
- [tab-navigation](../upstream/skills/tab-navigation/PROTOCOL.md) — Tab types, overflow handling, roving tabindex, ARIA tablist, URL state
- [modal-and-overlay-patterns](../upstream/skills/modal-and-overlay-patterns/PROTOCOL.md) — Overlay hierarchy, focus trap, dismiss rules, destructive confirms
- [data-display-and-selection](../upstream/skills/data-display-and-selection/PROTOCOL.md) — Grid/list/table, large hit areas, mass actions
- [repeated-component-alignment](../upstream/skills/repeated-component-alignment/PROTOCOL.md) — Repeated components as slot models: equal size, pinned anchors, clamp + recover text
- [operational-expert-tool-ui](../upstream/skills/operational-expert-tool-ui/PROTOCOL.md) — Dense, workflow-driven UIs for trained daily B2B users
- [coordinated-data-views](../upstream/skills/coordinated-data-views/PROTOCOL.md) — Keep a table and a visual view (map, diagram, chart) in sync
- [domain-expert-configuration](../upstream/skills/domain-expert-configuration/PROTOCOL.md) — Expose solver/algorithm settings in domain language
- [app-shell](../upstream/skills/app-shell/PROTOCOL.md) — Top bar, sidebar rail, app launcher, tenant and environment cue, status bar: one shell across an estate
- [global-toolbar-controls](../upstream/skills/global-toolbar-controls/PROTOCOL.md) — Currency, language, region and unit selectors: frequent but not primary
- [notifications-and-recovery](../upstream/skills/notifications-and-recovery/PROTOCOL.md) — Toasts, banners, retry, undo: always a path forward
- [status-colors-and-errors](../upstream/skills/status-colors-and-errors/PROTOCOL.md) — Minimal semantic colours, error recovery, prevention

## UX Principles

- [nielsen-usability-heuristics](../upstream/skills/nielsen-usability-heuristics/PROTOCOL.md) — 10 usability principles with review checklists
- [wcag-accessibility](../upstream/skills/wcag-accessibility/PROTOCOL.md) — WCAG 2.2 AA / EN 301 549: contrast, keyboard, ARIA
- [user-flows-and-guided-paths](../upstream/skills/user-flows-and-guided-paths/PROTOCOL.md) — Wizards, purchase flows, onboarding sequences
- [authentic-product-representation](../upstream/skills/authentic-product-representation/PROTOCOL.md) — Real content and real output over staged mockups and marketing chrome
- [micro-interactions](../upstream/skills/micro-interactions/PROTOCOL.md) — Animated icons, toggles, reveals, celebrations
- [loading-states-and-perceived-performance](../upstream/skills/loading-states-and-perceived-performance/PROTOCOL.md) — Spinners, skeleton screens, and staggered entry animations
- [motion-and-storytelling](../upstream/skills/motion-and-storytelling/PROTOCOL.md) — Disney principles and cinematic language in UI

## Technical Foundation

- [semantic-html-and-seo](../upstream/skills/semantic-html-and-seo/PROTOCOL.md) — HTML5, alt texts, Open Graph, progressive enhancement
- [performance-and-web-vitals](../upstream/skills/performance-and-web-vitals/PROTOCOL.md) — Lighthouse audit, LCP, CLS, INP, images, fonts, JS loading

## Pipeline & Orchestration

- [extract-design](../upstream/skills/extract-design/PROTOCOL.md) — Read the token output schema; live extraction uses the separate Kit runtime path.
- [clone-website](../upstream/skills/clone-website/PROTOCOL.md) — Compare a reconstruction with an authorized reference; use the measurement guidance only.
- [generate-ui-from-brand](../upstream/skills/generate-ui-from-brand/PROTOCOL.md) — Turn supplied tokens or DESIGN.md into a UI spec.
- [dembrandt](../upstream/skills/dembrandt/PROTOCOL.md) — Six-stage design review checklist; not a router or a command.
