/**
 * POST /api/waitlist
 *
 * 收一个 email,写到 Supabase 的 waitlist 表。
 * 用 fetch 直接调 Supabase REST API,避免依赖 @supabase/supabase-js
 * (Vercel cold start 时少一个 import,部署也少出意外)。
 *
 * 期望请求体: { email: string, hp?: string, lang?: 'zh' | 'en' }
 *
 * 响应:
 *   200 { ok: true } 邮箱已记录 (或之前就在,会被 Supabase 当 upsert 静默处理)
 *   400 { ok: false, error: 'invalid_email' | 'spam' }
 *   500 { ok: false, error: 'server_misconfigured' | 'server_error', detail?: string }
 *
 * 环境变量 (Vercel Dashboard → Project Settings → Environment Variables):
 *   SUPABASE_URL         例如 https://abcd.supabase.co  (不带尾巴 /)
 *   SUPABASE_SERVICE_KEY service_role key (不是 anon key)
 *
 * Supabase 表 schema:
 *   create table waitlist (
 *     id        bigserial primary key,
 *     email     text not null unique,
 *     lang      text,
 *     ip        text,
 *     created_at timestamptz not null default now()
 *   );
 */

import type { VercelRequest, VercelResponse } from "@vercel/node";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default async function handler(req: VercelRequest, res: VercelResponse) {
  // CORS
  if (req.method === "OPTIONS") {
    res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type");
    return res.status(204).end();
  }
  if (req.method !== "POST") {
    return res.status(405).json({ ok: false, error: "method_not_allowed" });
  }

  const SUPABASE_URL = process.env.SUPABASE_URL;
  const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_KEY;
  if (!SUPABASE_URL || !SUPABASE_SERVICE_KEY) {
    console.error("[waitlist] missing env vars", {
      has_url: !!SUPABASE_URL,
      has_key: !!SUPABASE_SERVICE_KEY,
    });
    return res.status(500).json({ ok: false, error: "server_misconfigured" });
  }

  // Vercel/Node 在 application/json 时已经 parse 好;但当 content-type 不
  // 标准时 body 可能是 string 或 Buffer。做一层防御。
  let body: any = req.body;
  if (typeof body === "string") {
    try { body = JSON.parse(body); } catch { body = {}; }
  }
  body = body || {};

  // Honeypot
  if (typeof body.hp === "string" && body.hp.trim().length > 0) {
    return res.status(400).json({ ok: false, error: "spam" });
  }

  if (typeof body.email !== "string") {
    return res.status(400).json({ ok: false, error: "invalid_email" });
  }
  const email = body.email.trim().toLowerCase();
  if (!EMAIL_RE.test(email) || email.length > 254) {
    return res.status(400).json({ ok: false, error: "invalid_email" });
  }

  const lang =
    typeof body.lang === "string" && (body.lang === "zh" || body.lang === "en")
      ? body.lang
      : null;

  const ipHeader = req.headers["x-forwarded-for"];
  const ip = Array.isArray(ipHeader)
    ? ipHeader[0]
    : (ipHeader ?? "").toString().split(",")[0]?.trim() || null;

  // 直接 POST 到 Supabase REST API。
  // Prefer: resolution=merge-duplicates 让同 email 二次提交不报错。
  try {
    const url = `${SUPABASE_URL.replace(/\/+$/, "")}/rest/v1/waitlist`;
    const r = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        apikey: SUPABASE_SERVICE_KEY,
        Authorization: `Bearer ${SUPABASE_SERVICE_KEY}`,
        Prefer: "resolution=merge-duplicates,return=minimal",
      },
      body: JSON.stringify({ email, lang, ip }),
    });
    if (!r.ok) {
      const text = await r.text().catch(() => "");
      console.error("[waitlist] supabase error", r.status, text);
      return res
        .status(500)
        .json({ ok: false, error: "server_error", detail: `supabase ${r.status}` });
    }
    return res.status(200).json({ ok: true });
  } catch (err) {
    console.error("[waitlist] fetch threw", err);
    return res.status(500).json({ ok: false, error: "server_error" });
  }
}
