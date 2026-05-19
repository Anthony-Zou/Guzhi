/**
 * GET /api/ping
 *
 * 最小函数,零外部依赖。用来隔离测试:
 * - 如果它能跑 → Vercel function 配置 OK,问题在 waitlist 的具体依赖
 * - 如果它也 500 → Vercel function 本身配置有问题 (TS 编译、runtime 等)
 */
import type { VercelRequest, VercelResponse } from "@vercel/node";

export default function handler(req: VercelRequest, res: VercelResponse) {
  res.status(200).json({
    ok: true,
    runtime: "node",
    method: req.method,
    has_supabase_url: !!process.env.SUPABASE_URL,
    has_supabase_key: !!process.env.SUPABASE_SERVICE_KEY,
    supabase_url_starts: process.env.SUPABASE_URL?.slice(0, 12) ?? null,
    supabase_key_len: (process.env.SUPABASE_SERVICE_KEY ?? "").length,
  });
}
