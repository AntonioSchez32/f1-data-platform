import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans, Titillium_Web } from "next/font/google";

import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { getDictionary } from "@/lib/i18n";

import "../globals.css";

const display = Titillium_Web({
  subsets: ["latin"],
  weight: ["600", "700"],
  variable: "--font-titillium",
  display: "swap",
});
const sans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-sans",
  display: "swap",
});
const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-plex-mono",
  display: "swap",
});

export const revalidate = 3600;

export async function generateMetadata({ params }: LayoutProps<"/[lang]">): Promise<Metadata> {
  const { t } = await getDictionary((await params).lang);
  return {
    title: { default: t.site.title, template: `%s · ${t.site.name}` },
    description: t.site.description,
  };
}

export default async function RootLayout({ children, params }: LayoutProps<"/[lang]">) {
  const { locale, t } = await getDictionary((await params).lang);
  return (
    <html lang={locale} className={`${display.variable} ${sans.variable} ${mono.variable}`}>
      <body className="flex min-h-dvh flex-col antialiased">
        <a
          href="#contenido"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-surface focus:px-4 focus:py-2 focus:font-semibold"
        >
          {t.site.skip}
        </a>
        <SiteHeader locale={locale} t={t} />
        <main id="contenido" tabIndex={-1} className="mx-auto w-full max-w-6xl flex-1 px-4 pb-16 pt-8 sm:px-6">
          {children}
        </main>
        <SiteFooter locale={locale} t={t} />
      </body>
    </html>
  );
}
