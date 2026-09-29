import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV === "development";
// La barra de comentarios de Vercel solo aparece en los despliegues de vista previa.
const vercelPreview = process.env.VERCEL_ENV === "preview" ? " https://vercel.live" : "";

/**
 * Política de seguridad de contenido estática. Todo se sirve desde el propio dominio (las fuentes
 * las aloja next/font y los datos se piden a la API desde el servidor). 'unsafe-inline' hace falta
 * para los scripts en línea con los que Next hidrata las páginas y para los estilos que ECharts
 * pone en el SVG; en desarrollo React necesita además 'unsafe-eval'.
 */
const contentSecurityPolicy = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}${vercelPreview}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self'",
  `connect-src 'self'${vercelPreview}`,
  `frame-src ${vercelPreview ? vercelPreview.trim() : "'none'"}`,
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
