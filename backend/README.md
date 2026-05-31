# 人生样本库 Backend MVP

这是当前 Demo 的最小 FastAPI 后端骨架，先支持轻量追问判断和搜索接口占位。第一版不接完整 LLM Agent，问题理解和追问判断使用规则实现。

## 启动

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## 环境变量

```bash
ZHIHU_APP_KEY=
ZHIHU_APP_SECRET=
ZHIHU_BASE_URL=https://openapi.zhihu.com/
ZHIHU_SEARCH_URL=https://developer.zhihu.com/api/v1/content/zhihu_search
ZHIHU_ACCESS_SECRET=
ZHIHU_SEARCH_QUERY_PARAM=Query
ZHIHU_SEARCH_COUNT_PARAM=Count
OPENAI_API_KEY=
LLM_MODEL=
USE_MOCK_FALLBACK=true
```

密钥只从环境变量读取，不写入代码。当前知乎搜索 API 使用 `ZHIHU_ACCESS_SECRET`，不使用 `ZHIHU_APP_KEY` / `ZHIHU_APP_SECRET`。

真实知乎搜索配置示例：

```bash
ZHIHU_SEARCH_URL=https://developer.zhihu.com/api/v1/content/zhihu_search
ZHIHU_ACCESS_SECRET=你的 access_secret
ZHIHU_SEARCH_QUERY_PARAM=Query
ZHIHU_SEARCH_COUNT_PARAM=Count
```

当前知乎搜索 API 使用 Bearer access_secret 鉴权。`ZHIHU_ACCESS_SECRET` 需要在知乎数据开放平台个人中心 / 控制台获取。如果未配置，后端会跳过真实搜索，使用 mock fallback，但 `debug.understanding` 和 `debug.keywords` 仍会返回。

## 测试

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

测试追问接口：

```bash
curl -X POST http://127.0.0.1:8000/api/query/clarify \
  -H "Content-Type: application/json" \
  -d '{"query":"我现在很迷茫"}'
```

测试搜索接口：

```bash
curl "http://127.0.0.1:8000/api/search?query=不工作之后我想去新西兰生活&count=20"
```

测试带追问答案的搜索接口：

```bash
curl "http://127.0.0.1:8000/api/search?query=我现在很迷茫&clarification=工作选择&count=20"
```

如果当前终端或 HTTP 客户端没有自动编码中文 URL，可以用更稳的写法：

```bash
curl --get http://127.0.0.1:8000/api/search \
  --data-urlencode "query=我现在很迷茫" \
  --data-urlencode "clarification=工作选择" \
  --data-urlencode "count=20"
```

## 当前知乎搜索状态

`services/zhihu_client.py` 已实现 Bearer access_secret 鉴权的知乎搜索客户端。当前默认请求：

```text
GET https://developer.zhihu.com/api/v1/content/zhihu_search?Query=...&Count=10
```

请求头：

```bash
Authorization: Bearer ${ZHIHU_ACCESS_SECRET}
X-Request-Timestamp: 秒级 Unix 时间戳
Content-Type: application/json
```

在 access secret 未配置、请求失败或没有结果时，`/api/search` 会返回可供前端渲染的 fallback `paths + people`，并把调试信息放在 `debug` 中。若接到真实知乎搜索结果，第一版只会把标准化后的原始结果放入 `debug.rawResults`，不会伪装成真实人物样本卡。
