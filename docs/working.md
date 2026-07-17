# Working Notes

## Changelog

### 2026-07-17

- 澄清 hosted integration 的 identity/lifetime 边界：OAuth attempt 绑定短期 authenticated session，长期 credential 绑定稳定 owner，模型请求逐次验证 session-to-owner authorization。
- 记录 legacy session-bound AEAD credential 的迁移要求：必须先用旧 session AAD 解密，再以 owner AAD rewrap，不能只改数据库 ownership 字段。

### 2026-07-16

- 建立 public-ready 独立 skill scaffold：中文 root skill、PRD/RFC/test、Python package、CLI、tests 和 public scan。
- 选择 Python 标准库实现 browser PKCE、localhost callback、token exchange/refresh、明文 `0600` JSON storage 和最小 Codex Responses request，不引入 OAuth SDK 或前端。
- 明确 compatibility 边界：参考 OpenCode MIT implementation，不宣称 OpenAI 官方第三方 OAuth contract；生产系统不得照搬明文 storage。
- 默认离线验证通过：16 tests、Ruff、CLI help 与 public-content scan 全部通过。
- macOS 上正在运行的 owner Workbench 占用 IPv6 `::1:1455`，Python callback 仍可独立绑定 IPv4 localhost 完成授权；未停止或重启现有 Workbench。
- 自定义 token path smoke 暴露 existing parent chmod bug：初版会尝试把 `/tmp` 等既有父目录改成 `0700`。现已改为只 chmod 本实现新建的私有目录，并增加权限不变回归测试；该次 OAuth token 未成功写盘。
- 首次完整 live demo 已完成 OAuth 和默认明文 token 落盘，但 request 返回 `Stream must be set to true`。据此将最小 transport 改为 SSE `stream:true`，增加 delta/completed/error event parsing 与回归测试。
- 修复 SSE transport 后复用落盘 token 完成真实 Codex request，stdout 严格返回 `OK`；`status --json` 只显示 metadata，token 目录权限为 `0700`、文件权限为 `0600`。
- 独立 review 修复五项边界：SSE partial+failure 不再误报成功且必须看到 `response.completed`；repo-local token 示例加入 ignore；错误/错 state callback 不再提前终止有效 attempt；默认 token 目录每次收紧到 `0700`；public scan 覆盖 extensionless 与隐藏文本文件。

## Lessons Learned

- Codex Responses transport 必须显式 `store:false`；多步 reasoning 还要保存/replay encrypted reasoning，不能引用未持久化 item ID。
- refresh token 可能 rotation。持久化时必须原子替换完整 token bundle，而不是只更新 access token。
- localhost OAuth callback port 是 redirect contract 的一部分。端口冲突应明确失败，不能静默改成随机端口。
