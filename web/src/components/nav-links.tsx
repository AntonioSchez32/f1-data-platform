"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function NavLinks({ links }: { links: { href: string; label: string }[] }) {
  const pathname = usePathname();
  return (
    <ul className="-mx-1 flex gap-x-5 gap-y-1 overflow-x-auto whitespace-nowrap px-1 text-sm font-medium sm:flex-wrap">
      {links.map(({ href, label }) => {
        const current = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <li key={href}>
            <Link
              href={href}
              aria-current={current ? "page" : undefined}
              className={`inline-block border-b-2 py-1 no-underline hover:border-line ${
                current ? "border-red text-ink" : "border-transparent text-muted hover:text-ink"
              }`}
            >
              {label}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

export function LanguageSwitch({
  locale,
  label,
  otherLabel,
}: {
  locale: string;
  label: string;
  otherLabel: string;
}) {
  const pathname = usePathname();
  const other = locale === "es" ? "en" : "es";
  const target = pathname.replace(new RegExp(`^/${locale}(?=/|$)`), `/${other}`);
  return (
    <Link
      href={target}
      hrefLang={other}
      lang={other}
      aria-label={`${label}: ${otherLabel}`}
      className="rounded border border-line px-2 py-1 text-sm no-underline hover:bg-surface-2"
    >
      {otherLabel}
    </Link>
  );
}
