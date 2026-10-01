---
name: grill-me
description: Entrevista exhaustiva al autor sobre un plan, un bloque o una decisión, una pregunta cada vez y con respuesta recomendada, hasta que no quede ninguna ambigüedad. Úsala cuando el usuario escriba /grill-me, pida que le «grilles» o haya que cerrar decisiones antes de implementar o replanificar.
---

# grill-me

Interroga al autor sobre el tema indicado (por ejemplo, «plan de D1») hasta llegar a un entendimiento compartido y sin huecos. El objetivo es cerrar ahora lo que, si se deja abierto, obligaría a rehacer trabajo después.

## Antes de preguntar

1. Lee el contexto del proyecto relacionado con el tema. En el TFG, las rutas son relativas a `f1-data-platform/`; si la sesión está abierta en la carpeta superior, antepón ese prefijo:
   - `docs/informe_situacion/SIGUIENTES_PASOS.md`;
   - `docs/informe_situacion/DECISIONES.md`;
   - `docs/informe_situacion/plan_accion.tex`;
   - el código afectado.
2. No preguntes lo que se puede averiguar leyendo el repositorio, los datos o la documentación. Averígualo tú.
3. Construye mentalmente el árbol de decisiones del tema: qué decisiones hay, cuáles dependen de otras y en qué orden conviene resolverlas.

## Cómo preguntar

- **Una sola pregunta cada vez.** Usa AskUserQuestion con 2–4 opciones.
- **Recomendación primero:** la opción recomendada va primera y lleva «(Recomendado)».
- **Opinión antes de preguntar:** en 2–4 líneas, explica por qué recomiendas esa opción, qué se gana, qué se arriesga y qué alternativa descartarías.
- **Orden:** recorre el árbol rama a rama, empezando por las decisiones de las que dependen otras. Cuando una respuesta abra decisiones nuevas, síguelas antes de pasar a otra rama.
- **Respuestas ambiguas:** si una respuesta es ambigua o contradice una decisión anterior, repregunta. No la interpretes por tu cuenta.
- **No te detengas pronto.** Sigue hasta que cada rama esté cerrada o el autor diga que basta.

## Al terminar

1. Resume en una tabla las decisiones tomadas: decisión, elección y motivo.
2. Añádelas a `docs/informe_situacion/DECISIONES.md` (o al registro de decisiones del proyecto en curso, si es otro) con el formato de ese fichero: fecha, alternativas valoradas y motivo.
3. Indica qué queda abierto, si queda algo, y cuál es el siguiente paso.
4. No hagas commit ni empieces a implementar sin que el autor lo pida.

Responde siempre en español.
