# 跨境电商选品调研 Agent

这是一个可重复运行、可自动化测评的模块化单体。默认使用固定 fixture 数据保证本地可测；配置 eBay Browse API 凭证后，商品候选和价格会优先来自真实 eBay 搜索结果。所有 synthetic 成本和供应商信息在报告中明确标记为假设，不承诺盈利。

## 快速运行

```powershell
conda activate fastapi
python -m pip install -r backend/requirements.txt
python -m uvicorn app.main:app --app-dir backend --reload
```

另开终端运行前端：

```powershell
cd frontend
npm install
npm run dev
```

打开 http://localhost:3000。演示账号：`researcher@example.com / Research123!`；只读账号：`viewer@example.com / Viewer123!`。

若需要启动 PostgreSQL、Redis、MinIO 和 API/前端容器：`docker compose -f infra/compose.yaml up --build`。本地验证默认 SQLite，避免没有 Docker 时无法开发。

## API 和测试

- `POST /api/v1/auth/login`
- `POST /api/v1/research-runs`（研究员/管理员，支持 `Idempotency-Key`）
- `GET /api/v1/research-runs/{run_id}`
- `POST /api/v1/research-runs/{run_id}/retry`
- `POST /api/v1/research-runs/{run_id}/cancel`
- `GET /api/v1/research-runs/{run_id}/events`
- `GET /api/v1/research-runs/{run_id}/report?format=json|csv`
- `GET /api/v1/research-runs/{run_id}/evidence`
- `POST /api/v1/research-runs/{run_id}/chat`（DeepSeek Agent 工具调用问答；未配置密钥时使用明确标注的本地可复现模式）

### 真实 Agent 和平台数据配置

问答 Agent 通过 OpenAI-compatible 接口调用 DeepSeek。项目支持 `LLM_API_KEY` 或系统变量 `DEEPSEEK_API_KEY`；模型自主选择只读研究工具，再根据工具返回的报告事实回答，工具不能修改利润、评分或来源。可通过 `LLM_BASE_URL` 替换为兼容接口进行联调。

商品候选数据支持 eBay Browse API。eBay Browse API 是官方开放搜索接口，配置下面两个变量后，调研运行会优先读取真实商品标题、价格、链接和卖家反馈信息；未配置时自动使用 fixture，并在报告中标记数据来源。

```powershell
$env:EBAY_CLIENT_ID="你的 eBay Client ID"
$env:EBAY_CLIENT_SECRET="你的 eBay Client Secret"
$env:EBAY_ENV="production" # sandbox 可用于联调
```

当前 eBay Browse API 不提供商品评论正文和供应商成本，因此这些字段不会被伪造；供应商成本、头程和税率仍会标记为 synthetic 假设。Amazon 真实商品数据应通过官方 SP-API 接入，需要 Amazon 开发者凭证，不能用公开抓取数据冒充实时数据。

```powershell
& C:\Users\123\anaconda3\envs\fastapi\python.exe -m pytest -p no:cacheprovider backend/tests
```

测试覆盖领域计算、状态机、固定数据契约、API、幂等、报告追溯、角色权限、租户隔离、输入校验和敏感信息泄露检查。性能/压力验证使用下面的最小脚本；正式 100～500 并发容量必须在企业环境以真实 PostgreSQL/Redis/Celery/对象存储基线测量，不能用个人电脑结果替代。

```powershell
conda activate fastapi
python scripts/smoke_test.py
```

更多冒烟、安全、并发探针和 Playwright 端到端命令见 [TEST_PLAN.md](TEST_PLAN.md)。
