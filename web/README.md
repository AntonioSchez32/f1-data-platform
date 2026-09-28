# Web de F1 Data Platform

Web pública (Next.js 16, React 19, Tailwind 4, ECharts) sobre la API de `../api`.
La guía de uso, las páginas y el criterio de accesibilidad están en el
[README principal](../README.md#web-nextjs).

```bash
npm ci
npm run dev          # http://localhost:3000, con la API en F1_API_URL (por defecto :8000)
npx playwright test  # pruebas de extremo a extremo y de accesibilidad
```
