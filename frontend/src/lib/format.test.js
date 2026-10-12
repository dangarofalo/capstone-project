import { describe, expect, it } from "vitest";
import { eventLabel, localInputToIso, logonLabel, ruleLabel, timeAgo, toQuery } from "./format.js";

describe("labels", () => {
  it("turns codes into plain English", () => {
    expect(eventLabel("login_failure")).toBe("Failed login");
    expect(ruleLabel("brute_force")).toBe("Password-guessing attack");
    expect(logonLabel("10")).toBe("Remote Desktop");
    expect(logonLabel("ssh")).toBe("SSH");
  });

  it("falls back to the raw value for unknown codes", () => {
    expect(eventLabel("something_new")).toBe("something_new");
    expect(logonLabel("4")).toBe("Type 4");
    expect(logonLabel(null)).toBe("");
  });
});

describe("timeAgo", () => {
  const now = new Date("2026-10-12T12:00:00Z").getTime();
  it.each([
    ["2026-10-12T11:59:50Z", "just now"],
    ["2026-10-12T11:55:00Z", "5 min ago"],
    ["2026-10-12T09:00:00Z", "3 hr ago"],
    ["2026-10-11T12:00:00Z", "1 day ago"],
    ["2026-10-10T22:00:00Z", "1 day ago"], // 38 hours: rounds down
    ["2026-10-02T12:00:00Z", "10 days ago"],
  ])("%s -> %s", (value, expected) => {
    expect(timeAgo(value, now)).toBe(expected);
  });

  it("handles missing values", () => {
    expect(timeAgo(null, now)).toBe("never");
  });
});

describe("toQuery", () => {
  it("drops empty filters and encodes the rest", () => {
    expect(toQuery({ host: "PC 1", username: "", severity: null, active: false, limit: 50 })).toBe(
      "?host=PC+1&limit=50",
    );
    expect(toQuery({})).toBe("");
  });
});

describe("localInputToIso", () => {
  it("converts a local date-time input to an ISO UTC string", () => {
    expect(localInputToIso("")).toBe("");
    expect(localInputToIso("2026-10-12T08:30")).toMatch(/^2026-10-1\dT\d\d:30:00\.000Z$/);
  });
});
