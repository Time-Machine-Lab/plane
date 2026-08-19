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

## 唯一开发与验收流程

```text
OpenSpec -> 开发 -> 受影响 CI 检查/测试 -> deploy-test.ps1 -> 独立 Tester 验收 -> 完成或返工
```

- OpenSpec 说明要改什么、重要风险边界、必要技术决策和可观察验收场景，不嵌入测试等级或命令矩阵。
- pre-commit 只负责暂存文件格式和 lint；CI 负责受影响模块的 lint、类型、构建及已有自动化测试。
- 开发 Agent 只在实现过程中运行有助于定位问题的 focused 检查，不为交接重复执行全库检查。
- 运行时变更只通过 `scripts/test/deploy-test.ps1` 部署一次；脚本负责服务选择、迁移、启动和健康检查。
- Tester 把 OpenSpec 场景合并为 3-7 条最小用户旅程，不重复 CI 检查，也不在正常成功路径分析日志。
- 失败后由开发 Agent 修复并重新部署，原 Tester 只复测失败旅程及一条必要的相邻回归。

## OpenSpec 最小要求

- `proposal.md`：目标、范围、非目标、受影响模块和适用规范。
- `specs/*`：使用可观察、可执行的行为场景表达需求。
- `design.md`：只在存在重要架构决策、跨模块契约、迁移、发布或回滚问题时创建或充实。
- `tasks.md`：保持为开发、自动化验证、部署、验收四类结果，不展开测试等级和重复命令清单。
- `verification.md`：记录 Tester 对必需旅程的精简 `pass`/`fail`/`blocked` 证据；环境前置条件缺失记为 `blocked`。

目录、工具链或模块边界变化时，同一变更应同步更新对应规范。命令和参数以仓库脚本及其帮助输出为事实来源。
