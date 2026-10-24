// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, streamChat } from "./api";
import type { StreamEvent } from "@/types/api";

function sseResponse(chunks: string[], status = 200): Response {
  const encoder = new TextEncoder();
  const body = new ReadableStream({
    start(controller) {
      for (const c of chunks) controller.enqueue(encoder.encode(c));
      controller.close();
    },
  });
  return new Response(body, { status, headers: { "Content-Type": "text/event-stream" } });
}

const frame = (event: string, data: unknown) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
async function collect(gen: AsyncGenerator<StreamEvent>) {
  const out: StreamEvent[] = [];
  for await (const e of gen) out.push(e);
  return out;
}
const DONE = { conversation_id: "c", intent: "study_question", retrieval_path: [], execution_events: [], evidence_found: true, artifact: null, latency_ms: 1 };

afterEach(() => vi.unstubAllGlobals());

describe("streamChat", () => {
  it("parses events even when the network splits them at arbitrary byte boundaries", async () => {
    const wire = frame("token", { text: "héllo ✓" }) + frame("done", DONE);
    const chunks = [wire.slice(0, 7), wire.slice(7, 30), wire.slice(30)]; // splits mid-header and mid-JSON
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sseResponse(chunks)));
    const events = await collect(streamChat({ question: "q" }));
    expect(events.map((e) => e.event)).toEqual(["token", "done"]);
    expect(events[0]).toMatchObject({ data: { text: "héllo ✓" } });
  });

  it("sends the request as JSON POST to the backend", async () => {
    const fetchMock = vi.fn().mockResolvedValue(sseResponse([frame("done", DONE)]));
    vi.stubGlobal("fetch", fetchMock);
    await collect(streamChat({ question: "hi", conversation_id: "abc", document_ids: ["d1"] }));
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/chat\/stream$/);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ question: "hi", conversation_id: "abc", document_ids: ["d1"] });
  });

  it("turns a pre-stream HTTP error into a typed ApiError with the server's code", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ error: { code: "not_found", message: "Some documents were not found.", details: {} } }), { status: 404 })));
    await expect(collect(streamChat({ question: "q" }))).rejects.toMatchObject({ name: "ApiError", status: 404, code: "not_found" });
  });

  it("reports a dropped connection when the stream ends without done or error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sseResponse([frame("token", { text: "partial" })])));
    const err = await collect(streamChat({ question: "q" })).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe("stream_interrupted");
  });

  it("accepts an error event as a valid terminal event", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sseResponse([frame("error", { code: "x", message: "m", retryable: false })])));
    expect((await collect(streamChat({ question: "q" }))).map((e) => e.event)).toEqual(["error"]);
  });

  it("explains an unreachable backend", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(collect(streamChat({ question: "q" }))).rejects.toMatchObject({ code: "network_error", message: expect.stringContaining("Is it running?") });
  });

  it("propagates cancellation as an AbortError, not as a failure", async () => {
    const ctrl = new AbortController();
    vi.stubGlobal("fetch", vi.fn().mockImplementation((_u: string, init: RequestInit) => new Promise((_res, rej) => {
      init.signal?.addEventListener("abort", () => rej(new DOMException("aborted", "AbortError")));
    })));
    const pending = collect(streamChat({ question: "q" }, ctrl.signal));
    ctrl.abort();
    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
  });
});
