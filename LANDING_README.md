# 故知 · Landing Page 发布手册

`landing.html` 已经生成。这份文档讲两件事:
1. **怎么让 waitlist 表单真的能收 email**(三个免代码方案)
2. **怎么把这页发出去让别人看到**(域名、托管、第一波推广)

---

## 一、Waitlist 表单接入

`landing.html` 里的表单 `action` 现在是 `REPLACE_WITH_FORM_ENDPOINT`。
你需要替换成下面三个服务里**任意一个**的 endpoint URL。

### 方案 A:Formspree(推荐 — 最简单)

**步骤:**
1. 去 https://formspree.io ,免费注册
2. 点 New Form,起个名("Guzhi Waitlist")
3. 它会给你一个 URL,长这样:`https://formspree.io/f/xxxxxxxx`
4. 把 `landing.html` 第 391 行的 `REPLACE_WITH_FORM_ENDPOINT` 替换成这个 URL
5. 试着在自己页面提交一次,Formspree 会发邮件到你注册的邮箱确认表单激活

**收到的 email 在哪看:**
- Formspree 后台 → 你的 form → Submissions
- 每次有新 email 进来,Formspree 自动转发到你注册邮箱
- 可以导出 CSV

**限额:**
- 免费版 50 条/月。够你测试早期 demand。
- 超过了可以升级,或者改成自建邮件接收

---

### 方案 B:Tally(推荐 — 体验最好)

**步骤:**
1. 去 https://tally.so ,免费注册
2. 新建 form,加一个 email 字段
3. Tally 提供两种接入方式:
   - **iframe 嵌入**:把 Tally 生成的 form 直接嵌进 landing.html
   - **API endpoint**:类似 Formspree,改 action URL

**对你的优势:**
- 免费版无条数限制
- 自带后台、邮件通知
- 如果你想换成更长的表单(加"最近在想什么")很简单

**对当前 landing 的小麻烦:**
- 你已经写好的诗意表单要换掉,可能视觉风格不一致

如果你将来想加更多字段问用户问题,Tally 比 Formspree 强。

---

### 方案 C:Google Form(最保守)

**步骤:**
1. 去 https://forms.google.com 新建 form,加一个 email 字段
2. 点击 Send → 复制链接,在 landing 的 waitlist 处改成"加入名单"按钮链接到 Google Form
3. 这样会跳出 landing 页面到 Google Form,体验**不如** A 和 B

**唯一的好处:** Google Sheets 自动汇总,完全免费、无限制。

**建议**:**用 Formspree(A)**——最快、对你现有页面侵入最小。

---

## 二、把这页发出去

### Step 1:本地预览

```sh
cd /Users/zouzeren/workspace/Guzhi
open landing.html
```

直接在浏览器看效果。注意 demo 链接(poc/viz/guzhi_town.html)需要保持相对路径,所以**部署时要把 poc/ 目录也带上**(或者改链接指向其他地方)。

### Step 2:挑域名

回到我前面给你的 8 个公司名候选:

- **如果用「故知」**:`guzhi.app` / `guzhi.co` / `guzhi.io` 是好选择;`.com` 几乎肯定被占
- **如果用「重逢」**:`chongfeng.app` 概率较高
- **如果用「寻光」**:`seeklight.com` 可能要查 — 我不能替你查注册情况,你去 https://www.namecheap.com 或 https://www.cloudflare.com/products/registrar/ 查

**新加坡用户买域名**:Namecheap / Cloudflare Registrar / GoDaddy 都行。Cloudflare 最便宜且不加价。

### Step 3:挑托管

三个免费/低成本方案:

| 方案 | 优势 | 劣势 |
|---|---|---|
| **Vercel** | 一键部署 GitHub repo;自动 HTTPS;速度快;你之前做的 POC 也可以一起挂 | 需要 GitHub 账号 |
| **Netlify** | 同 Vercel,稍微好上手一点 | 同 |
| **Cloudflare Pages** | 和 Cloudflare 域名打通;速度最快 | UI 略复杂 |
| **GitHub Pages** | 完全免费 | 自定义域名稍麻烦 |

**推荐 Vercel**:
1. 把 `/Users/zouzeren/workspace/Guzhi` 整个文件夹上传到 GitHub(新 repo,可以叫 `guzhi-landing`)
2. 去 https://vercel.com,用 GitHub 登录,Import 这个 repo
3. Vercel 自动检测,30 秒部署完
4. 拿到一个 `xxx.vercel.app` 域名,后面再绑你买的 `guzhi.app`

### Step 4:接 waitlist(见上面方案 A)

部署完成之后再做这一步,因为本地预览时 Formspree 也能用,但绑定到真实域名才能让别人提交。

### Step 5:第一波推广(早期种子用户)

**你的目标不是 1000 个 email,是 30-50 个"对的人"的 email。**

试这几个渠道(按 ROI 排):

1. **你自己的朋友圈 / X / LinkedIn**(成本: 0)
   - 不要 spam 朋友,挑 5-10 个你觉得会对"故知"主题真有共鸣的人,**一对一**发链接,问 ta 觉得这是什么
   - 这些 feedback 比 100 个陌生人的注册更值钱

2. **小红书**(成本: 0,周期: 7 天)
   - 不要 hard-sell。写一篇"我在想一个新的相遇方式"的随笔,把 landing 放在评论区
   - 你之前写过 designdoc 那种文笔,这件事你很会

3. **即刻 App**(成本: 0)
   - 即刻的"独立开发者"圈很活跃,愿意试 demo,会给反馈
   - 发一条"做了一个反 Tinder 的 AI 相遇 demo",带链接

4. **Hacker News / Show HN**(成本: 0,但要小心)
   - **如果你打算挂 HN**,landing 必须是英文版,而且要强调 KG-First 架构(技术读者吃这个)
   - 现在的中文 landing 不适合 HN
   - 这个等 Phase 2 再考虑

5. **不要**做的:
   - 不要花钱投广告(Phase 1 阶段,你不知道哪种文案有效,投了浪费钱)
   - 不要 cold email B2C(你之前提到的 cold outbound 流程不适用这阶段)
   - 不要 Twitter/X 自动化跟人(会被 ban)

---

## 三、第一周看什么数据

写完不是结束。**第一周内你应该有的指标:**

| 指标 | 目标 | 不达标的话 |
|---|---|---|
| **页面访问量** | 50+ | 推广渠道选错了 |
| **页面停留时间** | 中位数 > 30 秒 | 文案太长 / 太短,用户不读 |
| **Waitlist 注册数** | 5-15 | 转化路径不清晰,需要改 CTA |
| **来自朋友的真实反馈** | 至少 3 条具体的(不是"挺好的") | 你的圈子可能不是 ICP |

**这四个数字里,最重要的是最后那条:具体反馈。** 数字再漂亮,如果没人能用 50 个字告诉你 "我懂你做的是什么、我觉得这个对/不对",你就还没找到 product-market fit 的信号。

---

## 四、什么时候启动 Phase 2(B2B)

**条件**(满足任何一个):
1. Waitlist 收到 100+ 真实邮箱,且至少 5 个人主动联系你想了解更多
2. **或者**:你跟 5 个真实早期用户聊过,确认他们愿意为这个产品付费(或愿意推荐给朋友)

**满足之前不要做 B2B**。因为 B2B 引擎卖点是 "我们这套引擎在 C 端跑出过 X 用户、Y 留存"——
没有 C 端数据,你给 HR 招聘平台讲 KG-First 是没说服力的。

启动 Phase 2 时,我再来帮你写:
- B2B landing(讲技术、讲案例、讲集成成本)
- Lead sourcing 思路(怎么找到 HR 决策者的邮箱)
- Cold outbound email + cold call script(中英文都行)
- 第一通 demo call 的 5 个常见反对意见怎么答

---

## 五、文件清单

```
Guzhi/
├── landing.html              ← 你要发的 landing 主页
├── LANDING_README.md         ← 你正在看的这份手册
└── poc/                       ← 已有的 POC(landing 会链接到这里的可视化)
    ├── viz/
    │   ├── guzhi_town.html   ← 像素小镇 demo
    │   └── guzhi_viz.html    ← 网络图 demo
    └── ... (其余 POC 代码)
```

---

*Made for the Phase 1 launch. Stay slow.*
