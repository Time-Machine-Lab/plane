# AI 本地测试与提案验收规范

## 为什么本地开发仍需要测试规范

测试由 AI 执行，并不意味着可以省略测试规范。规范的作用不是要求人工操作，而是约束 AI：

- 不能把“代码已写完”“类型能通过”当成业务提案已经实现。
- 必须把 OpenSpec 中的每条需求和场景转换为可执行的本地验证。
- 必须实际运行命令、启动必要服务、观察结果并留下可复核证据。
- 无法运行的验证必须标记为未验证，不能根据代码推断为通过。

本规范以本地开发验收为主。CI 是后续合并保护，不替代 AI 在完成开发时的本地验收。

## 验收对象

AI 开始实施前必须阅读当前 change 的：

- `proposal.md`：目标、范围、非目标和风险。
- `specs/**/*.md`：需求和 GIVEN/WHEN/THEN 场景。
- `design.md`：模块契约、迁移和测试设计（存在时）。
- `tasks.md`：实现与验证任务。

测试不能只围绕修改的函数设计，必须回到 proposal/specs 验证用户最终能够观察到的结果。

## 本地验收流程

### 1. 建立验收映射

编码前，AI 在 `tasks.md` 中为每条需求或场景确定：

| 内容 | 说明 |
| --- | --- |
| Requirement/Scenario | 对应的 OpenSpec 需求或场景 |
| Affected module | web、admin、space、api、live 或共享包 |
| Verification | 静态检查、单元测试、契约测试或本地运行场景 |
| Command/Evidence | 要执行的命令、HTTP 请求、页面操作或可观察结果 |
| Result | `pending`、`pass`、`fail` 或 `unverified` |

每条必需场景都要有验证方式。无法客观验证的需求应先修正 spec，而不是进入编码。

### 2. 执行最小相关检查

AI 每次修改完成后先运行受影响模块的快速检查：

- 格式检查。
- Lint，且不得新增 warning。
- TypeScript 类型检查或 Python Ruff 检查。
- 直接相关的 unit/contract test。
- 受影响模块的 build（该模块存在 build 时）。

快速检查失败时先修复，不继续用更大范围测试掩盖局部问题。

### 3. 执行自动化行为测试

- 新功能必须增加正常、边界和失败路径测试。
- bug 修复先添加能稳定复现缺陷的测试，再验证修复后通过。
- 权限变更至少覆盖允许访问、低权限、其他 workspace/project 和未认证场景。
- 跨模块契约同时验证提供方和消费方，不能只 mock 掉本次真正修改的边界。
- 不通过删除断言、放宽预期、增加无理由 skip 或吞掉错误来让测试变绿。

### 4. 启动本地服务验证真实场景

只要 proposal 描述了用户可见行为，仅运行单元测试和构建还不够。AI 应启动必要的本地服务，
按 spec 场景完成实际验收：

- 前端：打开真实路由，验证正常、loading、empty、error、权限和关键交互状态。
- API：使用本地测试数据发送真实请求，检查状态码、响应、数据库副作用和权限隔离。
- 实时协作：验证连接、鉴权、更新传播、重连和持久化。
- 共享包：在至少一个真实消费应用中验证公共行为。
- 跨模块：从用户入口贯穿到 API/实时服务，至少完成一条完整业务路径。

AI 可以使用当前环境已有的浏览器自动化、HTTP 客户端或测试工具，但不应仅为一次验收随意引入
新的长期依赖。需要保留本地服务供用户复核时，报告访问 URL；临时服务则在验证结束后清理。

### 5. 按风险执行回归

不要求每个小修改都运行全库测试。使用以下范围：

| 风险 | 回归范围 |
| --- | --- |
| 低 | 目标文件/包检查、直接测试、目标模块 build |
| 中 | 目标模块完整检查，以及直接消费者的类型检查、测试或 build |
| 高 | 全库前端检查/build、完整 API Docker suite、跨模块本地场景 |

以下情况默认高风险：认证授权、数据库 migration、公共类型/API、共享状态、编辑器数据、
实时协议、导入导出、安全修复、基础配置和上游大版本同步。

### 6. 逐条验收提案

所有实现任务完成后，AI 必须重新阅读 proposal 和全部 delta specs，而不是只查看 `tasks.md`：

1. 对每个 Requirement/Scenario 找到对应自动化测试或本地行为证据。
2. 运行最终所需的检查和回归命令。
3. 在 `tasks.md` 末尾维护 `## Local acceptance record`。
4. 记录环境、命令、结果摘要、场景证据和已知限制。
5. 所有必需项为 `pass` 后，才可将 change 报告为已验收。

`fail` 表示实现或测试失败；`unverified` 表示环境或依赖使测试无法运行。两者都不能算验收通过。

## 模块验证矩阵

| 变更 | 本地最低验证 |
| --- | --- |
| `apps/web`、`apps/admin`、`apps/space` | format、lint、types、目标应用 build、相关测试、真实路由交互 |
| `apps/api` 非数据库代码 | Ruff、相关 unit/contract pytest、受影响端点真实请求 |
| API/权限 | unit + API/app contract、允许/拒绝/跨租户请求 |
| 模型/migration | migration 测试、数据前后状态、contract；按风险运行完整 Docker pytest |
| `apps/live` | format、lint、types、Vitest、build、实际连接/传播场景 |
| `packages/*` | 包检查/build、受影响消费者检查、消费应用行为 |
| UI/Propel/Editor | Storybook build、交互/可访问性状态、真实消费页面 |
| i18n | sync check、类型生成、变量/ICU 结构和实际页面文案 |
| proxy/Compose | 配置解析、受影响服务启动、health 和关键路由 smoke |
| 跨模块 | 各模块验证之和，加至少一条完整用户路径 |

## 前端和 Node 测试

- 使用目标包已经配置的测试框架；当前 `apps/live` 和 codemods 使用 Vitest。
- 测试文件遵循现有 `*.test.ts(x)` 或 `*.spec.ts(x)` 命名。
- 纯函数、store 和 service 覆盖失败、边界、并发、重试和回滚状态。
- 组件测试关注用户可见行为、键盘和异步状态，不锁定无意义 DOM 结构。
- Storybook 验证组件隔离状态，但不能代替业务逻辑和真实页面验收。
- 时间、随机数、网络和浏览器 API 必须可控，测试结束后恢复 mock 和 timer。

仓库目前没有为 `web`、`admin`、`space` 配置统一的 test script。涉及这些应用时，AI 必须在
OpenSpec design/tasks 中明确测试放置位置和执行方式；不能因为缺少现成脚本而跳过行为验收。

## API 测试

- pytest marker 使用已注册的 `unit`、`contract`、`smoke`、`slow`。
- `contract/api` 与 `contract/app` 按认证接口面选择正确 fixture。
- 数据库测试显式使用 `django_db`，fixture 只创建验证场景所需的最小数据。
- 单元测试 mock 外部服务；需要真实依赖时使用 `docker-compose-test.yml` 隔离栈。
- 权限测试必须验证对象归属和 workspace/project 隔离。
- 测试不得访问真实生产系统或修改非测试数据。

## 常用本地命令

全库静态检查与构建：

```bash
pnpm check
pnpm build
```

局部前端/共享包检查：

```bash
pnpm turbo run check:format check:lint check:types --filter=<package-name>
pnpm turbo run build --filter=<package-name>
```

实时服务：

```bash
pnpm --filter=live test
pnpm --filter=live build
```

API 定向测试：

```bash
docker compose -f docker-compose-test.yml run --rm --build api-tests pytest -m unit
docker compose -f docker-compose-test.yml run --rm --build api-tests pytest -m contract
```

API 完整测试：

```bash
docker compose -f docker-compose-test.yml up --build --abort-on-container-exit --exit-code-from api-tests
docker compose -f docker-compose-test.yml down -v
```

命令只是基线。AI 必须根据 proposal 场景补充实际页面、请求、数据或实时连接验证。

## AI 结果报告要求

AI 最终报告必须区分：

- `Passed`：实际运行且成功的命令和场景。
- `Failed`：运行失败及其原因。
- `Unverified`：没有执行或环境无法执行的项目。
- `Residual risk`：测试通过后仍存在的风险和未覆盖范围。

禁止使用“应该没问题”“从代码看可以”代替测试证据。没有执行的测试必须明确说明，不能写成通过。

## 本地验收记录模板

在 OpenSpec `tasks.md` 末尾使用以下结构：

```markdown
## Local acceptance record

- Environment: <OS/runtime/services/test data>
- Date/commit: <date and commit or working tree state>

| Requirement/Scenario | Verification | Result | Evidence |
| --- | --- | --- | --- |
| <spec reference> | <command or local behavior> | pass/fail/unverified | <summary> |

### Commands

- `<command>`: pass/fail

### Residual risks

- <remaining risk, or None>
```

## 验收完成条件

- proposal 和 specs 的每个必需场景都有本地证据并标记为 `pass`。
- 相关格式、Lint、类型、自动化测试和 build 已实际运行通过。
- 用户可见功能已在本地运行环境验证，而不是只做代码审查。
- 没有新增 warning、skip、only、临时断言或被隐藏的失败。
- `tasks.md` 的 Local acceptance record 完整记录命令、结果和剩余风险。

任一必需项为 `fail` 或 `unverified` 时，AI 必须报告 change 尚未通过验收。
