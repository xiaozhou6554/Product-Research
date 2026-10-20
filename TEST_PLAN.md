# 测试与评测计划

## 已覆盖

| 层级 | 入口 | 关注点 |
| --- | --- | --- |
| 领域单元 | `backend/tests/test_domain.py` | 利润全成本公式、增长率、评分、等级、状态机 |
| 数据契约 | `backend/tests/test_contract.py` | 固定 fixture 的字段、价格、证据置信度 |
| API/集成 | `backend/tests/test_api.py` | 登录、创建、幂等、异步完成、报告、证据、取消/重试、报告问答 |
| Agent 工具调用 | `backend/tests/test_agent.py` | 模型先选择只读研究工具，再基于工具结果回答；禁止直接改写确定性指标 |
| 安全 | `backend/tests/test_api.py`、`scripts/security_test.py` | 角色授权、租户隔离、输入校验、错误信息脱敏 |
| 前端 E2E | `frontend/tests/e2e/research.spec.ts` | 创建调研、进度、报告展示和底部问答窗口 |
| 冒烟 | `scripts/smoke_test.py` | 健康链路、登录、创建任务 |
| 并发探针 | `scripts/load_test.py` | 本机小规模创建请求平均耗时和 P95 |

## 运行顺序

1. 使用已有 Conda `fastapi` 环境启动 API：`& C:\Users\123\anaconda3\envs\fastapi\python.exe -m uvicorn app.main:app --app-dir backend --port 8000`。
2. 使用 `npm run dev` 启动前端。
3. 执行领域/API 测试、冒烟、安全脚本，再执行 `$env:LOAD_COUNT='20'; python scripts/load_test.py`。
4. 浏览器环境安装后执行 `cd frontend; npx playwright install chromium; npm run test:e2e`。

生产容量 100～500 并发任务、真实 PostgreSQL/Redis/Celery/对象存储、Prometheus/Grafana/Sentry 需要在企业环境做独立基线；本地 SQLite + 线程池结果不能冒充生产容量结论。
