# 测试报告

执行日期：2026-10-13（Asia/Shanghai）

## 结果摘要

| 类型 | 结果 | 证据 |
| --- | --- | --- |
| 领域、契约、API、安全、Agent 自动化 | 9 passed | `backend/tests` |
| TypeScript | passed | `frontend/npm run lint` |
| Next.js 生产构建 | passed | Next.js 16.0.10 |
| 前端 Playwright E2E | 2 passed | `frontend/tests/e2e/research.spec.ts` |
| 冒烟 | passed | 登录、创建任务、返回任务编号 |
| 安全脚本 | passed | 未登录 401、跨租户读取 404 |
| 并发/压力探针 | 50/50 passed | 平均 83.27ms，P95 102.00ms；仅为本机开发环境探针 |
| Compose 配置校验 | passed | `docker compose config` |
| 前端生产依赖审计 | 0 high vulnerabilities | `npm audit --omit=dev --audit-level=high` |

## 验收结论

- 已覆盖登录、研究员创建任务、只读用户拒绝创建、幂等键、任务状态、固定数据分析、利润全成本公式、评分/推荐等级、报告、CSV 导出、证据追溯和租户隔离。
- 已实现真实 Agent 问答链路：DeepSeek 配置启用后，Agent 先调用只读利润/趋势/竞品/风险工具，再根据工具结果生成回答；工具调用和引用会回传到前端。无密钥时仅启用明确标注的本地可复现模式，便于离线测试。
- 报告把 fixture、synthetic、搜索兴趣不等于销量等边界明确写入结果，未接入商业平台抓取。
- 本机压力探针只验证 API 创建入口在开发环境的行为，不能推导生产环境 100～500 并发任务容量。

## 未在本机做出的生产级结论

当前本地闭环使用 SQLite + 进程线程池；Compose 提供 PostgreSQL、Redis、MinIO、API、Worker、Frontend 服务位，但 Worker 仍是本地编排占位。生产容量、Celery 恢复、LangGraph 持久化、真实 S3、Prometheus/Grafana/Sentry 和公开数据集导入需要在企业基础设施中继续实施和基线测量，不能以本报告冒充已完成。
