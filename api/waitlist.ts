/**
 * POST /api/waitlist
 *
 * 收一个 email,写到 Supabase 的 waitlist 表。
 * Vercel Serverless Function (Node 20 runtime).
 *
 * 期望请求体: { email: string, hp?: string, lang?: 'zh' | 'en' }
 *
 * 响应:
 *   200 { ok: true } 邮箱已记录 (或之前就在)
 *   400 { ok: false, error: 'invalid_email' | 'spam' } 校验失败
 *   500 { ok: false, error: 'server_error' }
 *
 * 环境变量 (Vercel Dashboard → Project Settings → Environment Variables):
 *   SUPABASE_URL         例如 https://abcd.supabase.co
 *   SUPABASE_SERVICE_KEY service_role key (不是 anon key —— 服务端用)
 *
 * Supabase 表 schema (一次性建,见 SETUP.md):
 *   create table waitlist (
 *     id        bigserial primary key,
 *     email     text not null unique,
 *     lang      text,
 *     ip        text,
 *     created_at timestamptz not null default now()
 *   );
 */

import { createClient } from "@supabase/supabase-js";
import type { VercelRequest, VercelResponse } from "@vercel/node";

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_KEY;

// 简单 email 校验:够用,不和库扯
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default async function handler(req: VercelRequest, res: VercelResponse) {
  // CORS:同源没事;如果以后 landing 在别的域,放宽这里
  if (req.method === "OPTIONS") {
    res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type");
    return res.status(204).end();
  }
  if (req.method !== "POST") {
    return res.status(405).json({ ok: false, error: "method_not_allowed" });
  }

  if (!SUPABASE_URL || !SUPABASE_SERVICE_KEY) {
    console.error("Supabase env vars missing");
    return res.status(500).json({ ok: false, error: "server_misconfigured" });
  }

  const body = (req.body ?? {}) as {
    email?: unknown;
    hp?: unknown;
    lang?: unknown;
  };

  // Honeypot:正常用户不会填 hp 字段。有值就当 spam 静默放弃
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

  // Vercel 给的真实 IP
  const ipHeader = req.headers["x-forwarded-for"];
  const ip = Array.isArray(ipHeader)
    ? ipHeader[0]
    : (ipHeader ?? "").split(",")[0]?.trim() || null;

  const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY, {
    auth: { persistSession: false },
  });

  const { error } = await supabase
    .from("waitlist")
    .upsert(
      { email, lang, ip },
      { onConflict: "email", ignoreDuplicates: true },
    );

  if (error) {
    console.error("Supabase insert error:", error);
    return res.status(500).json({ ok: false, error: "server_error" });
  }

  return res.status(200).json({ ok: true });
}
