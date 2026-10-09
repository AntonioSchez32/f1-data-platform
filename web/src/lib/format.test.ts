import { describe, expect, it } from "vitest";

import { gap, lapTime, number, raceTime } from "./format";

describe("raceTime", () => {
  it("rellena los minutos y los segundos cuando los minutos son 0 (WEB-01, Singapur 2014)", () => {
    expect(raceTime(7_204_795)).toBe("2:00:04.795");
  });

  it("formatea una carrera de más de una hora", () => {
    expect(raceTime(5_523_897)).toBe("1:32:03.897");
    expect(raceTime(3_600_000)).toBe("1:00:00.000");
  });

  it("sin horas, igual que una vuelta", () => {
    expect(raceTime(3_599_999)).toBe("59:59.999");
    expect(raceTime(65_432)).toBe("1:05.432");
  });

  it("sin dato, una raya", () => {
    expect(raceTime(null)).toBe("—");
    expect(raceTime(undefined)).toBe("—");
  });
});

describe("lapTime", () => {
  it("minutos y segundos con tres decimales", () => {
    expect(lapTime(92_345)).toBe("1:32.345");
    expect(lapTime(61_005)).toBe("1:01.005");
  });

  it("menos de un minuto, solo segundos", () => {
    expect(lapTime(23_456)).toBe("23.456");
  });

  it("sin dato, una raya", () => {
    expect(lapTime(null)).toBe("—");
  });
});

describe("gap y number", () => {
  it("diferencia en tiempo o en vueltas", () => {
    expect(gap(1_234)).toBe("+1.234");
    expect(gap(null, 2, "laps")).toBe("+2 laps");
    expect(gap(null)).toBe("");
  });

  it("números con el formato del idioma y raya si no hay dato", () => {
    expect(number(12001.77, "en", 2)).toBe("12,001.77");
    expect(number(11409, "en")).toBe("11,409");
    expect(number(null, "es")).toBe("—");
  });
});
