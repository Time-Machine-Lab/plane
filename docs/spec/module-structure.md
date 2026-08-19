# 模块与目录结构说明

本文说明仓库中稳定的模块边界和关键目录职责。功能内部的叶子目录很多，新增目录时应沿用
相邻领域的组织方式，不要为了单个功能在仓库根部创建新的架构层。

## 根目录

| 路径                       | 职责                                                     |
| -------------------------- | -------------------------------------------------------- |
| `apps/`                    | 可独立运行或部署的应用与服务                             |
| `packages/`                | 被多个应用复用的 TypeScript/React 包                     |
| `deployments/`             | 社区版部署资产、安装、升级、备份与恢复脚本               |
| `docs/`                    | 团队和项目文档；`docs/spec` 保存长期开发规范             |
| `openspec/`                | OpenSpec 主规格、进行中的 change、归档 change 和项目配置 |
| `.github/`                 | GitHub Issue/PR 模板、CI 工作流和代码生成指令            |
| `.husky/`                  | Git hooks；提交前触发 lint-staged                        |
| `.codex/`、`.claude/`      | 仓库级 AI 工具指令和技能，不存放业务代码                 |
| `.codegraph/`              | 代码图工具配置或索引元数据                               |
| `.idx/`                    | 云开发环境配置                                           |
| `docker-compose-local.yml` | 本地依赖与应用开发栈                                     |
| `docker-compose-test.yml`  | 隔离的 API pytest 测试栈                                 |
| `docker-compose.yml`       | 社区版完整运行栈                                         |
| `pnpm-workspace.yaml`      | pnpm workspace、catalog 依赖版本和 overrides             |
| `turbo.json`               | monorepo 构建任务、依赖关系和缓存输入输出                |

## 应用目录 `apps`

### `apps/web`

主产品前端，开发端口为 `3000`。

| 子目录             | 职责                                                          |
| ------------------ | ------------------------------------------------------------- |
| `app/`             | React Router 路由入口、页面、布局、错误页和路由类型           |
| `app/routes/`      | core/extended 路由声明、兼容跳转和路由合并逻辑                |
| `core/components/` | 主应用核心业务组件                                            |
| `core/layouts/`    | 页面和工作区布局                                              |
| `core/hooks/`      | 仅主应用使用的业务 hooks                                      |
| `core/services/`   | 主应用专用服务封装；可复用服务应进入 `@plane/services`        |
| `core/store/`      | 主应用专用 MobX store；跨应用状态应进入 `@plane/shared-state` |
| `core/lib/`        | 主应用的 provider、wrapper 和基础组合逻辑                     |
| `helpers/`         | 无状态、应用专用辅助函数                                      |
| `public/`          | 静态资源和 PWA 产物；不要手工修改生成的 service worker 文件   |
| `styles/`          | 应用级全局样式                                                |
| `nginx/`           | Web 镜像静态服务配置                                          |

### `apps/admin`

实例管理前端，开发端口为 `3001`，入口通常为 `/god-mode/`。

| 子目录                         | 职责                                 |
| ------------------------------ | ------------------------------------ |
| `app/`                         | 管理端路由、页面、布局和应用入口     |
| `components/`                  | 认证、实例、工作区和通用管理组件     |
| `store/`                       | 管理端实例、用户、主题和工作区状态   |
| `providers/`                   | store、实例、用户和通知上下文        |
| `hooks/`、`helpers/`、`lib/`   | 管理端专用 hooks、辅助函数和基础封装 |
| `public/`、`styles/`、`nginx/` | 静态资源、全局样式和镜像服务配置     |

### `apps/space`

公开发布空间前端，开发端口为 `3002`。

| 子目录                         | 职责                                                   |
| ------------------------------ | ------------------------------------------------------ |
| `app/`                         | 公开页面路由、工作区/项目页面和错误页                  |
| `components/`                  | 公开视图、编辑器、工作项和实例组件                     |
| `store/`                       | Space 专用状态                                         |
| `types/`                       | 只在 Space 使用的补充类型；共享类型进入 `@plane/types` |
| `hooks/`、`helpers/`、`lib/`   | Space 专用交互与辅助逻辑                               |
| `public/`、`styles/`、`nginx/` | 静态资源、样式和镜像服务配置                           |

### `apps/api`

Django/DRF 后端，容器内主要监听 `8000`。

| 子目录                        | 职责                                                   |
| ----------------------------- | ------------------------------------------------------ |
| `plane/settings/`             | common/local/production/test 配置、缓存和对象存储配置  |
| `plane/db/models/`            | Django 数据模型                                        |
| `plane/db/migrations/`        | 数据库 schema 与数据迁移；已应用迁移不可修改           |
| `plane/db/management/`        | Django 管理命令                                        |
| `plane/api/`                  | 对外 API 的 urls、views、serializers 和 middleware     |
| `plane/app/`                  | Web 应用会话接口及其 permissions、views 和 serializers |
| `plane/authentication/`       | 登录、会话和认证流程                                   |
| `plane/bgtasks/`              | Celery 后台任务                                        |
| `plane/middleware/`           | Django 全局中间件                                      |
| `plane/throttles/`            | API 限流策略                                           |
| `plane/analytics/`            | 分析相关后端能力                                       |
| `plane/space/`                | 公开 Space 后端接口                                    |
| `plane/license/`              | 许可证相关运行逻辑，不得与仓库 AGPL 文件混淆           |
| `plane/seeds/`                | 初始化数据                                             |
| `plane/utils/`                | 后端通用工具和基础能力                                 |
| `plane/tests/`                | unit、contract、smoke 测试和 fixtures                  |
| `templates/`、`plane/static/` | 邮件/错误模板和 Django 静态资源                        |
| `bin/`                        | API、worker、beat 和 migrator 容器入口脚本             |
| `requirements/`               | base/local/production/test Python 依赖集合             |
| `tests/`                      | API 测试运行说明，不作为测试代码主目录                 |

### `apps/live`

实时协作 Node.js 服务。

| 子目录             | 职责                                         |
| ------------------ | -------------------------------------------- |
| `src/controllers/` | HTTP/WebSocket 控制器入口                    |
| `src/extensions/`  | Hocuspocus 数据库、Redis、日志和生命周期扩展 |
| `src/services/`    | 页面、用户、API 和 PDF 导出业务服务          |
| `src/schema/`      | Zod 输入/输出 schema                         |
| `src/lib/`         | 认证、错误、PDF 和无状态协作基础逻辑         |
| `src/types/`       | 服务内部类型和管理命令类型                   |
| `src/utils/`       | 广播等无状态工具                             |
| `tests/`           | Vitest 测试，结构应与 `src` 的能力对应       |

### `apps/mcp`

对外 AI 工具协议服务，默认监听 `3100`，由代理暴露为 `/mcp`。

| 子目录                   | 职责                                                |
| ------------------------ | --------------------------------------------------- |
| `src/server.ts`          | MCP Streamable HTTP 生命周期、健康检查和启用开关    |
| `src/tools.ts`           | 面向 AI 客户端的受限 Plane 工具目录和输入 schema    |
| `src/plane-api.ts`       | 只通过 `/api/v1` 访问 Plane 的有界、脱敏 API 适配器 |
| `src/request-context.ts` | Bearer API Token 和无状态 workspace 上下文解析      |
| `tests/`                 | MCP 协议、工具 schema、API 映射和隔离测试           |

### `apps/proxy`

Caddy 边缘代理。`Caddyfile.ce` 负责将 `/spaces`、`/god-mode`、`/live`、
`/mcp`、`/api`、`/auth`、静态资源和对象存储请求路由到对应服务；Dockerfile 用于构建社区版代理镜像。

## 共享包目录 `packages`

| 包                         | 职责                                                |
| -------------------------- | --------------------------------------------------- |
| `@plane/ui`                | 上游约定的共享 UI 组件和 Storybook                  |
| `@plane/propel`            | 新一代设计系统组件、图标、样式和 Storybook          |
| `@plane/editor`            | Tiptap/ProseMirror/Yjs 编辑器核心、CE/EE 扩展和样式 |
| `@plane/shared-state`      | 跨应用共享 MobX store 和过滤器状态                  |
| `@plane/services`          | 按领域组织的 API 服务客户端                         |
| `@plane/types`             | 跨模块领域类型和接口契约                            |
| `@plane/constants`         | 跨模块常量、端点和配置枚举值                        |
| `@plane/utils`             | 无状态通用工具、权限和过滤器逻辑                    |
| `@plane/hooks`             | 跨 React 应用复用的 hooks                           |
| `@plane/i18n`              | i18next 初始化、语言类型、脚本和 locale JSON        |
| `@plane/logger`            | Winston 结构化日志和请求日志                        |
| `@plane/decorators`        | Express HTTP/WebSocket controller decorators        |
| `@plane/tailwind-config`   | 颜色 token、Canvas/Surface/Layer 和动画规则         |
| `@plane/typescript-config` | 共享 TypeScript 编译配置                            |
| `@plane/codemods`          | jscodeshift 自动迁移脚本及测试                      |

## 部署目录 `deployments`

| 路径                                | 职责                                     |
| ----------------------------------- | ---------------------------------------- |
| `deployments/aio/community/`        | All-In-One 社区镜像、启动脚本和运行说明  |
| `deployments/cli/community/`        | Compose 安装、升级、备份、恢复及变量模板 |
| `deployments/kubernetes/community/` | 社区版 Kubernetes/Helm 使用入口          |
| `deployments/swarm/community/`      | Docker Swarm 安装与管理脚本              |

## OpenSpec 目录 `openspec`

| 路径                         | 职责                                                |
| ---------------------------- | --------------------------------------------------- |
| `openspec/config.yaml`       | 项目上下文和 proposal/specs/design/tasks 生成规则   |
| `openspec/specs/`            | 已生效的系统行为规格                                |
| `openspec/changes/<change>/` | 进行中变更的 proposal、design、delta specs 和 tasks |
| `openspec/changes/archive/`  | 已完成并归档的变更                                  |
| `openspec/AGENTS.md`         | AI 在 OpenSpec 目录工作的附加要求                   |

## 禁止的目录行为

- 不提交 `node_modules`、`.turbo`、`dist`、`build`、`.react-router`、coverage 或 Storybook 构建产物。
- 不在 `apps` 之间通过相对路径互相导入；共享能力下沉到合适的 `packages`。
- 不在 `packages` 中反向依赖具体应用。
- 不用新建 `common`、`misc` 或 `helpers` 作为不明确职责代码的默认归宿。
- 不手工修改自动生成文件；需要修改生成源和生成命令。
