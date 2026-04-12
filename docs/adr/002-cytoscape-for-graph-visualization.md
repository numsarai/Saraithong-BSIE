# ADR-002: Cytoscape.js for Graph Visualization

**Status:** Accepted  
**Date:** 2026-04-11  
**Author:** ร้อยตำรวจเอกณัฐวุฒิ สาหร่ายทอง

## Context
BSIE needs interactive network graphs to visualize money flows between accounts. The visualization must support: drag nodes, zoom, pan, multiple layout algorithms, and dynamic data loading.

## Decision
Use **Cytoscape.js** for all graph visualization (Link Chart, Account Flow Graph).

## Rationale
- **Graph-specialized** — designed specifically for network graphs (vs D3 which is general-purpose)
- **Built-in interaction** — drag, zoom, pan, selection without custom code
- **Multiple layouts** — cose, breadthfirst, concentric, circle, preset built-in
- **No external dependencies** — pure JavaScript, no Java/Flash required
- **React compatible** — works with React refs, lifecycle management
- **Lightweight** — ~400KB minified vs D3 ~280KB but D3 requires far more custom code

## Consequences
- Node styling is limited to CSS-like properties (no arbitrary SVG per node)
- No built-in animation timeline (would need custom implementation)
- Large graphs (>1000 nodes) may need virtualization

## Alternatives Considered
- **D3.js** — more flexible but requires writing drag/zoom/layout from scratch
- **vis.js** — similar to Cytoscape but less maintained
- **Sigma.js** — WebGL-based, better for very large graphs but harder API
