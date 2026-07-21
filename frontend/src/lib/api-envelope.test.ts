import { describe, expect, it } from "vitest";
import {
  ApiError,
  errorEnvelope,
  isErrorEnvelope,
  isSuccessEnvelope,
  parseEnvelopeError,
  successEnvelope,
  unwrapEnvelopeData,
} from "./api-envelope";

describe("api-envelope", () => {
  it("builds success envelope", () => {
    const env = successEnvelope({ id: "1" }, "ok", { trace: "abc" });
    expect(isSuccessEnvelope(env)).toBe(true);
    expect(env.data).toEqual({ id: "1" });
    expect(env.message).toBe("ok");
    expect(env.meta).toEqual({ trace: "abc" });
  });

  it("builds error envelope", () => {
    const env = errorEnvelope("NOT_FOUND", "missing", 404, { job_id: "x" }, { job_id: "x" });
    expect(isErrorEnvelope(env)).toBe(true);
    expect(env.error.code).toBe("NOT_FOUND");
    expect(env.error.status_code).toBe(404);
  });

  it("unwraps enveloped data and falls back to bare payload", () => {
    expect(unwrapEnvelopeData(successEnvelope({ jobs: [] }))).toEqual({ jobs: [] });
    expect(unwrapEnvelopeData({ jobs: [] })).toEqual({ jobs: [] });
  });

  it("parses backend error envelope into ApiError", () => {
    const err = parseEnvelopeError(errorEnvelope("UNAUTHORIZED", "unauthorized", 401), 401);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe("UNAUTHORIZED");
    expect(err.message).toBe("unauthorized");
    expect(err.statusCode).toBe(401);
  });

  it("parses legacy message and FastAPI detail shapes", () => {
    expect(parseEnvelopeError({ message: "bad request" }, 400).message).toBe("bad request");
    expect(parseEnvelopeError({ detail: "not found" }, 404).code).toBe("NOT_FOUND");
    expect(parseEnvelopeError({ detail: [{ msg: "field required" }] }, 422).message).toBe(
      "field required",
    );
  });
});
