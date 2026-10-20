import { afterEach, expect, it, vi } from "vitest";
import { formatDateTime, formatTime } from "../utils/format";

afterEach(() => vi.restoreAllMocks());

it("renders database UTC and offset timestamps as the same local instant", () => {
  const instant = Date.parse("2026-10-20T19:21:53Z");
  vi.spyOn(Date.prototype, "toLocaleTimeString").mockImplementation(function (this: Date) { return String(this.getTime()); });
  vi.spyOn(Date.prototype, "toLocaleString").mockImplementation(function (this: Date) { return String(this.getTime()); });
  for (const value of ["2026-10-20T19:21:53", "2026-10-20T19:21:53Z", "2026-10-20T21:21:53+02:00"]) {
    expect(formatTime(value)).toBe(String(instant));
    expect(formatDateTime(value)).toBe(String(instant));
  }
});

it("shows a placeholder for missing or invalid timestamps", () => {
  for (const value of [null, undefined, "", "invalid"]) {
    expect(formatTime(value)).toBe("—");
    expect(formatDateTime(value)).toBe("—");
  }
});
