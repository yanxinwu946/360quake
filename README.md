# 360Quake

面向 360 Quake 的资产检索与导出工具。基于 Web 登录凭证发起查询，不消耗 API Token。

## 使用

```bash
pip install -r requirements.txt
python main.py
```

访问 [http://127.0.0.1:8765](http://127.0.0.1:8765)

添加 Quake 登录 Cookie 后即可检索。表格字段可按网页端结果自定义，结果可导出为 JSON、CSV、URL、IP、主机与域名。网页通道单次最多 100 条。国内分省能把中国结果铺开，拿到更完整的资产。

也可以接到 Cursor、Claude、Grok 这类 agent 上，用自然语言盘点资产，结果直接进对话。

```json
{
  "mcpServers": {
    "quake": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "项目目录"
    }
  }
}
```

网页开着时，agent 也可以走 [http://127.0.0.1:8765/mcp](http://127.0.0.1:8765/mcp)。

检索语法与官方控制台一致：

- `domain:"example.com"`
- `port:443 AND country:"China"`

## 获取 Cookie

登录 [360 Quake](https://quake.360.net/)，在浏览器开发者工具中复制任意请求的 Cookie 字段。

仅用于授权范围内的资产盘点。未经书面许可，禁止复制、修改、分发与商业使用。见 `LICENSE`。
