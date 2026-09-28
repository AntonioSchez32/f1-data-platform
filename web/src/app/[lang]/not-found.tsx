import Link from "next/link";

/** 404 dentro del sitio (no recibe el idioma: se muestra en los dos). */
export default function NotFound() {
  return (
    <div className="grid max-w-[60ch] gap-4 border-t-4 border-red pt-4">
      <h1 className="text-3xl font-bold">No hemos encontrado esta página</h1>
      <p className="text-muted">Puede que el enlace esté mal o que ese dato no exista.</p>
      <p lang="en" className="text-muted">
        We couldn&apos;t find this page: the link may be wrong or that record may not exist.
      </p>
      <p className="flex gap-4">
        <Link href="/es">Volver al inicio</Link>
        <Link href="/en" lang="en" hrefLang="en">
          Back to home
        </Link>
      </p>
    </div>
  );
}
