const slug = /^[a-z0-9-]{1,64}$/;
const token = /^[a-f0-9]{64}$/;
const code = /^[a-f0-9]{36}$/;
const id = /^[a-f0-9]{32}$/;
const hex = bytes => Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("");
const random = length => hex(crypto.getRandomValues(new Uint8Array(length)));
const digest = async value => hex(new Uint8Array(
  await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value)),
));
const json = (body, status = 200) => Response.json(body, {
  status,
  headers: { "Cache-Control": "no-store" },
});

export default {
  async fetch(request, env) {
    if (request.method !== "POST") return json({ error: "method_not_allowed" }, 405);
    const path = new URL(request.url).pathname;
    if (!["/issue", "/redeem", "/check", "/revoke"].includes(path)) {
      return json({ error: "not_found" }, 404);
    }
    if (path === "/issue" || path === "/revoke") {
      const bearer = request.headers.get("Authorization") ?? "";
      if (!token.test(env.ADMIN_TOKEN ?? "") || bearer !== "Bearer " + env.ADMIN_TOKEN) {
        return json({ error: "unauthorized" }, 401);
      }
    }

    let data;
    try {
      const reader = request.body?.getReader();
      if (!reader) return json({ error: "invalid_request" }, 400);
      let size = 0;
      const decoder = new TextDecoder();
      let input = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > 4096) {
          await reader.cancel();
          return json({ error: "request_too_large" }, 413);
        }
        input += decoder.decode(value, { stream: true });
      }
      data = JSON.parse(input + decoder.decode());
    } catch {
      return json({ error: "invalid_request" }, 400);
    }
    const { game, activationCode, installationToken, licenseId } = data ?? {};
    if (typeof game !== "string" || !slug.test(game)) return json({ error: "invalid_game" }, 400);

    const now = Math.floor(Date.now() / 1000);
    const db = env.DB;
    if (path === "/issue") {
      const newId = random(16);
      const newCode = random(18);
      const expiresAt = now + 86400;
      await db.prepare("INSERT INTO licenses (id, game, code_hash, expires_at) VALUES (?, ?, ?, ?)")
        .bind(newId, game, await digest(newCode), expiresAt).run();
      return json({ licenseId: newId, activationCode: newCode, expiresAt }, 201);
    }
    if (path === "/revoke") {
      if (typeof licenseId !== "string" || !id.test(licenseId)) return json({ error: "invalid_id" }, 400);
      const result = await db.prepare("UPDATE licenses SET revoked = 1 WHERE id = ? AND game = ? AND revoked = 0")
        .bind(licenseId, game).run();
      return json({ revoked: result.meta.changes === 1 });
    }
    if (typeof installationToken !== "string" || !token.test(installationToken)) {
      return json({ error: "invalid_installation" }, 400);
    }
    const installation = await digest(installationToken);
    if (path === "/check") {
      const found = await db.prepare("SELECT 1 FROM licenses WHERE game = ? AND installation_hash = ? AND revoked = 0")
        .bind(game, installation).first();
      return json({ allowed: Boolean(found) });
    }
    if (typeof activationCode !== "string" || !code.test(activationCode)) {
      return json({ error: "invalid_code" }, 400);
    }
    // A retry by the same installation succeeds. A second installation cannot claim this code.
    const result = await db.prepare(`
      UPDATE licenses SET installation_hash = ?
      WHERE game = ? AND code_hash = ? AND revoked = 0
        AND (installation_hash = ? OR (installation_hash IS NULL AND expires_at > ?))
        AND NOT EXISTS (
          SELECT 1 FROM licenses AS other
          WHERE other.game = licenses.game AND other.installation_hash = ?
            AND other.id != licenses.id AND other.revoked = 0
        )
    `).bind(installation, game, await digest(activationCode), installation, now, installation).run();
    const allowed = result.meta.changes === 1;
    return json({ allowed }, allowed ? 200 : 403);
  },
};
