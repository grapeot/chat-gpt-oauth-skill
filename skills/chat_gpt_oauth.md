# ChatGPT/Codex OAuth Skill

## 何时使用

当用户需要理解、实现或排查以下能力时加载本 skill：

- 用 ChatGPT Plus/Pro subscription OAuth，而不是 OpenAI API key，授权本地 owner-controlled tool。
- 实现 localhost browser PKCE callback、token exchange、refresh rotation。
- 理解 access token、refresh token、ID token、account ID 和 scope 的边界。
- 将 OAuth credential 接到 Codex Responses compatibility transport。
- 运行本 repo 的最小 reference implementation，验证最终返回 `OK`。

## 目标与边界

成功结果不是拿到三个 token 就结束，而是建立一条可审计的 credential lifecycle：用户在可信 OpenAI 页面授权；callback 严格校验 `state`；code 只与原 PKCE verifier 一起兑换；token 存储位置和保护级别对用户透明；请求前检查 expiry 并正确处理 refresh rotation；模型请求只携带 access token 与 account ID，不泄漏 refresh/ID token。

本 skill 不把该流程描述成 OpenAI 官方第三方 OAuth contract。它基于 OpenCode 的 MIT-licensed compatibility implementation。public client identity、private Codex endpoint、可用模型和 header 都可能变化。不要把 reference implementation 直接推广成多用户 SaaS，也不要承诺 subscription OAuth 比官方 OpenAI API 稳定。

## Reference Implementation

从 repo root 运行：

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e '.[dev]'
.venv/bin/chatgpt-oauth demo
```

默认行为：

- 在 `localhost:1455` 启动临时 callback server。
- 打开系统浏览器完成 ChatGPT/Codex authorization code + PKCE flow。
- 将 token 明文保存到 `~/.chatgpt_oauth/token.json`，默认目录权限 `0700`、文件权限 `0600`。
- 打印明文风险和准确路径，但永不把 token value 输出到 terminal。
- 调用 Codex Responses endpoint，并要求模型只返回 `OK`。

分步命令：

```bash
.venv/bin/chatgpt-oauth login
.venv/bin/chatgpt-oauth --json status
.venv/bin/chatgpt-oauth request --prompt '请只回复 OK，不要添加其他文字。'
.venv/bin/chatgpt-oauth logout
```

需要改 token 文件位置时使用全局参数：

```bash
.venv/bin/chatgpt-oauth --token-path ./local-token.json status
```

不要把 repo 内路径作为长期 token 默认值。`--token-path` 主要用于隔离测试；正常运行应把 credential 放在 repo 外。自定义路径始终把文件设为 `0600`，但不会擅自修改已经存在的父目录权限。

## Token 语义

| 字段 | 能做什么 | 不能拿它做什么 |
|---|---|---|
| `access_token` | 短期 bearer credential；放入 `Authorization: Bearer ...` | 不等于用户 ID；不应写日志、prompt、artifact 或浏览器 storage |
| `refresh_token` | access token 临近过期时换取新 token | 不发送给 Codex Responses；不能假设永不旋转 |
| `id_token` | OIDC 身份声明；可解析可信 token response 中的 account claim | 不是 Codex API bearer credential；只 decode 不等于验证任意来源 JWT |
| `account_id` | 放入 `ChatGPT-Account-Id`，选择 subscription account | 不应从用户输入或未验证的任意 JWT 猜测 |
| `scope` | 记录授权 consent 范围 | 不代表 backend 一定允许某个模型或 endpoint |
| `expires_at` | 本地根据 `expires_in` 计算何时 refresh | 不应仅依赖 wall clock 后继续使用已被 server revoke 的 token |

authorization code、PKCE verifier、challenge 和 state 不属于长期 token bundle。code 是单次短期凭据；verifier 是本地随机秘密；challenge 是 verifier 的 SHA-256 base64url 投影；state 把 callback 绑定到发起它的 login attempt。

## Integration Invariants

任何实现都应维持以下结果：

- OAuth authorize URL 使用 `code_challenge_method=S256`，callback 必须同时验证 code 与 constant-time state equality。
- localhost callback 只监听本机，五分钟内未完成就关闭；端口冲突时明确报错，不随机换端口，因为 redirect URI 属于 public client contract。
- token response 做结构验证。缺少 access token、refresh token 或 account ID 时 fail closed。
- refresh 在过期前进行；新 token response 原子替换旧 token，refresh response 未返回新 ID token/account claim 时才保留已知 metadata。
- 并发或多实例生产系统需要 refresh lease/single-flight + version compare-and-swap；本地单进程 reference 不声称解决分布式 rotation。
- Codex request 只允许预期 Responses endpoint，替换任何 placeholder `Authorization`，设置 `ChatGPT-Account-Id`，并使用 backend 要求的 SSE `stream:true`。
- Responses 使用 `store:false`。多步 reasoning integration 还必须请求并 replay `reasoning.encrypted_content`，不能引用未持久化的 reasoning item ID。
- credential 不进入 model prompt、tool output、event payload、artifact、analytics 或错误日志。

## 明文存储边界

本 reference implementation 按用户要求使用明文 JSON，目的是让 token lifecycle 可观察。`0600` 只限制其他 Unix 用户，不能抵御同一用户下的恶意进程、备份同步、终端录屏或误上传。

面向真实产品时，把 `storage.py` 替换为以下任一方案，OAuth 与 transport contract 不需要变化：

- macOS Keychain、Windows Credential Manager、Linux Secret Service。
- 只在本机运行的 encrypted file store，master key 留在 OS keychain。
- Server-side encrypted database，使用 AES-GCM envelope、独立 AAD、rotation version 和 revoke metadata。

## 验收标准

- `login` 打开浏览器，callback state mismatch 会失败，成功后明确报告 token file 路径。
- token file 包含完整教学字段，权限为 `0600`，Git 不跟踪该路径。
- `--json status` 只输出 metadata，不包含任何 token value。
- access token 临近过期时，下一次 `request` 会 refresh 并保存 rotated refresh token。
- `request` 的 body 包含 `store:false`，header 包含 bearer access token 和 account ID，但不包含 refresh/ID token。
- `demo` 最终输出严格的 `OK`；若 backend、模型或 subscription 不再兼容，应返回可诊断的 HTTP status，而不是偷偷 fallback 到 API key。
- 默认测试离线通过；live OAuth 只由用户显式启动。

## 已知真实陷阱

- Codex backend 会拒绝省略或启用 `store` 的某些 Responses 请求，错误表现为 `Store must be set to false`。
- Codex backend 会拒绝 `stream:false`，错误表现为 `Stream must be set to true`；最小 client 也必须解析 SSE，而不是只等一个 JSON object。
- `store:false` 的多步 reasoning 不能继续引用 server item ID；需要 encrypted reasoning replay，否则会得到 item not found。
- OpenAI JSON Schema 子集不接受某些 regex lookaround；把安全 path check 留在 executor，不要把所有校验硬塞进 tool schema。
- 不要把长期 OAuth credential 绑定到短期 browser/access session。`state`、PKCE verifier、authorization code 和 callback consumption 必须绑定发起 login 的 session；成功兑换后的完整 token bundle 应绑定稳定的 authenticated owner/account identity。每次模型请求仍须验证当前 session 有权代表该 owner 使用 credential。否则 cookie 过期、重新 challenge 或服务重启会制造假的 `connected=false` 并诱导用户重复授权。
- refresh token 可能旋转。只更新 access token 会让下一次 refresh 使用已失效的旧值。
- `id_token` 可以帮助读取 account claim，但 decode JWT 不等于验证任意外部 token。这里只信任刚从固定 OAuth token endpoint 得到的响应。

## 速度档位与用量测量

CLI 通过 `--service-tier`、Python API 通过 `service_tier` 参数指定请求速度档位，可选值为 `default`、`fast`、`priority` 与 `ultrafast`。其中 `fast` 自动映射为 `priority`。调用层不提供静默降级逻辑（no silent fallback），如果需要降级处理，调用方应在配置或命令中显式选择 `fast` 等备选档位；默认显式请求 `default`（Standard），不会自动选择加速档位；只有用户明确选择时才请求 Fast 或 Ultrafast。实测延迟与吞吐数据见[速度基准测试文档](../docs/speed_benchmark_20260929.md)。

### CLI 调用示例

```bash
.venv/bin/chatgpt-oauth --json request --model gpt-6-astra --service-tier ultrafast --reasoning-effort xhigh --prompt-file article_prompt.txt
```

### JSON 输出与 API 行为

在 `--json` 模式下，响应返回以下关键字段：
- `requested_service_tier` 与 `service_tier`：分别记录请求档位与服务端回传档位。2026-09-29 六次实测的耗时有明显差异，但服务端均回传 `default`，该特性不应作为客户端禁用 fast 或 ultrafast 的依据。本功能属于工程实验接入，并非官方第三方 API 规范承诺。
- `usage` 与 `timing`：记录服务端原始 token 统计及首字延迟和总耗时；`output_tokens` 包含 reasoning tokens，正文 tokens 需相减计算。

### 接口与参数说明

- `request_result`：返回包含文本正文、`usage`、`timing` 及档位状态的结构化对象；`request_text` 返回纯文本内容。
- `tokens=`：Python 接口接受调用方在内存中维护的 `TokenBundle`，不触发磁盘读写与自动刷新机制。
- `--timeout`：控制底层网络 socket 超时时长。
- 概念区分：`--reasoning-effort` 的 `ultra` 档位用于调整模型思考深度，与控制排队优先级和生成速率的 `--service-tier ultrafast` 属于独立参数。


## 深入阅读

- `README.md`：安装、命令和 token 文件示例。
- `docs/rfc.md`：协议、数据流和生产化边界。
- `src/chat_gpt_oauth/`：不依赖 OAuth SDK 的最小实现。
- `THIRD_PARTY_NOTICES.md`：OpenCode reference 与 MIT notice。
