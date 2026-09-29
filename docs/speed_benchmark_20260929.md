# GPT-6-Astra 速度档位基准测试报告

- 测试日期：2026-09-29

## 测试配置与环境

本测试针对 `gpt-6-astra` 模型在不同服务速度档位（Service Tier）下的生成延迟与吞吐性能展开实测。

- 模型：`gpt-6-astra`
- 推理深度：`reasoning_effort: xhigh`
- 工具调用：无外部工具
- 请求方式：各档位独立单次请求
- 任务内容：将 4877 字符的中文长文主体完整翻译为英文
- 文本来源：[从上下文失忆到文档驱动开发：突破Agentic AI的项目规模陷阱](https://yage.ai/agentic-memory.html)
- 提示词指令：
  ```text
  Translate the following complete Chinese article into English. Preserve all headings, paragraphs, lists, and meaning. Do not summarize, omit, add commentary, or update its claims. Output only the complete English translation.
  ```
- 提示词完整 SHA-256 哈希（用于复现验证）：`c2bac7478b302096115c129f75451c356299dda2b2d30c2e9c8b170e3884bf5e`
- 凭证与执行：使用经授权的活跃订阅 OAuth 凭证于内存中执行，未修改或持久化本地凭证。早期使用过期示例凭证触发的 401 失败请求已从统计中剔除，耗时数据全部基于成功请求。

文本生成速率为正文 tokens 除以首个至最后一个文字 delta 的接收时间差，是客户端估算，包含流传输影响。总耗时始于凭据准备完成后、HTTP 请求之前。

## 第一轮测试结果（正序：Standard -> Fast -> Ultrafast）

第一轮所有请求均未命中缓存（缓存 Tokens 均为 0）。总输出 Tokens（`output_tokens`）包含思考阶段 Tokens，实际正文 Tokens 满足公式：`text_tokens = output_tokens - reasoning_tokens`。

| 档位 (Requested Tier) | 总耗时 (s) | 首文本耗时 (s) | 文本生成速率 (tokens/s) | 输入 Tokens | 输出 Tokens (含思考) | 思考 Tokens | 文本 Tokens |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| standard (`default`) | 101.38 | 13.81 | 33.4 | 3159 | 3318 | 401 | 2917 |
| fast (`priority`) | 63.44 | 17.40 | 63.7 | 3159 | 3832 | 917 | 2915 |
| ultrafast (`ultrafast`) | 17.78 | 10.94 | 428.4 | 3159 | 3549 | 648 | 2901 |

相比 standard 档位：
- fast 档位总耗时比为 101.379 / 63.438，提速约为 1.60x，文本生成速率达到 63.7 tokens/s；
- ultrafast 档位总耗时比为 101.379 / 17.782，提速约为 5.70x，文本生成速率达到 428.4 tokens/s。

## 第二轮测试结果（逆序：Ultrafast -> Fast -> Standard）

逆序测试用于观察缓存及连续请求对生成速度的影响。`ultrafast_2` 命中 2944 cached tokens。其余五次请求缓存命中均为 0。每档仅测两次，分别列出，不混算成稳定性能承诺。

| 运行轮次 | 请求档位 | 总耗时 (s) | 首文本耗时 (s) | 文本速率 (tokens/s) | 缓存 Tokens | 文本 Tokens |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| ultrafast_2 | ultrafast | 14.55 | 4.65 | 295.7 | 2944 | 2902 |
| fast_2 | priority | 65.46 | 13.67 | 56.3 | 0 | 2911 |
| standard_2 | default | 104.65 | 17.91 | 33.7 | 0 | 2916 |

## 结构一致性与完整度校验

当前所有已完成的输出均保持 4 个二级标题与 27 个空行分隔文本段落，与原文结构完全吻合；各档位生成的文本 Tokens 均在 2900 左右（2901 至 2917），未观察到整段遗漏或提前截断，文本生成阶段也显示出明显速率差异。本次测试专注于吞吐与延迟测量，并非正式的语义翻译质量审计。

## 协议特性与说明

- 响应回传特性：所有请求的响应体中，`service_tier` 字段最终均返回 `default`；第二轮请求仍分别显式指定 `ultrafast`、`priority`、`default`，但 `response.created` 和 `response.in_progress` 都回报 `auto`，`response.completed` 都回报 `default`。因此保留用户选择的档位，并分别记录请求值与回报值；不因该字段禁用加速选项，也不声称已由回报值认证实际后端档位。
- 适用边界：上述加速倍率展示了当前测试环境下的实测表现，不构成跨账号的稳定性承诺，无法用于反推服务端具体硬件配置，也不能根据 Token 数量折算实际配额消耗。

六次测量的脱敏数据见 [speed_benchmark_20260929.json](speed_benchmark_20260929.json)。三档都使用相同模型和 `xhigh`；复测的服务端 reasoning 字段也确认 `xhigh`。
