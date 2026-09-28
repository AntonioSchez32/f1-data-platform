import Link from "next/link";

import { LanguageSwitch, NavLinks } from "@/components/nav-links";
import type { Dictionary, Locale } from "@/lib/i18n";

export function SiteHeader({ locale, t }: { locale: Locale; t: Dictionary }) {
  const nav = t.site.nav;
  const links = [
    { href: `/${locale}/seasons`, label: nav.seasons },
    { href: `/${locale}/drivers`, label: nav.drivers },
    { href: `/${locale}/constructors`, label: nav.constructors },
    { href: `/${locale}/records`, label: nav.records },
    { href: `/${locale}/quality`, label: nav.quality },
  ];
  return (
    <header className="border-b border-line bg-surface">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-8 gap-y-3 px-4 py-3 sm:px-6">
        <Link
          href={`/${locale}`}
          className="flex items-baseline gap-2 font-display text-xl font-bold no-underline"
        >
          <span aria-hidden="true" className="inline-block h-3 w-6 -skew-x-12 bg-red" />
          {t.site.name}
        </Link>
        <nav aria-label={nav.label} className="order-last w-full sm:order-none sm:w-auto sm:flex-1">
          <NavLinks links={links} />
        </nav>
        <div className="ml-auto sm:ml-0">
          <LanguageSwitch locale={locale} label={t.site.language} otherLabel={t.site.otherLanguage} />
        </div>
      </div>
    </header>
  );
}
