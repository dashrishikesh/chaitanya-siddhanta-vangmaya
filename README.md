# चैतन्य सिद्धान्त वाङ्मय

An Astro-powered digital repository for Chaitanya Siddhanta texts, styled after
a classical grantha-archive UI: sticky Devanagari nav, categorized book-strip
listings with a grid/tree view toggle, and a clean sans-serif reading layout.

## Project structure

```text
/
├── public/                       static assets (favicon)
├── src/
│   ├── components/
│   │   ├── Header.astro          sticky nav + wordmark
│   │   └── Footer.astro
│   ├── layouts/
│   │   └── Layout.astro          shared <head>, fonts, header/footer shell
│   ├── pages/
│   │   ├── index.astro           मुख्यपृष्ठम् (home)
│   │   ├── ग्रन्थाः/index.astro   texts listing — placeholder categories/entries
│   │   ├── अन्वेषणम्/index.astro  search (UI only, not wired to an index)
│   │   └── साहाय्यम्/index.astro  help / FAQ
│   └── styles/
│       └── global.css            palette, typography, layout
└── astro.config.mjs              site + base for GitHub Pages
```

The texts listing (`src/pages/ग्रन्थाः/index.astro`) currently ships with
**placeholder categories and dummy entries** (`ग्रन्थनाम १`, `लेखकस्य नाम`, `href="#"`)
— replace the `groups` array with your real corpus and links.

## Commands

| Command           | Action                                       |
| :----------------- | :-------------------------------------------- |
| `npm install`       | Install dependencies                          |
| `npm run dev`       | Start local dev server at `localhost:4321`    |
| `npm run build`     | Build production site to `./dist/`            |
| `npm run preview`   | Preview the production build locally          |

## Deployment (GitHub Pages)

`.github/workflows/deploy.yml` builds and deploys on every push to `main`
using `withastro/action`. One-time setup on GitHub:

1. Repo **Settings → Pages → Source** → set to **GitHub Actions**.
2. Push to `main` — the workflow builds and publishes automatically.

`astro.config.mjs` is set for `dashrishikesh/chaitanya-siddhanta-vangmaya`:

```js
site: 'https://dashrishikesh.github.io',
base: '/chaitanya-siddhanta-vangmaya',
```

If the repo is renamed, update `base` to match.
