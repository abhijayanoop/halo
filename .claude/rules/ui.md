---
paths:
  - "ui/**/*.{ts,tsx}"
---
# UI rules
- Event types come from ui/src/types (generated). Never edit them; run npm run gen:types.
- All state lives in the zustand store, produced by the event reducer. Components are pure.
- Animation: Framer Motion. Mascot shapes: plain SVG paths from ui/src/character/draw.ts (no Rough.js, nothing random). No other animation libraries.
- Styling: Tailwind only.
- After any visual change, screenshot it with Playwright at /moods or with ?mock= and compare.
