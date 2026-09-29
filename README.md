# ChatGPT OAuth Skill

这是一个中文 AI skill 与最小 Python reference implementation，用来解释和演示：本地程序如何打开浏览器完成 ChatGPT/Codex subscription OAuth，如何理解和刷新 token，以及如何用 subscription credential 发送 Codex Responses 请求（支持返回 `OK` 或任意文本，并支持指定速度档位与用量/耗时测量）。

它不需要 OpenAI API key，也没有前端。Python CLI 在 `localhost:1455` 临时监听 OAuth callback，授权完成后把 token 明文写入：

```text
~/.chatgpt_oauth/token.json
```

这是故意采用的教学设计，不是生产安全建议。文件权限设为 `0600`，但 token 内容仍是明文。生产系统应改用 OS Keychain、encrypted secret store 或 application-level envelope encryption。

## 重要边界

本项目不是 OpenAI 官方 SDK。它参考 OpenCode 的 MIT-licensed ChatGPT/Codex integration，使用公开 OAuth client identity 和未承诺为稳定第三方 contract 的 Codex backend。OpenAI 可以改变 endpoint、模型、header 或授权行为。只应将它用于个人学习、兼容性验证和 owner-controlled tooling，不应直接扩展成多用户 SaaS。

## 安装

```bash
git clone https://github.com/grapeot/chat-gpt-oauth-skill chat_gpt_oauth
cd chat_gpt_oauth
uv venv .venv
uv pip install --python .venv/bin/python -e '.[dev]'
```

## 最短 Demo

```bash
.venv/bin/chatgpt-oauth demo
```

CLI 会：

1. 明确提示 token 将以明文保存及其绝对路径。
2. 启动 `http://localhost:1455/auth/callback`。
3. 打开系统浏览器，让用户在 OpenAI 页面授权。
4. 校验 OAuth `state`，使用 PKCE verifier 换取 token。
5. 将完整 token bundle 写入 `~/.chatgpt_oauth/token.json`，权限设为 `0600`。
6. 必要时 refresh access token，然后调用 Codex Responses，要求模型只返回 `OK`。

也可以拆开运行：

```bash
.venv/bin/chatgpt-oauth login
.venv/bin/chatgpt-oauth status
.venv/bin/chatgpt-oauth request --prompt '请只回复 OK，不要添加其他文字。'
.venv/bin/chatgpt-oauth logout
```

如果不希望 CLI 自动打开浏览器：

```bash
.venv/bin/chatgpt-oauth login --no-open
```

## Token 文件

明文 JSON 包含：

```json
{
  "schema_version": 1,
  "access_token": "<redacted>",
  "refresh_token": "<redacted>",
  "id_token": "<redacted>",
  "expires_at": 1780000000,
  "account_id": "<redacted>",
  "scope": "openid profile email offline_access"
}
```

- `access_token`：短期 bearer credential。只放在请求的 `Authorization` header，不能当用户 ID。
- `refresh_token`：在 access token 过期时换取新 token。它通常寿命更长、权限更敏感，而且可能每次 refresh 都旋转；保存新值时必须原子替换旧值。
- `id_token`：OIDC 身份声明 JWT。reference implementation 只从中提取 account ID，不把它当 API bearer token。
- `expires_at`：CLI 根据 `expires_in` 计算的本地 Unix timestamp，不是 OAuth server 直接返回的 token。
- `account_id`：从可信 token response 内的 JWT claims 提取，请求 Codex backend 时放入 `ChatGPT-Account-Id` header。
- `scope`：授权范围记录。它描述 consent，不替代服务端权限检查。

OAuth authorization code、PKCE verifier 和 `state` 只在单次登录过程中存在，不写入 token 文件。code 只能兑换一次；verifier 证明发起授权与兑换 code 的程序相同；state 用于阻止 callback CSRF/串线。

## 给 AI Agent 安装 Skill

把 `https://github.com/grapeot/chat-gpt-oauth-skill` 交给 Codex、Claude Code、Cursor、OpenCode 或其他 coding agent，并要求它：

1. 先阅读目标 workspace 的 `AGENTS.md`、`CLAUDE.md` 或 routing 文档。
2. 将 [`skills/chat_gpt_oauth.md`](skills/chat_gpt_oauth.md) 放入该 workspace 的 skill discovery chain。
3. 如果 workspace 有 `skills/INDEX.md` 或 `rules/skills/INDEX.md`，添加一个指向 root skill 的条目；否则在 `AGENTS.md` 或 `CLAUDE.md` 中添加短指针。

只暴露这一个 root skill。reference implementation、RFC 和测试继续留在 repo 内，由 root skill 按需引用。

## 开发与验证

```bash
.venv/bin/python -m pytest -v
.venv/bin/ruff check .
.venv/bin/python scripts/check_public.py
```

默认测试完全离线，不访问 OpenAI，也不读取真实 token 文件。真实 OAuth 与 Codex 请求支持显式发起的 `demo`、`login` 与 `request`。

架构与生产边界见 [`docs/rfc.md`](docs/rfc.md)，Agent 使用 contract 见 [`skills/chat_gpt_oauth.md`](skills/chat_gpt_oauth.md)。

## 速度档位、长文本与测量结果

### 命令行请求

CLI 支持如下请求参数：

- `--service-tier`：可选 `default`、`fast`、`priority`、`ultrafast`，默认显式使用 `default`。协议层将 `fast` 映射为 `priority`。
- `--reasoning-effort`：可选 `low`、`medium`、`high`、`xhigh`、`max`、`ultra`。
- `--prompt-file`：指定提示词文件路径。
- `--timeout`：套接字超时时间（秒，默认 600，并非整请求超时）。

全局 `--json` 控制输出结构。默认仅打印文本回答；添加 `--json` 输出结构化数据，包含 `answer`、请求参数（`requested_model`、`requested_service_tier`、`reasoning_effort`）、服务端实际返回（`model`、`service_tier`、`status`、`usage`）及 `timing` 指标（`total_seconds`、`first_event_seconds`、`first_text_seconds`、`last_text_seconds`、`completed_seconds`）。若服务端未返回实际 tier 或 usage 则保持 `null`，不根据请求参数推断。

计时统计始于凭据准备完毕、网络请求发出之前，底层通过增量 SSE 流式读取；TTFT（`first_text_seconds`）以首个非空 `output_text.delta` 为准，不会把 reasoning 事件误当成首个响应文本；等待响应文本前的推理时间仍包含在 TTFT 中。

示例命令：

```bash
.venv/bin/chatgpt-oauth --json request --model gpt-6-astra --service-tier fast --reasoning-effort xhigh --prompt-file article_prompt.txt
```

### Python API

- `request_text`：返回纯文本回答。
- `request_result`：返回结构化字典。支持可选参数 `tokens=TokenBundle`，直接使用内存托管凭据，不读取或刷新本地 token store，由调用方自行维护生命周期与过期时间。

实测数据与限制见 [速度基准测试](docs/speed_benchmark_20260929.md)。
