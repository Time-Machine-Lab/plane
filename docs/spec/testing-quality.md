# AI 测试与 OpenSpec 提案验收规范

## 目标

测试由 AI 执行不等于可以省略测试过程。AI 必须把 OpenSpec 的 Requirement/Scenario 转换为可执行验证，
实际运行命令或用户场景，并留下可复核证据。代码审查、类型推断和“实现看起来正确”都不是验收证据。

本项目采用分级测试，避免每次修改都启动或部署完整 Plane：Windows 本地负责快速反馈和前端运行；
需要真实 API、数据库、Worker、Live 或跨模块环境时，按照
[测试环境 Runbook](./test-environment.md) 直接部署隔离测试服务器。CI 是合并保护，不是日常测试的必经路径。

## 验收输入

实施和测试都必须阅读当前 change 的：

- `proposal.md`：目标、范围、非目标和风险。
- `specs/**/*.md`：Requirements 与 GIVEN/WHEN/THEN 场景。
- `design.md`：模块契约、迁移、回滚和测试设计（存在时）。
- `tasks.md`：实现任务、验证计划和验收记录。
- 本规范、测试环境 Runbook 和所有受影响模块规范。

测试必须验证用户或下游模块可观察的结果，不能只围绕被修改的函数编写。

## L1-L4 分级测试

| 等级            | 用途                                         | 最低验证                                       | 运行位置                  |
| --------------- | -------------------------------------------- | ---------------------------------------------- | ------------------------- |
| L1 快速检查     | 每轮实现反馈                                 | format、lint、types/Ruff、相关单测、目标 build | Windows 本地              |
| L2 模块运行验收 | 前端、UI、共享状态和单模块用户行为           | 启动本地前端并验证真实页面                     | 本地前端 + 测试 API       |
| L3 提案集成验收 | API、权限、migration、任务、Live、跨模块变更 | 部署受影响服务并验证真实契约、数据和用户路径   | 隔离测试服务器            |
| L4 发布级回归   | 高风险、合并或正式发布前                     | 全库检查/测试、迁移演练和关键业务回归          | 测试服务器 + 正式发布流程 |

使用能覆盖风险的最低等级：

- 纯文档、类型、工具函数通常为 L1。
- `apps/web`、`apps/admin`、`apps/space` 或 UI 修改通常为 L1 + L2。
- `apps/api`、后台任务或 `apps/live` 修改为 L1 + L3。
- 权限、migration、公共 API/类型、实时协议、安全和跨模块变更至少为 L1 + L3，合并前升级 L4。
- Dockerfile、Compose、依赖锁和基础镜像变更必须实际重建受影响镜像。

测试等级是风险下限，不是命令数量目标。无需为低风险修改重复部署完整 Plane；也不得把需要真实依赖的
场景降级为 mock 后的 L1 并声称完成集成验收。

## 实现 Agent 职责

实现 Agent 必须：

1. 在编码前将每条 Requirement/Scenario 映射到验证等级、命令和证据类型。
2. 为新功能增加正常、边界与失败路径测试；bug 修复增加稳定复现测试。
3. 完成实现后执行所有 L1 检查并处理失败。
4. 保持工作区可测试，说明改动模块、运行过的命令和已知限制。
5. 不自行作出 OpenSpec 最终验收结论；将最终验证交给全新的 Tester 子 Agent。

实现 Agent 的 L1 结果是交接条件，不替代 Tester 的独立复核。

## 独立 Tester 子 Agent

实现任务结束后，主 Agent 必须创建一个全新的 Tester 子 Agent。Tester 与实现 Agent 共享工作区和权限，
因此独立指职责与判断独立，不是进程、凭据或安全隔离。

Tester 初始上下文只提供 change 名称、change 路径、测试规范路径和工作区已准备的事实，不应传递实现过程
中的正确性判断。Tester 必须自行读取 proposal、design、specs、tasks 和适用规范。

Tester 负责：

- 复核 Requirement/Scenario 与测试等级选择。
- 重跑必要 L1，并按风险执行 L2、L3 或 L4。
- 按 [测试环境 Runbook](./test-environment.md) 使用 `start-local.ps1` 或 `deploy-test.ps1`。
- 验证真实页面、请求、权限、数据副作用、Worker 或实时连接。
- 不修改产品代码；失败时记录稳定复现步骤并交回实现 Agent。
- 写入 `openspec/changes/<change>/verification.md`，并给出 `pass`、`fail` 或 `unverified` 结论。

实现 Agent 修复失败后，主 Agent 必须创建另一个全新的 Tester 子 Agent重新执行失败场景和必要回归，
不得复用原 Tester 直接宣布通过。

## 验收映射

`tasks.md` 和 `verification.md` 应为每个必需场景记录：

| 字段                 | 内容                                         |
| -------------------- | -------------------------------------------- |
| Requirement/Scenario | OpenSpec 中的准确引用                        |
| Affected module      | web、admin、space、api、live、proxy 或共享包 |
| Level                | L1、L2、L3 或 L4                             |
| Verification         | 静态检查、单测、契约、请求、页面或实时场景   |
| Result               | `pending`、`pass`、`fail` 或 `unverified`    |
| Evidence             | 脱敏命令输出、部署 ID、截图/报告或可观察结果 |

每条必需场景都必须可客观验证。无法验证的需求应先修正 spec，不应直接进入编码。

## 自动化测试要求

- 新功能覆盖正常、边界和失败路径。
- bug 修复先用测试稳定复现缺陷，再验证修复通过。
- 权限变更至少覆盖允许访问、低权限、其他 workspace/project 和未认证场景。
- 跨模块契约同时验证提供方和消费方，不能 mock 掉本次真正修改的边界后声称契约通过。
- 测试数据只包含场景所需的最小对象，且不得访问生产系统或修改非测试数据。
- 不得通过删除断言、放宽预期、增加无理由 skip/only 或吞掉异常让测试变绿。
- 时间、随机数、网络和浏览器 API 必须可控，测试结束后恢复 mock 和 timer。

## 模块最低验证

| 变更                                   | 最低验证                                                     |
| -------------------------------------- | ------------------------------------------------------------ |
| `apps/web`、`apps/admin`、`apps/space` | format、lint、types、目标 build、相关测试、真实路由交互      |
| `apps/api` 普通代码                    | Ruff、相关 unit/contract pytest、测试环境端点请求            |
| API/权限                               | unit + API/app contract、允许/拒绝/跨租户真实请求            |
| 模型/migration                         | migration 测试、数据前后状态、contract、测试环境迁移和 smoke |
| `apps/live`                            | format、lint、types、Vitest、build、真实连接/传播/重连场景   |
| `packages/*`                           | 包检查/build、直接消费者检查、消费应用行为                   |
| UI/Propel/Editor                       | Storybook build、交互/可访问性状态、真实消费页面             |
| i18n                                   | sync check、类型生成、变量/ICU 结构和实际页面文案            |
| proxy/Compose                          | 配置解析、受影响服务启动、health 和关键路由 smoke            |
| 跨模块                                 | 各模块验证之和，加至少一条完整用户路径                       |

## 前端与 Node 测试

- 使用目标包已配置的框架；测试文件遵循现有 `*.test.ts(x)` 或 `*.spec.ts(x)` 命名。
- 纯函数、store 和 service 覆盖失败、边界、并发、重试和回滚状态。
- 组件测试关注用户可见行为、键盘、可访问性和异步状态，不锁定无意义 DOM 结构。
- Storybook 验证隔离组件状态，但不替代业务逻辑和真实页面验收。
- 仓库未给 `web`、`admin`、`space` 提供统一 test script 时，OpenSpec design/tasks 必须明确测试放置位置和执行方式。
- 用户可见功能使用 `scripts/test/start-local.ps1` 启动本地应用，连接隔离测试 API 完成 L2。

## API 与真实依赖测试

- pytest marker 使用已注册的 `unit`、`contract`、`smoke`、`slow`。
- `contract/api` 与 `contract/app` 按认证接口面选择正确 fixture。
- 数据库测试显式使用 `django_db`，fixture 只创建最小数据。
- 单元测试可以 mock 外部服务，但真实依赖契约必须在 L3 测试环境验证。
- 权限测试必须验证对象归属和 workspace/project 隔离。
- 无 Docker 的 Windows 环境不要求运行本地 Compose；使用 `scripts/test/deploy-test.ps1` 部署测试服务器。
- 能在本地运行 Docker 时仍可使用 `docker-compose-test.yml`，但它不是当前 Windows 工作流的前置条件。

## 常用命令

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

Windows 本地前端：

```powershell
.\scripts\test\start-local.ps1 -Apps web
```

直接部署受影响服务到测试环境：

```powershell
.\scripts\test\deploy-test.ps1 -Services api
```

所有脚本参数、私有配置、端口、健康检查和回滚步骤以
[测试环境 Runbook](./test-environment.md) 与脚本帮助为准。

## 测试结果和证据

Tester 的 `verification.md` 必须区分：

- `Passed`：实际运行成功的命令和场景。
- `Failed`：运行失败、稳定复现步骤及可观察结果。
- `Unverified`：因环境或依赖未能执行的必需项。
- `Residual risk`：已通过范围之外仍存在的风险。

证据必须脱敏。不得记录真实服务器地址、账号、密码、连接串、认证 Header、Cookie、Token 或私有配置
内容。使用部署 ID、服务逻辑名、HTTP 状态、脱敏摘要和本地/测试环境逻辑名称即可。

## OpenSpec 验收记录

`verification.md` 使用测试环境 Runbook 中的模板。`tasks.md` 末尾保留精简索引：

```markdown
## Acceptance record

- Tester: <new tester agent identifier>
- Verification report: `./verification.md` (在实际 `tasks.md` 中使用 Markdown 链接)
- Selected level: <L1/L2/L3/L4>
- Verdict: pass/fail/unverified
- Residual risks: <summary or None>
```

## 验收完成条件

- proposal 和 specs 的每个必需场景都在 `verification.md` 中有证据并标记为 `pass`。
- 相关 format、lint、types/Ruff、自动化测试和 build 已实际运行通过。
- 用户可见功能完成 L2；真实后端/数据/实时或跨模块变更完成 L3；高风险发布按要求完成 L4。
- Tester 是实现结束后新创建的子 Agent，且未修改产品代码。
- 没有新增 warning、skip、only、临时断言或被隐藏的失败。
- `tasks.md` 链接最终 `verification.md`，结论和剩余风险一致。

任一必需项为 `fail` 或 `unverified` 时，AI 必须报告 change 尚未通过验收，不得标记完成或归档。
