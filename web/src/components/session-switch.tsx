import Link from "next/link";

/** Selector de sesión (carrera/sprint) como enlaces: funciona sin JavaScript. */
export function SessionSwitch({
  label,
  options,
  current,
}: {
  label: string;
  options: { value: string; label: string; href: string }[];
  current: string;
}) {
  return (
    <nav aria-label={label} className="flex gap-2">
      {options.map((option) => (
        <Link
          key={option.value}
          href={option.href}
          aria-current={option.value === current ? "page" : undefined}
          className={`rounded-full border px-3 py-1 text-sm font-semibold no-underline ${
            option.value === current
              ? "border-ink bg-ink text-surface"
              : "border-line bg-surface text-muted hover:text-ink"
          }`}
        >
          {option.label}
        </Link>
      ))}
    </nav>
  );
}
