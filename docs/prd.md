# PRD：ChatGPT OAuth Skill

## 产品定义

为 AI coding agent 和开发者提供一个中文、public-ready 的 ChatGPT/Codex OAuth skill。它既解释关键协议与安全边界，也提供可运行的最小 Python 实现，让读者从浏览器授权一直走到真实 Responses request，而不是停留在伪代码。

## 用户

- 想让本地 AI tool 使用自己的 ChatGPT Plus/Pro subscription，但不想使用 OpenAI API key 的开发者。
- 需要把 OpenCode-style Codex OAuth integration 移植到另一个 owner-controlled harness 的 Agent 工程师。
- 需要理解 token lifecycle、refresh rotation 和 account header 的 AI agent。

## V0 需求

- 中文 root skill，解释 OAuth PKCE、每类 token、refresh、account ID 和 transport。
- Python 3.11+ 标准库 reference implementation，无前端、无 OAuth SDK。
- 默认打开系统浏览器，localhost callback 固定在 1455。
- token 按用户要求明文写入 repo 外 JSON，并明确打印路径与风险。
- CLI 至少提供 login、status、request、demo、logout。
- request 使用 ChatGPT/Codex subscription credential，默认要求严格返回 `OK`。
- 默认 tests 完全离线；live acceptance 显式 opt-in。
- 明确披露 private/unsupported compatibility contract，不冒充 OpenAI 官方 SDK。

## 非目标

- 多用户 Web OAuth service。
- 加密 secret store、Keychain UI 或 hosted callback。
- 通用 OpenAI API client、chat UI、Agent harness 或模型选择器。
- 绕过 subscription 权限、共享 token、自动注册 OAuth client。
- 保证 undocumented endpoint 永久稳定。

## 成功标准

- 新用户只需安装 package 并运行一个 `demo` 命令，就能看到浏览器授权、准确 token path 和最终 `OK`。
- Agent 只读 root skill 就能正确区分三类 token，并实现不泄漏 credential 的 transport。
- offline tests 能验证 PKCE、state、JWT claim extraction、明文权限、refresh rotation 与 request contract。
- public scan 不发现真实 credential、内部路径或 private vault reference。
