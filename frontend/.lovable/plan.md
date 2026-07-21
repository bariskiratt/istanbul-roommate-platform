

## Plan: RoomMatch Logo Click → Ana Sayfa

The RoomMatch logo and name in the top-left navbar needs to be wrapped in a link that navigates to `/` (homepage).

### Change

**File: `src/pages/Index.tsx`** — Find the navbar section where the RoomMatch logo (Home icon + "RoomMatch" text) is rendered. Wrap it in a `<Link to="/">` or use `onClick={() => navigate("/")}` so clicking it navigates to the homepage root `/`.

Additionally, check `src/components/layout/AppHeader.tsx` — the same RoomMatch branding block there should also link to `/` when clicked, ensuring consistency across all pages that use `AppHeader`.

Both changes are minimal: wrap the existing logo+text `div` in a React Router `Link` component with `to="/"` and add `cursor-pointer` styling.

