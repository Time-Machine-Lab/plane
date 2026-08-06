# Plane 团队开发规范

本目录是 Plane 团队定制版本的开发规范入口。规范依据当前仓库结构、根目录
`AGENTS.md`、上游贡献指南和现有工具链整理，供团队成员、AI Agent 和 OpenSpec
共同使用。

## 模块划分

当前项目分为以下开发模块：

| 模块             | 主要路径                           | 职责                                              | 必读规范                                           |
| ---------------- | ---------------------------------- | ------------------------------------------------- | -------------------------------------------------- |
| 主应用前端       | `apps/web`                         | 登录、工作区、项目、工作项等主要交互界面          | [前端开发规范](./frontend-development.md)          |
| 管理端前端       | `apps/admin`                       | 实例、认证、邮件、AI 和工作区管理                 | [前端开发规范](./frontend-development.md)          |
| 公开空间前端     | `apps/space`                       | 对外发布的项目、工作项和页面                      | [前端开发规范](./frontend-development.md)          |
| 后端 API         | `apps/api`                         | Django API、认证、数据模型、任务和迁移            | [后端开发规范](./backend-development.md)           |
| 实时协作服务     | `apps/live`                        | Hocuspocus/Yjs 协同编辑、WebSocket 和 PDF 导出    | [实时协作开发规范](./realtime-development.md)      |
| 网关代理         | `apps/proxy`                       | Caddy 路由、TLS、上传限制和反向代理               | 通用规范、测试规范和结构说明                       |
| 共享前端/Node 包 | `packages`                         | UI、状态、服务、类型、编辑器、i18n 和工具库       | [共享包开发规范](./shared-packages-development.md) |
| 部署层           | `deployments`、根目录 Compose 文件 | Docker Compose、AIO、Kubernetes、Swarm 和备份恢复 | 通用规范、测试规范和结构说明                       |

所有模块同时遵守：

- [通用开发规范](./general-development.md)
- [测试与质量规范](./testing-quality.md)
- [测试环境 Runbook](./test-environment.md)
- [模块与目录结构说明](./module-structure.md)

## AI 规范选择规则

AI 在分析、设计或修改代码前必须按受影响路径选择规范：

1. 始终阅读本索引、通用开发规范和测试与质量规范；需要启动页面、部署或运行验收时同时阅读测试环境 Runbook。
2. 修改 `apps/web`、`apps/admin` 或 `apps/space` 时阅读前端开发规范。
3. 修改 `apps/api` 时阅读后端开发规范。
4. 修改 `apps/live` 时阅读实时协作开发规范。
5. 修改 `packages/*` 时阅读共享包开发规范；涉及 UI 时同时阅读前端开发规范。
6. 修改 `apps/proxy`、`deployments`、Dockerfile、Compose 或 CI 时阅读模块结构、通用和测试规范。
7. 跨模块改动必须阅读全部相关规范，并在设计与 PR 中列出跨模块契约。
8. 更深层目录存在 `AGENTS.md` 时，还必须遵守距离目标文件最近的指令。

## OpenSpec 使用要求

OpenSpec 已通过 `openspec/config.yaml` 注入本目录的选择规则。每个 change 的产物必须做到：

- `proposal.md`：声明受影响模块、适用规范、范围和非目标。
- `design.md`：说明模块边界、API/数据/事件契约、迁移与回滚策略。
- `specs/*`：使用可验证的行为场景，不使用纯实现描述代替需求。
- `tasks.md`：按模块拆分任务，为每组任务列出验证等级和命令，并维护验收记录。
- 实施前重新读取相关规范；发现设计偏差时先更新 OpenSpec 产物，再继续编码。
- 实施完成后必须创建全新的 Tester 子 Agent；Tester 按测试环境 Runbook 独立验证并写入
  `openspec/changes/<change>/verification.md`，只有全部必需场景通过才可验收 change。

## 规范维护

当目录、工具链、运行时版本或架构边界发生变化时，同一个 PR 必须更新对应规范。
规范中的命令应以当前 `package.json`、`pyproject.toml`、Compose 文件和 CI 为事实来源，
避免复制已经失效的版本说明。
