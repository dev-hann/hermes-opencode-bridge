/**
 * Callback handler — receives completion notifications from OpenCode.
 *
 * Uses OpenClaw's registerHttpRoute to avoid running a separate HTTP server.
 * When OpenCode finishes a task, it POSTs to this route, and the plugin
 * enqueues a next-turn injection to notify the OpenClaw session.
 */

import type { IncomingMessage, ServerResponse } from "node:http";

export interface CallbackPayload {
  session_id: string;
  session_title?: string;
  status: "completed" | "error";
  summary?: string;
  directory?: string;
}

/**
 * Build the instruction block that tells OpenCode to call back on completion.
 * The sessionId uses __SESSION_ID__ placeholder which api.ts replaces after
 * session creation.
 */
export function buildCompletionInstruction(params: {
  callbackUrl: string;
  token: string;
  sessionId: string;
  sessionTitle?: string;
  directory: string;
}): string {
  const payload = {
    session_id: params.sessionId,
    session_title: params.sessionTitle ?? "",
    directory: params.directory,
  };

  // Build curl command as plain strings to avoid template literal issues
  const jsonStr = JSON.stringify(payload);
  const lines: string[] = [
    "",
    "<completion_callback>",
    "When your task is fully complete (all changes made, tested, committed, pushed),",
    "run this command to notify OpenClaw:",
    "",
    "```bash",
    'curl -s -X POST "' + params.callbackUrl + '" \\',
    '  -H "Content-Type: application/json" \\',
    '  -H "X-Callback-Token: ' + params.token + '" \\',
    "  -d '" + jsonStr + "'",
    "```",
    "",
    "If the task fails or you cannot complete it, run the same command",
    'but add "status": "error" and a "summary" field explaining what went wrong.',
    "You MUST run this callback exactly once when you are done. Do not run it early.",
    "</completion_callback>",
  ];

  return lines.join("\n");
}

/**
 * Verify the callback token from the request header.
 */
export function verifyToken(req: IncomingMessage, expectedToken: string): boolean {
  const authHeader = req.headers["x-callback-token"];
  if (Array.isArray(authHeader)) {
    return authHeader[0] === expectedToken;
  }
  return authHeader === expectedToken;
}

/**
 * Read and parse JSON body from incoming request.
 */
export function readBody(req: IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    let data = "";
    req.on("data", (chunk) => {
      data += chunk;
      if (data.length > 65536) {
        reject(new Error("Payload too large"));
        req.destroy();
      }
    });
    req.on("end", () => resolve(data));
    req.on("error", reject);
  });
}

/**
 * Send a JSON response.
 */
export function sendJson(res: ServerResponse, status: number, body: unknown): void {
  const json = JSON.stringify(body);
  res.writeHead(status, {
    "Content-Type": "application/json",
    "Content-Length": Buffer.byteLength(json),
  });
  res.end(json);
}
