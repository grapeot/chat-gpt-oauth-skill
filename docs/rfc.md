# RFC：最小 ChatGPT/Codex OAuth Reference

## 1. 状态

V0 implementation。目标是协议可读、行为可测、风险透明，不追求 production secret storage 或多用户 tenancy。

## 2. 数据流

```text
CLI
  -> generate state + PKCE verifier/challenge
  -> listen on localhost:1455
  -> open auth.openai.com/oauth/authorize
  -> receive one-time code and verify state
  -> POST auth.openai.com/oauth/token
  -> parse account ID from trusted token response
  -> write plaintext ~/.chatgpt_oauth/token.json (0600)

request
  -> load token file
  -> refresh if expires_at <= now + 60s
  -> atomically replace complete token bundle
  -> POST chatgpt.com/backend-api/codex/responses
     Authorization: Bearer <access token>
     ChatGPT-Account-Id: <account ID>
     store: false
  -> extract output_text
```

## 3. 为什么用 authorization code + PKCE

这是 public desktop client，没有可安全隐藏的 client secret。PKCE 让截获 authorization code 的第三方无法在没有 verifier 的情况下兑换 token。`state` 解决的是另一类问题：callback 必须属于当前 login attempt，不能接受另一个 tab、旧 attempt 或恶意站点制造的 code。

redirect URI 固定为 `http://localhost:1455/auth/callback`。reference implementation 不随机选择端口，因为 OAuth server 只接受 public client 已登记的 redirect contract。

## 4. Token 模型

token endpoint 的 response 是唯一可信输入。程序从刚收到的 ID/access JWT payload 中读取 account ID；这里的 decode 用于 metadata extraction，不构成通用 JWT verification API。

长期存储是完整 bundle，而不是只存 access token。refresh 可能返回 rotated refresh token，因此更新必须覆盖整个文件。reference implementation 使用同目录临时文件 + `os.replace`，避免进程中断留下半个 JSON。

明文文件是教学 trade-off：可检查、无平台依赖，但同一 OS 用户下的任何进程都可能读取。目录 `0700`、文件 `0600` 只是最低限度，不是 encryption。

## 5. Codex Transport

reference request 使用固定 endpoint allowlist，不接受用户传入任意 URL。它发送：

```json
{
  "model": "gpt-5.4-mini",
  "input": [
    {
      "role": "user",
      "content": [{"type": "input_text", "text": "请只回复 OK，不要添加其他文字。"}]
    }
  ],
  "store": false,
  "stream": true,
  "include": ["reasoning.encrypted_content"]
}
```

`access_token` 只进入 bearer header；`account_id` 进入 `ChatGPT-Account-Id`；refresh token 和 ID token 不离开 local storage/token endpoint 边界。

多步 Agent integration 比这个单轮 reference 更复杂。`store:false` 意味着 server 不持久化 reasoning item。调用方必须把 `reasoning.encrypted_content` 保留在可信会话历史中，并在后续 turn replay，同时移除不可复用的 persisted reasoning item ID。

## 6. Productionization Gap

将 reference 变成 owner-only production integration，至少需要：

- encrypted credential store 与 master-key rotation；
- credential 与 authenticated owner/session 的强绑定；
- 多实例 refresh lease、single-flight 和 credential-version CAS；
- revoke/delete lifecycle、audit metadata 和 kill switch；
- endpoint/model allowlist、budget、rate limit 与 subscription error handling；
- event/log redaction，确保 prompt、artifact 和 telemetry 不包含 token；
- upstream compatibility tests，及时发现 public client、model、endpoint 或 request schema 变化。

Hosted multi-user service 还需要 OpenAI 明确支持的 OAuth/client registration contract。不能因为 localhost owner experiment 可运行，就假设可以合法、稳定地扩展到任意第三方 Web 用户。

## 7. 来源与许可

协议参数和 compatibility behavior 参考 OpenCode 的公开 MIT implementation。reference code 重新以 Python 标准库实现，并在 `THIRD_PARTY_NOTICES.md` 保留 notice。OpenAI endpoints 和 trademarks 不受本项目 MIT license 授权或担保。
