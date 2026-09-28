# Propuesta de correcciones para F1DB (decisión N10)

Texto y ficheros para proponer a [F1DB](https://github.com/f1db/f1db) los errores confirmados en la
revisión de divergencias de 2026. **No se ha publicado nada**: decides tú si abrir la *issue*.

- Detalle, un valor por fila: `f1db_correcciones_propuestas.csv` (194 filas, con la evidencia de
  cada una).
- Hojas de evidencia originales: `B1_numero_vuelta_rapida.csv`, `B5_parrillas.csv`,
  `B2_tiempos_clasificacion.csv`, `V7_vueltas_completadas_historicas.csv` y
  `B4_correcciones_Script2.csv`.

Recomendaciones antes de publicar:
- Adjunta el CSV a la *issue*. Los PDF de la FIA **no** se redistribuyen: cítalos por su título
  (están en fia.com).
- Si el mantenedor lo prefiere, puede dividirse en varias *issues* (una por tipo de dato).
- La versión revisada de F1DB es `v2026.15.1`.

---

## Texto propuesto (en inglés, para el repositorio de F1DB)

**Title:** Data corrections found cross-checking F1DB with FIA documents and Stats F1 (v2026.15.1)

Hi! While building a data project on top of F1DB I cross-checked it against formula1db.com, Ergast
and FastF1, and settled every disagreement with official FIA timing documents or, when those were
not available, Stats F1. These are the values where F1DB appears to be wrong. The attached CSV has
one row per value: season, round, driver, field, current F1DB value, proposed value and evidence.

**1. Fastest lap number (97 values: 96 in rounds 1–8 of 1998, 1 in 1996).** The lap time is correct but
it is attached to the wrong lap. Stats F1, formula1db.com and Ergast all agree on the proposed lap.
Example: 1998 French GP, Frentzen, 1:19.229, lap 47 in F1DB and lap 48 in the other sources.
*Not included:* 2001 Belgian GP, where F1DB counts laps from the first start and the other sources
count from the restart. That is a convention, not an error. F1DB's own pit stops in that race use
the restart numbering, so it may still be worth unifying.

**2. Laps completed (72 values, 1950–1997).** Stats F1, formula1db.com and Ergast agree on a
different lap count for these drivers. Many are shared cars, where F1DB gives each driver the
car's total while the other sources split the laps between drivers (for example Bonetto and Fangio
at the 1953 Swiss GP). The others are retirements that differ by one lap.

**3. Starting grid in race results (5 drivers).** In the 2020 Styrian GP (Russell 11, Stroll 12,
Kvyat 13, Leclerc 14) and the 2023 Qatar GP (Hülkenberg 14), `race_grid_position_number` in the race
results does not match F1DB's own starting grid, which agrees with the FIA final starting grid.
`race_positions_gained` changes accordingly.

**4. 2018 Brazilian GP, P14/P15.** The FIA race classification gives 14. Vandoorne
(1:28:14.332) and 15. Ocon (1:28:15.651). F1DB has them the other way round. FastF1, Ergast and
formula1db.com agree with the FIA. Neither driver scored points.

**5. 2021 Qatar GP qualifying, Verstappen Q3.** The FIA Qualifying Session Lap Times give his best
Q3 lap as 1:21.282 (lap 18). F1DB has 1:21.424, which was his earlier attempt (lap 15). The gap to
pole becomes 0.455 s.

**6. 1980 South African GP, Lammers' number.** F1DB lists both Surer and Lammers with #9 in the same
team. formula1db.com gives Lammers #10. *(Stats F1 lists #9, so this one is less certain.)*

**Also noticed, not errors:**
- F1DB pit stops match the FIA pit stop summaries exactly in the races checked (Qatar 2024;
  Australia, Monaco, Canada and Britain 2025; Monaco 2026). They exclude penalties, Safety Car
  passes and red-flag entries.
- 1994 San Marino (+4), Japanese (+13) and Spanish (−1) GPs: pit stop laps are offset from the lap
  numbering used by the fastest laps and the lap charts.
- No pit stop data for the 1994 Brazilian GP, the 1994 Monaco GP or the 1997 Italian GP.

Thanks for maintaining F1DB!
