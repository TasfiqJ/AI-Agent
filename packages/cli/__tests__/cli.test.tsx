import { describe, it, expect } from "vitest";

describe("test-guardian CLI", () => {
  it("should have shared types available", async () => {
    const shared = await import("@test-guardian/shared");
    expect(shared).toBeDefined();
  });
});
