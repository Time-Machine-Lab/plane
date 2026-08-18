# 后端开发规范

## 适用范围

适用于 `apps/api` 的 Django、Django REST Framework、Celery、数据库、认证、对象存储和测试代码。

## 分层与边界

- URL 只负责路由；view/viewset 负责请求编排；serializer 负责输入验证和输出表示。
- 数据模型及其约束位于 `plane/db/models`，不要把 HTTP 语义写入 model。
- `plane/api` 与 `plane/app` 是不同接口面。新增端点前先选择与现有认证方式和消费者一致的接口面。
- 通用能力进入明确命名的 service/helper；不要把大量业务逻辑塞入 serializer method 或 signal。
- 跨领域写操作应明确事务边界；失败时不能留下部分成功状态。

## API 设计

- 路径、HTTP method、状态码、分页和错误结构沿用相邻端点。
- 所有外部输入必须由 serializer 或明确 validator 校验，拒绝未知或越权字段。
- 对外响应不得泄漏内部异常、密钥、绝对路径或未经授权的对象字段。
- 列表接口避免 N+1，使用 `select_related`、`prefetch_related` 和已有查询工具。
- 新增排序、过滤和搜索字段时使用白名单，不直接把输入传给 ORM 表达式。
- 破坏性 API 变更必须提供兼容期、迁移说明或新版本端点。
- 涉及 OpenAPI 的端点同步维护 schema 和示例。

## 认证、授权与租户隔离

- 每个 endpoint 明确认证方式、workspace/project 范围和角色要求。
- 授权必须基于服务端查询到的成员关系，不能信任请求体中的 workspace/project/user ID。
- 对对象执行更新、删除、导出、恢复前都要验证对象归属和操作权限。
- API token、session、guest 和 public access 应分别覆盖 contract test。
- 任何跨 workspace/project 查询都视为高风险，PR 中必须写出隔离验证场景。

## 模型与数据库迁移

- 已进入任何共享环境的 migration 不得修改、重命名或删除；通过新 migration 修正。
- schema 变更和数据回填分开，优先使用 expand-contract 兼容滚动发布。
- 新字段优先 nullable/default-safe，再回填数据，最后收紧约束。
- 大表数据迁移必须批处理，评估锁、索引、事务时长和回滚策略。
- 索引应来自实际查询模式；新增唯一约束前检查和清理历史冲突数据。
- `RunPython` 尽可能提供 reverse function；不可逆时在 design 和发布说明中明确。
- migration 中使用 historical model，不导入当前业务 model。

## Celery 与外部系统

- 后台任务必须可安全重试，使用业务幂等键或状态检查防止重复副作用。
- 设置合理超时、重试次数和退避；永久失败应可观测并支持人工恢复。
- 不在数据库事务提交前调度依赖该数据的任务，必要时使用 `transaction.on_commit`。
- HTTP、邮件、Webhook、S3/MinIO 等外部调用必须处理超时、部分失败和安全日志脱敏。
- URL 抓取、Webhook 和导入功能必须使用现有 SSRF/URL 安全工具。

## Python 风格与错误处理

- 遵守 `apps/api/pyproject.toml` 的 Ruff 配置：120 行宽、双引号、4 空格。
- 函数签名和关键返回值使用类型注解；不要用宽泛 `except Exception` 静默吞错。
- 将可预期业务错误转换为稳定 API 错误；意外错误记录上下文并交给统一异常处理。
- 日志包含请求/对象关联标识，但不包含 token、Cookie、密码或敏感正文。
- 新文件保留仓库版权和 `SPDX-License-Identifier: AGPL-3.0-only` 头。

## 测试

测试位于 `apps/api/plane/tests`：

- `unit/`：模型、serializer、utility、middleware 和任务的隔离行为。
- `contract/api/`：API token 等对外 API 契约。
- `contract/app/`：session 应用接口、权限和领域行为。
- `smoke/`：最关键的端到端存活路径。
- 使用 pytest fixture，避免 `setUp/tearDown` 和测试间共享状态。
- 数据库测试使用 `@pytest.mark.django_db` 并声明 `unit`、`contract`、`smoke` 或 `slow` marker。
- 单元/大部分契约测试 mock 外部系统，测试不能依赖真实公网服务。

仓库保留以下隔离 Docker 测试命令，供 CI 或明确要求的后端专项检查使用。API 变更由 CI 运行一次现有 pytest
套件；它们需要 Docker，不是 Windows 日常开发和 Tester 验收的步骤，也不得复制到 OpenSpec 任务清单：

```bash
docker compose -f docker-compose-test.yml run --rm --build api-tests pytest -m unit
docker compose -f docker-compose-test.yml run --rm --build api-tests pytest -m contract
docker compose -f docker-compose-test.yml up --build --abort-on-container-exit --exit-code-from api-tests
docker compose -f docker-compose-test.yml down -v
```

专项检查需要时可运行：

```bash
ruff check apps/api
ruff format --check apps/api
```

CI 中不得使用 `ruff check --fix` 代替检查；修复命令只用于本地明确修改。

## 后端完成清单

- 输入验证、权限、租户隔离和异常映射完整。
- 查询数量、事务边界、任务幂等和外部调用失败已评估。
- migration 可在生产数据量下执行，并有备份/回滚说明。
- unit/contract 测试覆盖正常、无权限、非法输入和失败路径。
- CI 已运行与风险相称的直接相关测试，Tester 已通过测试环境中的最小 OpenSpec 用户旅程。
