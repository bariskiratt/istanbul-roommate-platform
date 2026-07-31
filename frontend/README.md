# RoomMatch — frontend

React + TypeScript + Vite + Tailwind + shadcn/ui client for the RoomMatch
roommate platform. See the [root README](../README.md) for the full picture.

```bash
npm install
cp .env.example .env   # VITE_API_URL, defaults to http://127.0.0.1:8000
npm run dev            # http://localhost:8080
npm test               # vitest
npm run build          # production build (used by Vercel)
```

Design system: Hinge-inspired editorial theme — warm neutrals, ink/cream
primary actions, deep plum accent, Fraunces serif for headings. All colors are
CSS custom properties in `src/index.css` (`:root` light, `.dark` dark), so the
whole app can be re-themed from one file.
