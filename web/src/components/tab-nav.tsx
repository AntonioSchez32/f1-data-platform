"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/** Pestañas como enlaces (cada sección es una URL propia); la actual lleva aria-current. */
export function TabNav({ label, tabs }: { label: string; tabs: { href: string; label: string }[] }) {
  const pathname = usePathname();
  return (
    <nav aria-label={label} className="mb-8 overflow-x-auto overflow-y-hidden border-b border-line">
      <ul className="flex min-w-max gap-1">
        {tabs.map(({ href, label: text }) => {
          const current = pathname === href;
          return (
            <li key={href}>
              <Link
                href={href}
                aria-current={current ? "page" : undefined}
                className={`-mb-px inline-block border-b-2 px-3 py-2 text-sm font-semibold no-underline ${
                  current ? "border-red text-ink" : "border-transparent text-muted hover:text-ink"
                }`}
              >
                {text}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
