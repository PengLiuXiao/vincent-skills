# 求职画像（profile.md）

把本模板复制到工作目录，改名为 `profile.md` 并如实填写。
Agent 读取 `profile.md` 与简历提取文本作为**唯一事实源**——缺什么就说不确定，绝不编造。
`profile.md` 含个人信息，不要提交进 git。

## Identity

- name:
- name_en: (可选)
- phone:
- email:
- city:
- wechat: (可选)

## Links

- resume_path: (主简历绝对路径)
- resume_doc_path: (可编辑版 .docx / .md，可选)
- portfolio: (作品集链接；打招呼语会自动附带邀请语+此链接)
- github: / linkedin: (可选)

## Target

- roles: (目标岗位，如 新媒体运营, 内容增长)
- level: (应届 / 1-3年 / 3-5年 / 高级)
- cities: (目标城市，如 深圳, 远程)
- salary_min: / salary_max:      # 用于匹配打分与排序
- job_types: (全职 / 实习 / 兼职)

## Preferences

- must_have: (如 双休; 明显不满足会强制降级)
- avoid: (如 纯外包; 触发即 C)
- languages: (如 中文, English)

## Experience summary

只写真实事实，逐段经历列出：

### 公司 — 职位 (YYYY-MM ~ YYYY-MM)

- 场景/项目：
- bullets:
  - …（动词 + 范围 + 结果，有数字写数字）
  - …

## Education

- 学校 — 学历 — 专业 — 年份

## Skills

- strong: …（能被简历首屏佐证的）
- familiar: …
- tools: …

## 证书 / 语言

- （如 CET-6、N2……评分时作为硬性项核对依据）

## Greeting style（打招呼语个人开关）

> 格式、三变体与轮换规则唯一来源：references/greeting.md。这里只放个人偏好覆盖。

- language: zh          # zh / en
- tone: professional
- max_chars_zh: 130     # 建议区间内上限参考（硬上限见 greeting.md ~180）
- must_avoid: 期望薪资
- prefer_metric: yes    # 只用简历上有的数字
