# 不工作了，你要去哪儿 Demo

这个文件夹收拢《不工作了，你要去哪儿》产品 Demo 的相关文件，避免和根目录里的其他知乎人生路书原型混在一起。

## 打开方式

直接用浏览器打开：

```text
index.html
```

## 后端 LLM 配置

后端 LLM 客户端读取 `backend/.env`，可以先从示例文件复制：

```bash
cd backend
cp .env.example .env
```

需要填写这些变量：

```env
LLM_API_KEY=你的中转站 API Key
LLM_BASE_URL=你的 OpenAI-compatible /v1 base URL
LLM_MODEL=你的模型名
LLM_TIMEOUT_SECONDS=20
LLM_MAX_CONCURRENCY=3
```

LLM 客户端使用 OpenAI-compatible Chat Completions 格式，请求地址为 `${LLM_BASE_URL}/chat/completions`。代码不会写死 API Key、OpenAI 官方地址或具体中转站地址；`backend/.env.example` 里的 base URL 只是本地配置示例。

## 文件

- `index.html`：单文件 Web Demo。
- `assets/mirofish-character-svgs/`：附件解压出的 SVG 人物素材。
- `docs/不工作了你要去哪儿_产品Demo方案.md`：唯一产品方案文件。
- `docs/前后端联调字段清单.md`：前后端字段和接口对齐清单。
