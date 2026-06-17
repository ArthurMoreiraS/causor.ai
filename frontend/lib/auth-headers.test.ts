import { describe, it, expect } from "vitest";
import { withAuthHeaders } from "./auth-headers";

describe("withAuthHeaders", () => {
  it("adiciona Authorization quando há token", () => {
    const result = withAuthHeaders({ "Content-Type": "application/json" }, "abc");
    expect(result).toEqual({
      "Content-Type": "application/json",
      Authorization: "Bearer abc"
    });
  });

  it("não adiciona Authorization quando o token é nulo/indefinido", () => {
    expect(withAuthHeaders({ "Content-Type": "application/json" }, null)).toEqual({
      "Content-Type": "application/json"
    });
    expect(withAuthHeaders({ "Content-Type": "application/json" }, undefined)).toEqual({
      "Content-Type": "application/json"
    });
  });
});
