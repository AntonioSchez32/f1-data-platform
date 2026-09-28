import "server-only";

import { notFound } from "next/navigation";

const dictionaries = {
  es: () => import("@/dictionaries/es.json").then((module) => module.default),
  en: () => import("@/dictionaries/en.json").then((module) => module.default),
};

export type Locale = keyof typeof dictionaries;
export type Dictionary = Awaited<ReturnType<(typeof dictionaries)["es"]>>;

export const locales = Object.keys(dictionaries) as Locale[];
export const defaultLocale: Locale = "es";

export const hasLocale = (locale: string): locale is Locale => locale in dictionaries;

/** Diccionario del idioma de la ruta; 404 si el idioma no existe. */
export async function getDictionary(lang: string): Promise<{ locale: Locale; t: Dictionary }> {
  if (!hasLocale(lang)) notFound();
  return { locale: lang, t: await dictionaries[lang]() };
}
