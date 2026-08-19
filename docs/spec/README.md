# Plane 团队开发规范

本目录是 Plane 团队定制版本的规范入口。目标是让开发遵循上游结构，同时把日常流程保持为一条可以实际执行的轻量链路。

## 模块与规范映射

| 模块                     | 主要路径                                      | 职责                                      | 适用规范                                           |
| ------------------------ | --------------------------------------------- | ----------------------------------------- | -------------------------------------------------- |
| 主应用、管理端、公开空间 | `apps/web`、`apps/admin`、`apps/space`        | 用户界面和交互                            | [前端开发规范](./frontend-development.md)          |
| 后端 API                 | `apps/api`                                    | Django API、认证、模型、任务和迁移        | [后端开发规范](./backend-development.md)           |
| 实时协作                 | `apps/live`                                   | Hocuspocus/Yjs、WebSocket 和导出          | [实时协作开发规范](./realtime-development.md)      |
| 共享包                   | `packages/*`                                  | UI、状态、服务、类型、编辑器、i18n 和工具 | [共享包开发规范](./shared-packages-development.md) |
| 代理与部署               | `apps/proxy`、`deployments/*`、Docker/Compose | 路由、镜像和部署资产                      | [模块与目录结构说明](./module-structure.md)        |

所有代码变更同时遵守 [通用开发规范](./general-development.md)。所有运行时验收遵守
[测试与质量规范](./testing-quality.md) 和 [测试环境 Runbook](./test-environment.md)。更深目录存在
`AGENTS.md` 时，还必须遵守距离目标文件最近的指令。

Discord 通知卡片的新增或调整同时遵守
[Discord 通知卡片设计规范](./discord-card-design.md)。

## AI 读取规则

1. 先根据上表读取受影响模块规范；跨模块变更读取所有相关规范。
2. 添加或移动目录、包、运行时模块时读取模块结构说明。
3. 部署或测试运行时行为前读取测试环境 Runbook。
4. 遵循现有模块边界和实现模式，避免为小改动引入新的抽象或无关重构。

## 开发与验证流程

```text
OpenSpec -> 实现与必要开发检查 -> 新的独立 Tester 子 Agent 验证 -> 完成或返工
```

- OpenSpec 说明要改什么、重要风险边界、必要技术决策和可观察验收场景，不嵌入测试等级或命令矩阵。
- 实现 Agent 运行与需求和改动风险直接相关的检查；自动化测试按回归价值决定，不默认新增。
- 实现完成后，主 Agent 创建一个未参与实现的新 Tester 子 Agent；主 Agent 和实现 Agent 都不能替代最终验收。
- Tester 只验证需求目标、直接影响范围和确有必要的相邻回归，不设置固定场景数量。
- 本地或离线能够确认目标时不部署；必须依赖运行环境时，才使用 `scripts/test/deploy-test.ps1` 部署受影响服务。
- 验证失败后由实现 Agent 修复，再由同一个 Tester 只复验失败范围和必要的相邻行为。

## OpenSpec 最小要求

- `proposal.md`：目标、范围、非目标、受影响模块和适用规范。
- `specs/*`：使用可观察、可执行的行为场景表达需求。
- `design.md`：只在存在重要架构决策、跨模块契约、迁移、发布或回滚问题时创建或充实。
- `tasks.md`：保持为实现、必要开发检查和独立 Tester 验证；只在需求需要时加入自动化测试或测试环境部署。
- `verification.md`：仅在 OpenSpec、用户或变更风险要求长期保留证据时创建，不作为所有 change 的固定产物。

目录、工具链或模块边界变化时，同一变更应同步更新对应规范。命令和参数以仓库脚本及其帮助输出为事实来源。
