# Deploy · 故知 landing + waitlist endpoint

部署到 **Vercel** + **Supabase**。10 分钟一次搞定。

---

## 1. Supabase 建表（一次性）

1. 去 [supabase.com](https://supabase.com) 新建一个 project（免费档够用）
2. SQL Editor → New query → 粘下面这段 → Run

```sql
create table waitlist (
  id          bigserial primary key,
  email       text not null unique,
  lang        text,
  ip          text,
  created_at  timestamptz not null default now()
);

-- RLS:开,但只让 service_role 写。前端的 anon key 不能读不能写
alter table waitlist enable row level security;

-- 不加 policy ——  service_role 自动绕开 RLS
-- 这样：endpoint 用 service key 能写,任何用 anon key 的客户端都读写不了
```

3. Project Settings → API → 复制：
   - **Project URL**（形如 `https://abcd.supabase.co`）
   - **service_role key**（**不是** anon key —— 服务端用的，权限大，永远不要前端用）

---

## 2. Vercel 部署

### 第一次

```bash
cd /Users/zouzeren/workspace/Guzhi
npm install        # 装 @supabase/supabase-js + @vercel/node
```

然后选下面一种：

**A. CLI 一把推（推荐第一次）**

```bash
npm i -g vercel
vercel login
vercel              # 跟引导一路 enter
```

**B. GitHub 集成（之后的迭代用这个）**

把整个 `/Users/zouzeren/workspace/Guzhi` 推到 GitHub repo → vercel.com → New Project → Import 那个 repo。

### 配环境变量

Vercel Dashboard → Project → Settings → Environment Variables → 加两条：

| Name | Value |
|---|---|
| `SUPABASE_URL` | 第 1 步复制的 Project URL |
| `SUPABASE_SERVICE_KEY` | 第 1 步复制的 service_role key |

加完点 Redeploy（让新 env 生效）。

---

## 3. 验证

部署完会拿到一个 `your-project.vercel.app`。

```bash
# 1) Landing 能开
open https://your-project.vercel.app/

# 2) API 能 ping
curl -X POST https://your-project.vercel.app/api/waitlist \
  -H 'Content-Type: application/json' \
  -d '{"email":"test@example.com","lang":"zh"}'
# 期望: {"ok":true}

# 3) Supabase 后台 → Table editor → waitlist 表能看到那一行
```

---

## 4. 失败的提示分别意味着什么

| 浏览器看到 | 真实情况 |
|---|---|
| "收到了。你在。" | 写入成功（或之前就有同邮箱也算成功） |
| "暂时收不到。过会儿再试一次。" | 4xx / 5xx / 网络掉线。常见原因：env 没配好、Supabase 表没建、域名 CORS 异常 |

服务端能在 Vercel Logs 看到具体错误 (`SUPABASE_SERVICE_KEY missing` / `Supabase insert error: ...`)。

---

## 5. 域名（可选）

Vercel Dashboard → Domains → 加自定义域名（例如 `guzhi.app`）。
DNS 配置 Vercel 会给提示。

---

## 6. 本地预览的 caveat

直接双击 `landing.html` 用 `file://` 打开**不能跑 waitlist**（没 endpoint）。但小镇 demo、letters 都能跑。

如果要本地完整试：

```bash
npm i -g vercel
vercel dev    # 本地起 dev server,api 也能跑（需要本地 .env.local 配同样的 env）
```

`.env.local` 内容：

```
SUPABASE_URL=https://abcd.supabase.co
SUPABASE_SERVICE_KEY=ey...service_key...
```

`.env.local` 永远不要提交到 git。

---

## 7. 给未来自己的一句话

如果以后想给 waitlist 加 double-opt-in（用户点确认邮件链接才真入名单），最省事的做法是：

- 在 `waitlist` 表加 `confirmed boolean default false` 字段
- 写一个 `/api/confirm?token=...` endpoint 用 token 翻 confirmed 状态
- 用 Supabase Auth Email 或 Resend 发确认邮件

但现阶段没必要。先收着,等真要给 30 人发第一镇邀请的时候再做。
