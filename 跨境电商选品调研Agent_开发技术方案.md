# 跨境电商选品调研 Agent：开发技术方案

## 一、技术目标与边界

本方案只描述开发、运行、测试和部署实现。业务目标、用户角色和功能验收以《跨境电商选品调研Agent_需求文档.md》为准。

第一阶段采用公开数据集、官方公共数据、合成 CSV 和固定测试数据，不抓取商业平台页面，不绕过登录、验证码、反爬或访问限制。生产环境部署到企业容器平台，个人电脑只用于开发和验证。

## 二、已确认技术栈

| 层次 | 技术 |
|---|---|
| 前端 | Next.js 16、React 19、TypeScript、Node.js 24.20.0 |
| API | Python 3.11、FastAPI 0.142.2 |
| 工作流 | LangGraph 1.2.13 |
| 数据库 | PostgreSQL 18.6 |
| 缓存与消息 | Redis 8.x、Celery 5.6.3 |
| 对象存储 | 本地/测试使用 MinIO 固定镜像；生产使用企业批准的 S3 兼容服务 |
| 模型 | 远程 DeepSeek-V4.1-Flash，配置标识 `deepseek-flash` |
| 本地运行 | Docker Compose |
| 架构 | DDD 四层模块化单体 + 异步任务 |
| 测试 | pytest、Playwright、契约测试、集成测试 |
| 监控 | Prometheus、Grafana、Sentry、结构化日志 |

版本写入锁文件和构建文件，生产环境不使用 `latest`。

## 三、总体架构

```text
Next.js Web
    ↓ HTTPS / SSE
FastAPI 接口层
    ↓
应用服务层
    ↓
LangGraph 调研工作流
    ↓
领域服务与业务规则
    ↓
数据连接器、Repository、LLM、缓存和对象存储
```

系统采用模块化单体，不在第一阶段拆分微服务。原因是当前需要先验证完整业务闭环，同时保留清晰模块边界。数据分析和报告生成属于长耗时任务，由 Celery Worker 异步执行，API 不直接阻塞等待。

## 四、DDD 四层设计

### 4.1 Interface 接口层

负责 HTTP、SSE、鉴权、请求校验和响应转换。

不能实现利润算法、评分规则，也不能直接连接数据库、Redis 或外部数据源。

### 4.2 Application 应用层

负责创建调研、查询状态、重试节点、取消任务、生成报告和调用 LangGraph 工作流。

应用层依赖接口，不直接拼接 SQL，不直接调用第三方 SDK。

### 4.3 Domain 领域层

负责商品候选、价格、成本、利润、评分、证据、风险和任务状态机。

领域层不能导入 FastAPI、Next.js、LangGraph、SQLAlchemy 或外部平台 SDK。利润、评分和推荐等级必须由领域规则或确定性服务计算。

### 4.4 Infrastructure 基础设施层

负责 PostgreSQL、Redis、Celery、MinIO、DeepSeek 客户端、公开数据集连接器、CSV 和 Mock 实现。

基础设施层实现 Domain/Application 定义的 Port，但不把数据库模型和 SDK 类型泄漏到领域层。

依赖方向：

```text
Interface → Application → Domain
Infrastructure ──实现──> Domain/Application 定义的 Port
```

## 五、Agent 工作流

### 5.1 工作流节点

```text
参数校验
  ↓
生成研究计划
  ↓
并行节点：趋势 / 商品 / 评论 / 关键词 / 供应商 / 风险
  ↓
数据标准化
  ↓
利润计算与综合评分
  ↓
证据完整性检查
  ↓
报告生成
  ↓
引用校验与置信度评估
  ↓
保存报告并通知前端
```

### 5.2 模型和代码的职责边界

| 内容 | 实现方式 |
|---|---|
| 参数校验 | Python 代码和 Schema |
| 数据读取与清洗 | 连接器和确定性代码 |
| 利润、增长率、评分 | 领域规则和公式 |
| 查询改写 | 模型辅助，结果必须结构化 |
| 评论主题和痛点归纳 | 模型辅助，保留原始证据 |
| 风险文字说明 | 模型辅助，不能伪装为法律结论 |
| 报告表达 | 模型生成，必须通过 Schema 和引用校验 |

模型不能直接决定价格、利润、评分或数据来源。

### 5.3 并行、重试和恢复

趋势、商品、评论、关键词、供应商和风险节点可以并行执行。

利润计算依赖商品价格、成本和费用假设；评分依赖趋势、竞争、利润和风险结果；报告依赖已完成节点和证据校验。

工作流状态必须持久化。节点失败时记录错误码、重试次数和输入版本；重试只执行失败节点，不重复执行已成功节点。

## 六、数据接入与统一模型

### 6.1 数据源

| 数据源 | 使用方式 |
|---|---|
| Amazon Science ESCI | 离线商品文本和搜索相关性数据 |
| Google Trends 公共数据集 | 固定 CSV 或公开数据导入 |
| UCI Online Retail II | 离线历史交易数据 |
| 合成 CSV | 供应商、采购、物流、税费、退货和汇率 |
| Mock/CSV Fixture | 单元、契约、集成和端到端测试 |

所有数据保存来源、版本、市场、时间和原始记录哈希。缺少真实字段时必须为空或标记为假设，不能由模型补造。

### 6.2 Port 与 Adapter

业务层只依赖抽象接口：

```python
class ProductDataPort(Protocol):
    async def search_products(
        self,
        query: ProductSearchQuery,
    ) -> ProductSearchResult:
        ...

    async def get_product_detail(
        self,
        product_id: str,
        marketplace: str,
    ) -> ProductDetail:
        ...
```

当前实现：

```text
ProductDataPort
├── MarketplaceSimulatorAdapter  # 公开数据与合成数据
├── CsvProductDataAdapter        # CSV 数据
└── MockProductDataAdapter       # 自动化测试
```

以后如果接入经过授权的平台，只增加新的 Adapter，业务层不改。

### 6.3 元数据

每条数据和证据至少保存：

`tenant_id`、`source_type`、`source_version`、`marketplace`、`fetched_at`、`expires_at`、`raw_record_hash`、`created_by`。

## 七、核心领域模型

核心表：

| 表 | 主要字段和作用 |
|---|---|
| `research_run` | 调研任务、输入、计划、状态、错误和版本 |
| `product_candidate` | 商品候选、价格、评分、评论量、来源 |
| `evidence` | 原始证据、来源、时间、哈希和关联结论 |
| `profit_calculation` | 售价、采购、头程、佣金、广告、税费、退货、汇率和结果 |
| `risk_item` | 风险类型、等级、说明和证据 |
| `research_report` | 报告正文、结构化结果、版本和生成状态 |
| `users` / `tenants` | 用户、角色和租户关系 |

所有租户业务表必须有 `tenant_id`，查询、更新、删除和导出都必须带租户条件。不能只依赖前端传入的 `tenant_id`，应从登录令牌和服务端上下文解析。

## 八、接口设计

核心接口：

| 方法 | 路径 | 作用 |
|---|---|---|
| POST | `/api/v1/research-runs` | 创建调研任务 |
| GET | `/api/v1/research-runs/{run_id}` | 查询任务状态 |
| POST | `/api/v1/research-runs/{run_id}/retry` | 重试失败节点 |
| POST | `/api/v1/research-runs/{run_id}/cancel` | 取消任务 |
| GET | `/api/v1/research-runs/{run_id}/events` | SSE 进度事件 |
| GET | `/api/v1/research-runs/{run_id}/report` | 查询报告 |
| GET | `/api/v1/research-runs/{run_id}/evidence` | 查询证据 |

接口统一返回请求 ID、任务 ID、状态和错误码。错误信息不能泄露密钥、数据库连接串或其他租户的数据。

## 九、前端实现边界

Next.js 只负责页面、表单、进度、报告和证据展示。

核心页面：

1. 登录页。
2. 新建调研页。
3. 任务进度页。
4. 报告总览页。
5. 趋势、竞品、评论、利润、供应商和风险详情页。
6. 证据展开和报告导出。

前端只调用 FastAPI，不直接访问 PostgreSQL、Redis、MinIO 或外部数据源。

## 十、安全与可靠性

### 10.1 认证和授权

- 使用 JWT 登录。
- 服务端解析用户、角色和 `tenant_id`。
- 管理员、研究员、只读用户执行权限校验。
- 所有资源访问执行租户过滤。

### 10.2 外部调用和模型调用

- DeepSeek API 设置连接超时、读取超时、重试次数和最大输出长度。
- 只对可重试错误进行有限重试。
- 记录请求 ID、耗时、状态和错误类别，不记录完整密钥或敏感内容。
- 模型输出先做结构化解析和字段校验，再进入报告。

### 10.3 任务可靠性

- API 创建任务后立即返回任务 ID。
- Celery Worker 执行长耗时任务。
- PostgreSQL 保存任务状态，Redis 用于消息和缓存。
- 任务支持超时、取消、失败重试和部分失败。
- 关闭浏览器不影响后台任务继续执行。

## 十一、测试与评测

### 11.1 必须测试的内容

| 类型 | 重点 |
|---|---|
| 领域单元测试 | 利润、评分、推荐等级、状态机 |
| 契约测试 | MarketplaceSimulator、CSV、Mock 输出结构一致 |
| 租户隔离测试 | A 租户不能读取 B 租户数据 |
| 集成测试 | PostgreSQL、Redis、Celery、对象存储 |
| API 测试 | 创建、查询、重试、取消、权限和异常 |
| 前端端到端测试 | 登录、创建任务、查看进度、查看报告、错误提示 |
| 回归评测 | 固定问题集、标准候选、利润结果和引用 |

### 11.2 评测指标

- 数据检索：Recall@K、Precision@K、MRR、nDCG。
- 计算正确性：利润结果与标准答案误差。
- 报告质量：引用覆盖率、事实忠实度、字段完整率。
- 工程质量：任务成功率、平均耗时、节点失败率、模型调用成本。

评测集、标准结果和评测报告纳入版本管理。阈值由实际基线测试确定，不在没有数据时编造固定数值。

## 十二、本地到生产环境

### 12.1 本地环境

- Windows + Docker Desktop。
- 项目运行数据放在 `D:\AI0803\Chatgpt\runtime-data`。
- PostgreSQL、Redis、MinIO 使用 Compose 启动。
- 模型通过远程 DeepSeek API 调用，不在个人电脑运行本地大模型。
- Docker Desktop 的镜像缓存和虚拟磁盘需要单独确认已迁移到 D 盘。

### 12.2 生产环境

生产部署到企业容器平台：

- API、Worker、前端构建为独立镜像。
- PostgreSQL、Redis 使用企业批准的服务。
- 对象存储使用企业批准的 S3 兼容服务。
- 密钥通过 Secret 注入。
- 接入 Prometheus、Grafana、Sentry 和结构化日志。
- 按 100～500 个并发任务执行容量评估。

环境差异通过配置解决：数据库、Redis、对象存储、模型 API、日志和监控地址由环境变量注入，业务领域代码不随环境修改。

## 十三、正式目录结构

```text
cross-border-research-agent/
├── frontend/
│   ├── app/
│   ├── components/
│   ├── features/research/
│   ├── lib/api-client.ts
│   └── tests/e2e/
├── backend/
│   ├── app/
│   │   ├── interfaces/
│   │   │   ├── http/
│   │   │   ├── schemas/
│   │   │   └── auth/
│   │   ├── application/
│   │   │   ├── commands/
│   │   │   ├── queries/
│   │   │   ├── services/
│   │   │   ├── agents/
│   │   │   ├── prompts/
│   │   │   └── ports/
│   │   ├── domain/
│   │   │   ├── research/
│   │   │   ├── product/
│   │   │   ├── profitability/
│   │   │   ├── scoring/
│   │   │   ├── evidence/
│   │   │   └── risk/
│   │   ├── infrastructure/
│   │   │   ├── persistence/
│   │   │   ├── connectors/
│   │   │   ├── cache/
│   │   │   ├── storage/
│   │   │   ├── messaging/
│   │   │   ├── llm/
│   │   │   └── observability/
│   │   └── workers/
│   ├── tests/
│   │   ├── unit/
│   │   ├── contract/
│   │   ├── integration/
│   │   └── e2e/
│   ├── pyproject.toml
│   └── Dockerfile
├── data/
│   ├── mock/
│   ├── uploads/
│   └── processed/
├── evals/
├── infra/compose.yaml
├── runtime-data/
├── .env.example
└── README.md
```

## 十四、本地配置与 Docker 约束

`.env.local` 不提交 Git，示例：

```env
DATA_ROOT=D:/AI0803/Chatgpt/runtime-data/cross-border-research
POSTGRES_DB=research
POSTGRES_USER=research
POSTGRES_PASSWORD=请替换为本地随机密码
DATABASE_URL=postgresql+psycopg://research:请替换为本地随机密码@postgres:5432/research
REDIS_URL=redis://redis:6379/0
LLM_PROVIDER=deepseek
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=请填写模型密钥
LLM_MODEL=deepseek-flash
PRODUCT_DATA_BACKEND=marketplace_simulator
TRENDS_DATA_BACKEND=csv
OBJECT_STORAGE_BACKEND=minio
S3_ENDPOINT=http://minio:9000
```

Compose 至少包含 `postgres`、`redis`、`api`、`worker`、`frontend` 和本地 `minio`。所有端口默认只绑定 `127.0.0.1`。生产环境不直接使用本地 Compose 文件，而是根据企业容器平台生成部署配置。

## 十五、开发顺序

1. 锁定 Python、Node、数据库、缓存、任务和模型配置。
2. 建立 DDD 四层目录、配置加载、异常和健康检查。
3. 完成利润、评分、推荐等级和任务状态机等领域规则。
4. 建立 PostgreSQL 表、Repository、迁移和租户索引。
5. 接入公开数据、CSV、Mock，并完成契约测试。
6. 建立 FastAPI 任务、报告、证据、重试、取消和 SSE 接口。
7. 接入 LangGraph 状态、节点、重试、恢复和报告校验。
8. 接入 Celery Worker，让长任务脱离 HTTP 请求。
9. 开发 Next.js 表单、进度、报告和证据页面。
10. 完成单元、集成、API、端到端、租户隔离和评测回归。
11. 使用 Docker Compose 完成本地闭环。
12. 生成企业容器平台部署包并执行容量、监控、回滚和安全验证。

## 十六、交付验收

- Domain 层不依赖 Web 框架、数据库 ORM 和 Agent 框架。
- API 创建任务后立即返回，Worker 可以继续执行。
- 任务中断后可以恢复，失败节点可以单独重试。
- 租户隔离、角色权限和敏感信息保护测试通过。
- 报告中的关键数字可以追溯到计算结果或证据。
- 本地环境可以使用 D 盘数据目录完整启动。
- 生产配置只替换环境变量、数据库、缓存、对象存储和资源规格，不修改核心业务规则。
- 未授权数据源不会被接入，未实现能力明确标记。
