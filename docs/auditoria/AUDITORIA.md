# Auditoría del proyecto (02/10/2026)

Alcance: todo lo hecho del **plan original**, las fases 0–6, y del **plan de acción**: el tronco T1–T3, C1, C2 y D1. Lo pendiente (D2, D3, S1, C3, W1, W2, A1 y F0) no se ha contado como fallo.

## 1. Resumen

**El proyecto está sano.**
- La ingesta, la API y la web no tienen fallos críticos.
- La seguridad, la idempotencia, la integridad de las publicaciones y las pruebas están por encima de lo habitual en un TFG.
- Los bloques T1–T3, C1, C2 y D1 cumplen su criterio de terminado.
- Las cifras de `SIGUIENTES_PASOS.md` se han reproducido todas.

Hay **cinco fallos de gravedad alta, todos verificados por dos agentes**:
- **Tres comparten una misma causa:** los años y las temporadas de pilotos y constructores se sacan de la clasificación final de F1DB, que no incluye a quien no puntuó. Son DAT-01, DAT-02 y DAT-03.
- **La definición de «puntos de constructor» es errónea:** ninguna de las dos cifras que da la API es la oficial. Son API-01 y N1.
- **Un tercero no puede reproducir el proyecto siguiendo el README:** es DOC-01, y el arreglo es solo de documentación.

Todos los fallos altos se ven hoy en producción, salvo el del README. Propongo un bloque corto de correcciones (**C4**) antes de seguir con D2 (sección 6).

## 2. Método

| Área | Agente | Nota |
|---|---|---|
| 1. Ingesta, pipeline y releases | `f1-revisor-opus` | [notas/01_ingesta_pipeline.md](notas/01_ingesta_pipeline.md) |
| 2. Modelo de datos y calidad (dbt) | `f1-investigador` | [notas/02_modelo_datos.md](notas/02_modelo_datos.md) |
| 3. API | `f1-revisor-opus` | [notas/03_api.md](notas/03_api.md) |
| 4. Web | `f1-revisor-opus` | [notas/04_web.md](notas/04_web.md) |
| 5. Documentación frente a los planes | `f1-revisor-opus` | [notas/05_documentacion_planes.md](notas/05_documentacion_planes.md) |
| 6. Verificación crítica de los hallazgos | `f1-critico` | [notas/06_verificacion.md](notas/06_verificacion.md) |

- **Solo lectura.** Ningún agente modificó el proyecto. Las instrucciones comunes están en [INSTRUCCIONES.md](INSTRUCCIONES.md).
- **Comprobaciones ejecutadas:**
  - pytest, ruff y `dbt build` (223/223);
  - 16 130 peticiones GET a la API en local;
  - Playwright y axe contra producción, en escritorio y a 375 px;
  - un clon limpio del repositorio;
  - consultas sobre la base publicada `data-2026-10-01-6.1`.
- **Copias de la base.** Apareció una copia antigua, `data-2026-09-29`, en una carpeta temporal compartida. El verificador comprobó que todos los datos citados son idénticos en la copia publicada, en la local y en la del clon limpio. Ningún hallazgo cambia.
- **Gravedades.** Son las que fija el verificador cuando revisó el hallazgo; en el resto, las del auditor. Los duplicados entre áreas están unificados.

## 3. Lo que está bien hecho

**Ingesta y pipeline**
- Escritura atómica e idempotente: no hay ningún duplicado en el bronze.
- La carga es incremental de verdad, por carrera, sesión y endpoint.
- El cliente de OpenF1 es robusto:
  - respeta el límite de peticiones y la cabecera `retry-after`;
  - pone un tope a las respuestas 429 seguidas;
  - tiene un plazo global por ejecución.
- La extracción de las copias es segura: filtro `data`, lista blanca de ficheros y sin enlaces.
- Se publica en orden: primero la release fechada y el manifiesto en último lugar.
- Las acciones están fijadas por SHA y el token solo llega a los pasos que usan `gh`.

**Modelo de datos**
- Paridad automática con F1DB: títulos, inscripciones, salidas, victorias, podios, poles, vueltas rápidas y grand slams.
- Las correcciones de datos tienen evidencia y se desactivan solas si F1DB las arregla.
- La fusión de vueltas está documentada y tiene 14 unit tests.
- Los desempates son deterministas.
- Ninguna tabla tiene HUGEINT ni NaN, y hay un test que lo vigila.
- El grano está declarado y probado en todos los hechos.
- 58 controles de calidad entre fuentes que bloquean la publicación.
- La prioridad de fuentes de la decisión 20 está bien implementada.

**API**
- Todo el SQL está parametrizado.
- La base se abre de verdad en solo lectura.
- La recarga de datos no corta el servicio.
- Arranca sin GitHub gracias a la copia de respaldo.
- El contenedor no corre como root.
- La caché HTTP está completa (ETag y 304).
- La CI vigila que el contrato de la API siga siendo el que usa la web.
- Los coches compartidos están tratados y probados.

**Web**
- Las 18 rutas del plan responden, incluidas la telemetría y el mapa, y los ids inválidos dan 404.
- La CSP y las cabeceras de seguridad están completas.
- Los parámetros se validan antes de llamar a la API.
- El cliente aguanta el arranque en frío de Render.
- Buena base de accesibilidad:
  - enlace para saltar al contenido y foco visible;
  - tablas accesibles;
  - paleta Okabe-Ito y respeto de `prefers-reduced-motion`.
- Los estados vacíos son correctos.

**Documentación y seguimiento**
- Las decisiones 15–33 incluyen alternativas y motivo, y sirven directamente para la memoria.
- El pipeline está documentado al detalle.
- Las licencias y atribuciones son coherentes en el README, la API, las notas de las releases y la web.

## 4. Hallazgos

Leyenda de la columna «Verif.»:
- **V2:** reproducido por el auditor y por el verificador.
- **V1:** reproducido solo por el auditor.
- **L:** deducido leyendo el código.

### Alta

| ID | Hallazgo | Verif. | Evidencia | Arreglo propuesto |
|---|---|---|---|---|
| DAT-01 | `agg_driver_season` pierde las temporadas sin puntos: 1 586 pares temporada-piloto, todos con 0 puntos, entre 1950 y 2017. Hay 404 pilotos con salidas que no tienen ninguna fila | V2 | `/drivers?season=1985` devuelve 20 pilotos de 36. En `/drivers/ayrton-senna/seasons` falta 1994 | Construirlo desde `fact_race_result`, con *left join* a la clasificación, y añadir un test de cobertura (DAT-05) |
| DAT-02 | `first_season` y `last_season` de los pilotos están mal en 564 y 529 de 792, y son nulos en 404 | V2 | Senna sale de 1984 a 1993, Lauda desde 1973, Mansell hasta 1994 y Button hasta 2016, en la release y en producción | Calcular el mínimo y el máximo desde los resultados. Misma causa que DAT-01 |
| DAT-03 | Años de los constructores: 28 tienen mal el primer año (Ferrari, Cooper y Maserati salen desde 1958; Mercedes desde 2010) y 20 tienen mal el último (Tyrrell 1997, Lotus 1993, Brabham 1991) | V2 | `/constructors/ferrari` da 1958 | Calcular los años solo desde los resultados |
| API-01 + N1 (y DAT-11) | Los puntos de constructores no son los oficiales. Ferrari tiene 11 779,77 en `/records` y 12 001,77 en `/rankings`, y la web muestra «12.001,8». El oficial de F1DB es **11 409**: carrera más sprint, solo desde 1958, porque antes no había campeonato de constructores | V2 | Con esa definición los puntos cuadran con F1DB en 186 de 186 constructores. El test de paridad no compara los puntos, y por eso no se detectó | Una definición única en dbt, que use también `/rankings`, y añadir `points` a `assert_constructor_totals_match_f1db`. Corrige además la nota DBT-7 y el comentario inicial de `rankings.py`, que dicen que ya coinciden |
| DOC-01 (+ N2) | Un tercero no puede reproducir el proyecto con «Puesta en marcha»: `legacy` y `ergast` leen carpetas que están fuera del repositorio. `legacy` además termina con código 0 aunque no encuentre nada (N2) | V2 | En un clon limpio, `dbt build` da 6 errores. La alternativa `snapshot restore` del `bronze.tar.gz` publicado da 223 de 223 | Añadir al README una sección «Reproducir desde cero» con `snapshot restore`, y que `legacy` falle con un mensaje claro |

### Media

| ID | Hallazgo | Verif. | Arreglo y momento |
|---|---|---|---|
| WEB-01 | `raceTime` formatea mal las duraciones con 0 minutos: «2:00004.795» en 21 carreras, la última de 2014 | V2 | Corregir el formato y añadir la primera prueba unitaria de la web (C4 o C3) |
| DAT-04 | Los puntos del duelo entre compañeros (H2H) no cuentan el sprint | V2 | Incluir el sprint, que es lo que dice el reglamento desde 2021, y explicar en la web que solo cuentan las carreras compartidas (C4) |
| DOC-02 = DAT-09 | Solo 36 de las 299 columnas de gold tienen descripción, aunque los 19 modelos sí la tienen | V2 | Descripciones con `doc` blocks, empezando por los `agg_*` (A1 o junto a la memoria) |
| DAT-05 | Faltan pruebas que prometía el plan: `accepted_values` en `position_text`, integridad referencial y cobertura de los agregados | V1 | Junto a DAT-01 (C4) |
| DAT-06 | Una carrera con datos solo de OpenF1 se da por fiable sin contrastarla | V1 | Contrastarla con Jolpica en D2 |
| ING-01 | El pipeline no comprueba que el `bronze.tar.gz` anterior exista ni su SHA, así que no recurre a la release fechada si falta | V2 | Verificar el SHA y recurrir a la release fechada (D2, que ya toca el pipeline) |
| ING-02 | El umbral de filas perdidas es del 2 % en todas las tablas: podrían desaparecer 22 carreras y la prueba de humo seguiría en verde | V2 | Umbral 0 en las dimensiones (D2) |
| WEB-02 / WEB-03 | La página 404 no tiene `<title>`, y las 7 pestañas de una carrera comparten título | V1 | C3 / W1 |
| WEB-04 | En telemetría y en tiempos por vuelta las series solo se distinguen por el color | V1 | W2 |
| WEB-05 | No hay `loading.tsx`, así que no se ve nada mientras la API despierta (hasta unos 81 s) | V2 | C3 |
| WEB-06 | En la versión española, países, nacionalidades y motivos de abandono salen en inglés | V2 | Países, por su código ISO, en C3. Los motivos de abandono, en la seed de F0 |
| DOC-04 | La documentación menciona una opción `seasons` del pipeline que no existe | V1 | Inmediato (documentación) |
| DOC-06 | Las desviaciones del plan original no están registradas: shadcn, MapLibre, next-intl, Lighthouse CI, sqlfluff y nombres de endpoints | V1 | Inmediato: registrarlas como decisiones retroactivas |
| DOC-07 | No hay evidencia de la paridad de KPIs con el .pbix que pedía la verificación del plan original | V1 | Decisión del autor (sección 7) |

### Baja (resumen; el detalle está en las notas)

- **Ingesta:**
  - ING-03: una sesión de OpenF1 ya descargada no se puede volver a pedir (baja según el verificador). Es consecuencia de la decisión 24 y los defectos no llegan a gold.
  - ING-04: `continue-on-error` oculta los fallos del propio cargador de OpenF1.
  - ING-05: el cargador de F1DB no tiene pruebas ni reintentos.
  - ING-06: la ruta local con el nombre del autor está publicada en `bronze-static-v1`.
  - ING-07: se conservan 8 releases, no 8 semanas.
  - ING-08: el job de dbt de la CI pasa en verde sin `dbt build` si falla la descarga.
  - ING-09: las notas son incorrectas si falla la subida de OpenF1.
  - ING-10: los tipos del bronze de OpenF1 no son estables entre sesiones.
- **Modelo de datos:**
  - DAT-07: F1DB tiene desplazada la vuelta de la vuelta rápida en 2025–2026.
  - DAT-08: «pole» se usa con dos significados.
  - DAT-10: las vistas de staging usan rutas relativas.
  - DAT-12: `race_time_utc` sigue siendo VARCHAR.
- **API:**
  - API-02: la ETag no cambia con el código.
  - API-03: los enteros fuera de rango dan 500.
  - API-04: algunos órdenes no son deterministas.
  - API-05: las horas UTC salen sin zona.
  - API-06: la búsqueda trata `%` y `_` como comodines.
  - API-07: `drivers=,,,` devuelve una lista vacía.
  - API-09: falta la prueba de `GET /constructors`.
  - API-10 y API-11: observaciones sobre Render free y la imagen.
- **Web:**
  - WEB-07: el lap chart no se puede manejar con el teclado.
  - WEB-08: el trazado coloreado no tiene alternativa en tabla.
  - WEB-09: el cambio de idioma pierde la consulta.
  - WEB-10: la comprobación del idioma con `in` acepta claves del prototipo.
  - WEB-11: la CSP lleva `unsafe-inline`.
  - WEB-12: cada tabla es una parada de tabulación.
- **Documentación:**
  - DOC-03: el README dice que las páginas se cachean; en realidad solo se cachean los datos.
  - DOC-05: falta anotar en la decisión 1 que la decisión 2 la modifica.
  - DOC-08: las decisiones 31–33 están en otra tabla.
  - DOC-09: quedan restos desfasados en `SIGUIENTES_PASOS.md`.
  - DOC-10: el docstring de Ergast está desfasado.
  - DOC-11: el diagrama del README no muestra el despliegue.
  - DOC-12 (incluye API-08): faltan los endpoints `/rankings/*` en el README.
  - DOC-13: las sesiones de FastF1 del D1 original no se han reasignado.
  - DOC-14: hay erratas de dependencias en la tabla de bloques.

## 5. Promesas de los planes no cumplidas o desviadas

| Promesa | Estado |
|---|---|
| Plan original, fase 0: sqlfluff en pre-commit | No está (DOC-06) |
| Fase 2: diccionario de datos con `dbt docs` | Los modelos están descritos, pero las columnas no (DOC-02). La publicación en Pages se aplazó (decisión 10) |
| Fase 2: `accepted_values` en `position_text` | No está (DAT-05) |
| Fase 4: nombres de endpoints | Algunos cambiaron (`/teammates`, `/records/*`, `/circuits`). Están documentados, pero no registrados como decisión (DOC-06) |
| Fase 5: shadcn/ui, MapLibre y next-intl | Se usaron alternativas propias (DOC-06) |
| Fase 5: ISR con `revalidate` | Las páginas son dinámicas; solo se cachean los datos (DOC-03, ya anotado como A1/A2) |
| Verificación: Lighthouse CI con umbrales | No está (WEB, DOC-06) |
| Verificación: paridad de KPIs con el .pbix | Sin evidencia (DOC-07). Sí hay paridad automática con F1DB |
| D1 original: sesiones FP, SQ y SS de FastF1 | La decisión 22 las sustituyó por OpenF1; no se han reasignado de forma explícita (DOC-13) |

## 6. Cómo encajarlo en el plan (propuesta)

1. **Arreglos inmediatos de documentación, sin agentes, unas 2 h:**
   - DOC-01 y N2: sección «Reproducir desde cero» en el README y que `legacy` falle si no encuentra la carpeta;
   - DOC-04, DOC-05, DOC-08, DOC-09, DOC-12 y la nota DBT-7 de `SIGUIENTES_PASOS.md`;
   - DOC-06: desviaciones del plan original registradas como decisiones.
2. **Bloque nuevo C4, «correcciones de agregados», antes de D2.** Es de riesgo alto (datos), unos 1–2 días, con `f1-implementador-alto` y `f1-revisor-opus`. Incluye:
   - DAT-01, DAT-02 y DAT-03: años y temporadas calculados desde los resultados;
   - API-01, N1 y DAT-11: una definición única de puntos de constructor (carrera más sprint, solo desde 1958) y el test de paridad;
   - DAT-04: el sprint en el duelo entre compañeros;
   - DAT-05: tests de cobertura y `accepted_values`;
   - WEB-01: el formato de tiempo y la primera prueba unitaria de la web.
3. **D2 amplía su alcance** con DAT-06 (contrastar con Jolpica las carreras que solo tienen OpenF1) y con ING-01 y ING-02 (endurecer la descarga y los umbrales), porque D2 ya toca el pipeline.
4. **C3** absorbe WEB-02, WEB-05 y la parte de países de WEB-06. **W1** absorbe WEB-03 y **W2** absorbe WEB-04. **F0** absorbe los motivos de abandono de WEB-06.
5. **A1** absorbe DOC-02 y DAT-09, los fallos bajos de la API (API-02 a API-07 y API-09) y los bajos de ingesta (ING-04, ING-05, ING-08 e ING-10).
6. **Lista de pendientes sin bloque:** el resto de fallos bajos, por ejemplo ING-03 (orden `--refresh-session`), ING-06 y WEB-07 a WEB-12.

## 7. Decisiones que necesita el autor (para `/grill-me`)

1. **¿Se crea C4 y va antes de D2?** Recomendado: sí, porque hay datos visiblemente erróneos en producción (Senna, Ferrari).
2. **Qué cuenta como «temporada» de un piloto** (DAT-01 y DAT-02): las inscripciones (incluidas las no clasificaciones y las exclusiones) o solo las salidas. El recuento cambia: 472 pilotos sin filas frente a 404.
3. **Puntos antes de 1958:** si `/rankings/constructors` con un rango anterior a 1958 da 0, nulo o un aviso.
4. **Paridad con el .pbix (DOC-07):** comprobar una muestra de KPIs a mano en Power BI, darla por cubierta con la paridad automática con F1DB, o dejarla documentada como limitación.
5. **¿Se hacen ya los arreglos inmediatos de documentación** del punto 6.1?
