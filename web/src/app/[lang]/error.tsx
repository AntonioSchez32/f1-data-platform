"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";

const TEXT = {
  es: {
    title: "No se han podido cargar los datos",
    body: "El servicio de datos no responde ahora mismo. Inténtalo de nuevo en unos minutos.",
    retry: "Reintentar",
  },
  en: {
    title: "The data couldn't be loaded",
    body: "The data service isn't responding right now. Please try again in a few minutes.",
    retry: "Try again",
  },
};

export default function Error({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  const lang = usePathname().startsWith("/en") ? "en" : "es";
  const t = TEXT[lang];
  useEffect(() => {
    console.error(error);
  }, [error]);
  return (
    <div role="alert" className="grid max-w-[60ch] gap-3 border-t-4 border-red pt-4">
      <h1 className="text-3xl font-bold">{t.title}</h1>
      <p className="text-muted">{t.body}</p>
      <button type="button" onClick={() => retry()} className="w-fit rounded-md bg-ink px-4 py-2 font-semibold text-surface">
        {t.retry}
      </button>
    </div>
  );
}
