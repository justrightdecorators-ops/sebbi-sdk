# sebbi：AI 的证明层（MCP 服务器）

**sebbi.pro 为每一次 AI 决策提供任何人都可以独立核验的证据。** 每个决策在 30 毫秒内完成评分（ALLOW / CHALLENGE / BLOCK），写入防篡改的哈希链，并通过 OpenTimestamps 锚定到比特币区块链。监管机构、审计师、保险公司或法院无需信任 sebbi.pro，也无需信任您，即可自行验证。

## 一行命令接入

```json
{
  "mcpServers": {
    "sebbi": { "command": "npx", "args": ["-y", "sebbi", "mcp"] }
  }
}
```

或使用 Python：

```json
{
  "mcpServers": {
    "sebbi": { "command": "uvx", "args": ["sebbi", "mcp"] }
  }
}
```

也可以直接连接远程服务器（Streamable HTTP）：`https://sebbi.pro/mcp`

无需安装其他依赖，本地不保存任何数据。

## 主要工具

| 工具 | 作用 |
|---|---|
| `sebbi_notarize` | 免费把任意文件或文本的 SHA-256 指纹写入比特币时间戳。内容不离开本机，只发送指纹。 |
| `sebbi_input_gate` | 输入闸门：AI 使用第三方数据之前，先与数据来源在自己域名上公布的文件核对。被篡改的数据返回 TAMPERED 并被拒绝。 |
| `sebbi_no_return_check` | 不可逆操作安全闸：删除、付款、发送、发布之前先询问，没有退路就必须由真人批准。 |
| `sebbi_test_decision` | 对一次 AI 决策评分并封存，返回可公开核验的回执。 |
| `sebbi_run_everything` | 一次运行 755 项合规检查（欧盟 AI 法案、GDPR、DORA、ISO 42001、NIST AI RMF 等），每项结果都带回执。 |
| `sebbi_verify_chain` | 任何人都可以验证整条证据链。 |
| `sebbi_tools` | 列出其余全部工具（银行、人工监督、保险、法律等）。 |

## 为什么需要它

普通审计日志由被审计的机构自己保存，机构随时可以修改，外人无法察觉。sebbi 的记录在产生的那一刻就把指纹交给机构控制范围之外的比特币区块链，事后任何改动都会暴露。

- **输入是否真实？** 输入闸门在使用前核对数据来源。
- **AI 决定了什么？** 决策回执在产生时封存。
- **是否有人审批？** 人工批准与审阅时间一并封存。
- **之后是否被改动？** 比特币时间戳，任何人免费核验。

## 价格

免费试用 7 天，之后每台设备每月 50 便士（约 ¥4.6）。核验任何证据永久免费。

## 链接

- 中文页面：https://sebbi.pro/country/cn
- 输入闸门：https://sebbi.pro/garbage-in
- 连接说明：https://sebbi.pro/connect
- 官方 MCP Registry 命名空间：`pro.sebbi`
- PyPI：https://pypi.org/project/sebbi/ · npm：https://www.npmjs.com/package/sebbi
- 许可证：Apache-2.0

创始人兼首席系统架构师：Justin Dobson（sebbi.pro / Monop Content，英国）
