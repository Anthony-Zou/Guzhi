/**
 * GET /api/waitlist_count
 *
 * 返回 waitlist 表行数。
 * 用 Supabase REST 的 HEAD + Prefer: count=exact 拿 Content-Range。
 *
 * 响应 200 { count: number }
 *
 * 不暴露具体邮箱、不暴露其它字段。前端用这个值决定显示与否
 * (例如 < 30 时藏起来,不让"没什么人"的状态自我应验)。
 */

import type { VercelRequest, VercelResponse } from "@vercel/node";

export default async function handler(req: VercelRequest, res: VercelResponse) {
  if (req.method !== "GET") {
    return res.status(405).json({ error: "method_not_allowed" });
  }

  const SUPABASE_URL = process.env.SUPABASE_URL;
  const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_KEY;
  if (!SUPABASE_URL || !SUPABASE_SERVICE_KEY) {
    return res.status(500).json({ error: "server_misconfigured" });
  }

  try {
    const url = `${SUPABASE_URL.replace(/\/+$/, "")}/rest/v1/waitlist?select=*`;
    const r = await fetch(url, {
      method: "HEAD",
      headers: {
        apikey: SUPABASE_SERVICE_KEY,
        Authorization: `Bearer ${SUPABASE_SERVICE_KEY}`,
        Prefer: "count=exact",
        // 不需要 body,只要 Content-Range header
        Range: "0-0",
      },
    });
    if (!r.ok && r.status !== 206) {
      // 206 Partial Content 也是预期的(因为我们用了 Range)
      console.error("[waitlist_count] supabase", r.status);
      return res.status(500).json({ error: "server_error" });
    }
    // Content-Range: "0-0/N" 或 "*/N"
    const cr = r.headers.get("content-range") || "";
    const m = cr.match(/\/(\d+)$/);
    const count = m ? parseInt(m[1], 10) : 0;

    // 缓存 60 秒,减少 Supabase 调用
    res.setHeader("Cache-Control", "public, max-age=60, s-maxage=60");
    return res.status(200).json({ count });
  } catch (err) {
    console.error("[waitlist_count] threw", err);
    return res.status(500).json({ error: "server_error" });
  }
}
