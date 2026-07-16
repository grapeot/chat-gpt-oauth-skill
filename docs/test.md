# 测试策略

## 默认离线测试

`.venv/bin/python -m pytest -v` 不访问网络、不打开浏览器、不读取真实 home token。

覆盖：

- PKCE authorize URL、S256 challenge、state 和固定 callback。
- trusted JWT payload 中三种 account ID claim 位置。
- token response validation、`expires_in` 转换和 refresh metadata fallback。
- token JSON round trip、repo 外自定义路径、目录 `0700` 与文件 `0600`。
- 临近过期自动 refresh、rotated refresh token 原子持久化。
- Codex request endpoint、bearer/account headers、`store:false` 和 output text extraction。
- CLI status 不输出 token value。

## Live Acceptance

真实测试必须由用户显式运行：

```bash
.venv/bin/chatgpt-oauth demo
```

验收时观察：浏览器在 OpenAI 域名授权；callback 页面成功；CLI 明确报告明文 token 路径；`--json status` 不显示 token；最终 stdout 严格为 `OK`。该测试使用真实 subscription backend，不能进入 CI，也不能保存 response/token fixture。

## Public Scan

`.venv/bin/python scripts/check_public.py` 扫描公开候选文件中的本机绝对路径、private vault reference 和常见 secret pattern。它不替代人工 diff review。
