# ApexFlow — Marketing site

Next.js 15 marketing page for ApexFlow. The product UI (chat, panels, sessions)
lives in the Python/Gradio app at the repo root; this is the public-facing
artifact suitable for the README, GitHub Pages, or Vercel.

## Stack

- **Next.js 15** (App Router) + **React 19** + **TypeScript**
- **next/font** for typography (Fraunces, Instrument Sans, JetBrains Mono)
- Plain CSS (no framework) — design tokens in `app/globals.css`
- Zero third-party UI deps

## Local development

```bash
cd web
npm install
npm run dev          # http://localhost:3000
```

## Deploy to Vercel

```bash
cd web
npx vercel           # follow prompts; pick "web" as the root
```

The whole site is static-friendly — Vercel's free Hobby tier is more than
enough.

## Customising

- **Brand & copy**: edit `lib/agents.ts`, `lib/features.ts`, and the static
  copy inside the section components.
- **Accent colour**: change `--accent` and `--accent-2` in `app/globals.css`
  (currently luminous violet `#B19CFF` / deep amethyst `#7C3AED`).
- **Logo**: drop a PNG/SVG into `public/` and swap the `.brand .mark` letter
  for an `<Image>` in `components/Nav.tsx` and `components/Footer.tsx`.
- **GitHub / contact links**: search the components for `https://github.com`
  and `mailto:` and replace.

## File map

```
app/
  layout.tsx           ← root layout, font wiring, metadata
  globals.css          ← all design tokens + bespoke styles
  page.tsx             ← marketing page composition
components/
  Nav.tsx              ← sticky top bar
  Hero.tsx             ← headline + live status card
  Marquee.tsx          ← scrolling tech-stack strip
  Architecture.tsx     ← orchestrator + 8-agent grid (data-driven)
  Features.tsx         ← 6 capability cards (data-driven)
  Demo.tsx             ← chat-shell mock with multi-agent trace
  Numbers.tsx          ← at-a-glance stats
  Author.tsx           ← bio + pull quote + CTA
  Footer.tsx           ← footer
  RevealManager.tsx    ← client component, IntersectionObserver scroll-reveal
  Icon.tsx             ← inline SVG icon set for agent cards
lib/
  agents.ts            ← the 8 specialist agents
  features.ts          ← the 6 capability blocks
```
