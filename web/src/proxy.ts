import { NextResponse, type NextRequest } from "next/server";

const LOCALES = ["es", "en"];
const DEFAULT_LOCALE = "es";

/** Idioma preferido según Accept-Language (primer idioma soportado por orden de calidad). */
function preferredLocale(request: NextRequest): string {
  const header = request.headers.get("accept-language") ?? "";
  const ranked = header
    .split(",")
    .map((part) => {
      const [tag, q] = part.trim().split(";q=");
      return { lang: tag.toLowerCase().split("-")[0], q: q ? Number(q) : 1 };
    })
    .sort((a, b) => b.q - a.q);
  return ranked.find(({ lang }) => LOCALES.includes(lang))?.lang ?? DEFAULT_LOCALE;
}

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasLocale = LOCALES.some((l) => pathname === `/${l}` || pathname.startsWith(`/${l}/`));
  if (hasLocale) return;
  request.nextUrl.pathname = `/${preferredLocale(request)}${pathname}`;
  return NextResponse.redirect(request.nextUrl);
}

export const config = {
  // Todo salvo los ficheros internos de Next y los estáticos con extensión.
  matcher: ["/((?!_next|.*\\..*).*)"],
};
