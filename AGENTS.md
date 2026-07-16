# ChatGPT OAuth Skill

## 目标

这是一个面向公开 GitHub 的中文 skill 与最小 Python reference implementation。它解释并演示 ChatGPT/Codex subscription OAuth、localhost PKCE、token refresh 和 private Codex Responses transport。

## 结构

- `skills/chat_gpt_oauth.md`：唯一 root skill，面向 AI agent。
- `src/chat_gpt_oauth/`：OAuth、明文 token storage、Responses request 与 CLI。
- `tests/`：默认 offline tests，不联系 OpenAI。
- `docs/`：PRD、RFC、测试策略和 working log。
- `scripts/chatgpt-oauth`：从 repo root 执行的 thin wrapper。

## 工程约束

- Python 3.11+；本地依赖使用 `.venv` 和 `uv pip install`。
- 默认只使用 Python 标准库。新增 runtime dependency 前先证明标准库无法清晰完成。
- 每次实质修改更新 `docs/working.md`。
- 默认测试必须离线；真实 OAuth/request 必须显式运行，不进入 CI。
- 错误信息保留 HTTP status 和有限 response snippet，但绝不输出 access/refresh/id token。

## Public Repo 约束

- 不提交 `.env`、token cache、日志、真实 account ID、真实 OAuth response 或 live request artifact。
- 所有 fixture 使用 fake JWT/token/domain；`.env.example` 只放假值或非敏感默认值。
- `~/.chatgpt_oauth/token.json` 是故意采用的明文教学存储，不得改到 repo 内；CLI 必须持续明确提示路径与风险。
- 不能把本项目描述成 OpenAI 官方支持的第三方 OAuth SDK。它是基于 OpenCode MIT implementation 的 compatibility reference，相关 endpoint/client identity 可能变化。

## 验证

```bash
.venv/bin/python -m pytest -v
.venv/bin/ruff check .
.venv/bin/python scripts/check_public.py
```

live acceptance 只在 owner 明确执行时运行：

```bash
.venv/bin/chatgpt-oauth demo
```
