# 采集指南（输入契约 + Agent 采集模板 + 风控纪律）

本 skill **不内置爬虫**。采集由 Agent 在用户本机亲自执行（或用户的自有脚本执行），产物统一落到工作目录 `out/*.json`，再进入评分与落表流程。本文三部分：①产物契约、②可直接使用的采集 prompt 模板、③风控纪律。

> 法律与合规提示：Boss直聘条款禁止未授权抓取；采集仅限**个人求职**用途，低频、只读、单账号。请遵守平台条款与当地法律。

## 一、输入契约（所有模式共用）

无论用什么手段采集，最终产物必须是如下 JSON 文件：

```json
{
  "source": "search",
  "keyword": "新媒体运营",
  "city": "深圳",
  "fetchedAt": "2026-08-27T21:00:00+08:00",
  "riskInterrupted": false,
  "jobs": [
    {
      "company": "", "title": "", "salary": "", "link": "",
      "area": "", "experience": "", "education": "",
      "companyScale": "", "companyStage": "", "industry": "",
      "hrName": "", "hrTitle": "",
      "skills": [], "jd": ""
    }
  ]
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| source | ✅ | `search`（hunt 模式）或 `favorites`（收藏模式） |
| keyword | ✅ | 搜索词；收藏采集固定写 `收藏` |
| city | search 时建议 | 城市；favorites 可省略 |
| fetchedAt | ✅ | ISO 8601 时间戳 |
| riskInterrupted | ✅ | 中途遇风控终止时置 `true`；已落盘条目仍有效 |
| jobs[].company / title / salary / link | ✅ | 公司、岗位名、薪资原文、岗位链接——去重与落表都靠这四个 |
| jobs[].jd | 建议 | JD 全文；**空字符串 = 未取到详情（可能已下架），评估时跳过并在小结说明** |
| 其余字段 | 可选 | 地点/经验/学历/公司规模/融资阶段/行业/HR 姓名头衔/技能标签 |

- 文件命名：`out/search-<YYYYMMDDHHMM>.json` / `out/favorites-<YYYYMMDDHHMM>.json`
- 真实性：薪资等数字取平台返回原值，不要换算或修饰
- 只读边界适用于整个采集过程：绝不点击任何「立即沟通 / 发送 / 收藏 / 投递」按钮

## 二、采集 Prompt 模板

在独立 Chrome 进程里操作，打开 Boss直聘网页版。模板里的 `{...}` 由主流程替换后使用。

### search 模板

```text
用你的浏览器自动化能力（连接一个独立的真实 Chrome 进程，使用我已登录 zhipin.com 的会话，
不要 headless，不要用宿主内置浏览器）完成以下只读采集任务：

1. 打开 https://www.zhipin.com，确认登录态。
2. 搜索关键词「{keyword}」，城市选「{city}」，翻前 {pages} 页职位列表。
3. 对列表中每一条岗位进入详情页，记录 JD 全文；每两条详情之间随机等待 3–8 秒，
   本轮最多访问 {details} 条。
4. 全程只读：严禁点击「立即沟通」「发送」「收藏」「投递」等任何有副作用的按钮；
   不发任何消息。
5. 遇到以下任一情况立即停止采集、保留已收集数据并如实报告：
   出现安全验证/验证码页面、HTTP 403、接口返回 code=37「环境异常」、页面被重定向到验证流。
   不要尝试绕过或重试。
6. 把结果写入 {out_path}，JSON 结构必须完全符合：
   {"source":"search","keyword":"{keyword}","city":"{city}","fetchedAt":"ISO时间",
    "riskInterrupted":<bool>,
    "jobs":[{"company","title","salary","link","area","experience","education",
             "companyScale","companyStage","industry","hrName","hrTitle","skills":[],"jd"}]}
   详情没打开成功的条目 jd 写 ""，其余字段照常保留。
```

### favorites 模板

同上，改动第 2 步与 out 路径：

```text
2. 打开我账号的「收藏 / 感兴趣」职位列表（不执行站内搜索），
   尽量拉全列表，本轮最多对 {details} 条取详情；
   已知以下「公司|岗位」组合此前处理过，直接跳过不要进详情：{skip_list}
```

`skip_list` 来自两表已有记录的「公司|岗位」（见 modes-playbook favorites checklist）；没有就留空。

## 三、风控纪律

### 识别（四种形态）

| # | 形态 | 识别方式 |
|---|------|----------|
| 1 | 硬 403 | HTTP 状态码 |
| 2 | 软风控 · JSON | HTTP 200 但接口体 `code=37`「您的环境存在异常」 |
| 3 | 软风控 · 安全验证页 | HTTP 200 但渲染的是「安全验证」页 |
| 4 | IP 级拒连 | 页面/TLS 直接连不上，其他网站正常 |

消息正则兜底：`异常|验证|风控|频繁|拦截|限制`。

### 处理原则

1. **任何形态 → 终止本轮，不重试**。重试只会加重封锁。
2. 中断时已有部分数据落盘 → 置 `riskInterrupted: true`，**已落盘数据照常进入评估落表**，但不再继续抓。
3. 等待至少小时级，由**用户手动**在同一浏览器配置下打开 zhipin.com 完成一次安全验证即可恢复（通常无需重新登录）。
4. 解除后可补做轮次；表格中「评估日期」诚实写补做当天，不回填。

### 预算（保守值，宁少勿贪）

- 详情之间随机 3–8 秒拟人节奏；单轮详情上限默认 15（`config.yaml collection.details_per_round`）
- 短时间内多轮高密度抓取是已知的触发路径
- 收藏通道通常比搜索通道耐受性好，但同一原则适用

## 工具选型原则（给配环境的用户）

- 用 Playwright / Puppeteer / Selenium 等**独立进程**驱动一台**真实系统 Chrome**（带用户自己的 profile 目录，保持人工登录态）
- **不要用宿主应用的内置浏览器**直接开 zhipin.com——嵌入式 WebView 对该站极不稳定，已有导致宿主应用崩溃的实证
- 单账号、低频、只读；不要上代理池/云主机 IP——住宅 IP + 拟人节奏是仅有的安全姿势
