---
paths:
  - "ui/**/*.{ts,tsx}"
---
# UI rules
- Event types come from ui/src/types (generated). Never edit them; run npm run gen:types.
- All state lives in the zustand store, produced by the event reducer. Components are pure.
- Animation: Framer Motion. Mascot shapes: Rough.js. No other animation libraries.
- Styling: Tailwind only.
- After any visual change, screenshot it with Playwright at /moods or with ?mock= and compare.
