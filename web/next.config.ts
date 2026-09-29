import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV === "development";

/**
 * Política de seguridad de contenido estática. Todo se sirve desde el propio dominio (las fuentes
 * las aloja next/font y los datos se piden a la API desde el servidor). 'unsafe-inline' hace falta
 * para los scripts en línea con los que Next hidrata las páginas y para los estilos que ECharts
 * pone en el SVG; en desarrollo React necesita además 'unsafe-eval'. Las vistas previas usan la
 * misma política que producción: la barra de comentarios de Vercel (vercel.live) necesitaría
 * abrir varias directivas, así que se desactiva en el proyecto (Settings → General → Vercel
 * Toolbar).
 */
const contentSecurityPolicy = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self'",
  "connect-src 'self'",
  "frame-src 'none'",
  "frame-ancestors 'none'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: contentSecurityPolicy },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), browsing-topics=()" },
];

const nextConfig: NextConfig = {
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
