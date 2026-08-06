# 测试环境 Runbook

## 目的与边界

本 Runbook 规定 AI 在 Windows 开发机上启动 Plane 前端、将当前工作区直接部署到隔离测试服务器，
以及在 OpenSpec change 完成后执行独立验收的标准流程。测试环境用于开发验收，不是生产环境，
不得保存生产数据、生产密钥或承担正式流量。

日常测试不经过 GitHub Actions，也不要求 Windows 安装 Docker 或 WSL2：

- 前端页面在 Windows 本地启动，默认通过指定端口访问，并连接测试环境 API。
- API、Worker、Live、数据库及跨模块场景部署到测试服务器验证。
- 正式发布仍使用项目正式发布流程；本 Runbook 不能替代生产发布门禁。

## 文件与职责

| 文件                                        | 执行位置         | 用途                                         |
| ------------------------------------------- | ---------------- | -------------------------------------------- |
| `scripts/test/start-local.ps1`              | Windows 开发机   | 校验依赖、加载私有配置并启动本地前端         |
| `scripts/test/deploy-test.ps1`              | Windows 开发机   | 打包当前工作区、上传并触发测试环境部署       |
| `scripts/test/remote-deploy.sh`             | Linux 测试服务器 | 校验部署包、更新指定服务、健康检查和失败回滚 |
| `scripts/test/test-environment.example.env` | 公开仓库         | 私有配置模板，只包含占位值                   |
| `.secrets/plane-test.env`                   | Windows 开发机   | 真实测试配置，必须被 Git 忽略                |

用户入口只有前两个 PowerShell 脚本。`remote-deploy.sh` 由 `deploy-test.ps1` 上传和调用，
不要求用户手工登录服务器执行。

## 敏感配置

真实服务器地址、账号、密码、测试账号凭据和其他 Secret 只能写入
`.secrets/plane-test.env`。整个 `.secrets/` 目录必须在根 `.gitignore` 中明确忽略，并由脚本在执行前检查
其未被 Git 跟踪。公开仓库只提交 `test-environment.example.env`。

必须遵守以下规则：

- 不在聊天、OpenSpec 产物、Markdown、源代码、部署 manifest、截图或测试报告中记录真实 Secret。
- 不把私有配置复制到临时部署包；部署包只能包含应用源码、远程脚本和非敏感 manifest。
- 脚本和测试命令不得输出密码、完整连接串、认证 Header、Cookie 或 Token。
- 不使用 `git add -f` 添加私有配置；发现文件被跟踪时立即停止部署并报告。
- 测试服务器只允许部署和操作 Plane 测试实例，不得探测、修改或删除服务器上的其他项目和数据。
- 当前密码自动化模式具有较高风险；密码一旦出现在对话、日志或版本控制中必须立即轮换。
- 后续有条件时应迁移为专用低权限部署用户和 SSH key；迁移不改变本 Runbook 的用户入口。

## 首次准备

### 1. 开发机依赖

Windows 开发机需要：

- 仓库要求版本的 Node.js 和 pnpm。
- Python 3.12 或更高版本；部署脚本使用隔离的本地虚拟环境处理 SSH 传输依赖。
- Windows PowerShell 5.1 或 PowerShell 7。
- 脚本实际使用的 SSH/SCP 客户端。
- 可访问测试服务器指定 SSH 端口和 Plane 测试端口的网络。

从模板生成私有配置后填写真实值：

```powershell
New-Item -ItemType Directory -Force .\.secrets | Out-Null
Copy-Item .\scripts\test\test-environment.example.env .\.secrets\plane-test.env
```

不要把私有配置的内容粘贴到 AI 对话中。AI 只应运行脚本并依据脱敏输出判断结果。

私有配置支持以下变量；真实值以本地文件为准，不能复制到跟踪文件：

| 变量                             | 用途                                               |
| -------------------------------- | -------------------------------------------------- |
| `PLANE_TEST_HOST`                | 测试服务器主机                                     |
| `PLANE_TEST_SSH_PORT`            | SSH 端口，默认 `22`                                |
| `PLANE_TEST_SSH_USER`            | SSH 用户                                           |
| `PLANE_TEST_SSH_PASSWORD`        | SSH 密码，只能存在于私有配置                       |
| `PLANE_TEST_SSH_HOST_KEY_SHA256` | 已登记的服务器主机密钥指纹                         |
| `PLANE_TEST_REMOTE_ROOT`         | Plane 测试目录，默认 `/opt/plane-test`             |
| `PLANE_TEST_COMPOSE_PROJECT`     | 独立 Compose project name，默认 `plane-test`       |
| `PLANE_TEST_HTTP_PORT`           | 指定 HTTP 访问端口，默认 `18080`                   |
| `PLANE_TEST_HTTPS_PORT`          | 指定 HTTPS 访问端口，默认 `18443`                  |
| `PLANE_TEST_BASE_URL`            | 测试实例访问地址                                   |
| `PLANE_TEST_KEEP_RELEASES`       | 保留 release 数量，默认 `3`                        |
| `PLANE_TEST_BOOTSTRAP_RELEASE`   | 首次初始化使用的官方 Plane 镜像标签，默认 `stable` |
| `PLANE_TEST_LOCAL_ORIGINS`       | 允许访问测试 API 的本地前端 Origins                |
| `PLANE_TEST_TRUST_ON_FIRST_USE`  | 首次连接是否登记主机密钥；首次成功后应设为 `0`     |

`PLANE_TEST_PUBLIC_PORT` 仅作为旧配置的兼容别名；新配置统一使用 `PLANE_TEST_HTTP_PORT`。

### 2. 测试服务器边界

测试服务器必须已安装 Docker Engine 和 Docker Compose，并有足够空间运行 Plane。第一次部署只能在
脚本约定的 Plane 测试根目录内初始化。远程脚本必须：

- 将所有写操作限制在配置指定的 Plane 测试根目录。
- 不清空服务器、不删除未知目录、不停止非 Plane 容器。
- 使用唯一 Compose project name，避免影响其他 Compose 项目。
- 在执行任何清理、覆盖或回滚前校验目标绝对路径。
- 通过指定端口暴露测试实例；不假定使用 80/443。

### 3. 首次实例初始化

第一次部署完成后，Plane 仍可能显示 `Welcome to Plane / Get started` 或
`Setup your Plane Instance`。这表示容器和 API 已可用，但实例尚未完成业务初始化。首次初始化属于一次性人工操作：

1. 环境所有者通过指定端口或 `http://localhost:8000` SSH 隧道打开 Plane。
2. 环境所有者自行设置实例信息和首个管理员账号，并妥善保管账号凭据。
3. AI 不得代替环境所有者选择管理员邮箱、密码或组织信息，也不得把这些值写入脚本、文档、测试报告或 OpenSpec 产物。
4. 初始化后，Tester 重新检查 Web、Admin 和 `/api/instances/`，确认初始化页面不再出现，再执行需要登录的 L2/L3 场景。

实例未初始化时，可以把容器、代理、API、SSH 隧道和页面可达性分别记录为 `pass`，但所有依赖登录、权限、
工作区或业务数据的验收都必须记录为 `unverified`，不能把“首页可打开”当作提案验收通过。浏览器控制台错误和
hydration mismatch 需要单独记录；不得用“实例未初始化”掩盖可独立复现的前端错误。

### 4. 端口与跨域

远程 Plane 默认通过测试服务器的 `18080` 端口访问。本地前端由 `start-local.ps1` 建立 SSH 隧道，
将 `http://localhost:8000` 转发到服务器回环地址的 Plane HTTP 端口，而不把 API/容器端口额外暴露到
公网。测试 API 的 CORS、
CSRF trusted origins、Cookie secure/same-site 设置必须允许配置的本地前端 Origin；IP 与 localhost 混用时
不要配置固定 Cookie domain。

仅开放实际需要的端口：远程数据库、Valkey、RabbitMQ 和对象存储管理端口不得直接暴露到公网。

## 日常操作

以下示例以脚本帮助信息为参数事实来源；脚本调整参数时必须在同一变更中更新本文件。

### 启动 Windows 本地前端

启动默认 Web 应用：

```powershell
.\scripts\test\start-local.ps1
```

按需指定应用或端口时，先运行帮助查看可用参数：

```powershell
Get-Help .\scripts\test\start-local.ps1 -Detailed
```

主要参数为 `-Apps web,admin,space`、`-ConfigPath`、`-SkipChecks`、`-SkipInstall`、`-NoBrowser`、
`-Wait`、`-TimeoutSeconds` 和 `-WhatIf`。常用示例：

```powershell
.\scripts\test\start-local.ps1 -Apps web
```

脚本必须完成以下步骤：

1. 检查 Node.js、pnpm、私有配置和目标端口。
2. 从私有配置读取服务器连接信息，不打印 Secret。
3. 建立本地 `localhost:8000` 到远程 Plane 端口的 SSH 隧道并验证可达。
4. 让本地前端使用隧道地址，启动所选应用并等待 HTTP 可访问。
5. 输出本地访问 URL、进程 ID、隧道状态和日志位置。
6. 启动或隧道失败时返回非零退出码，并保留足够的脱敏诊断信息。

页面验收应覆盖真实路由、正常/loading/empty/error 状态、权限和本次变更的关键交互。仅看到首页成功
打开不构成功能验收。

### 部署当前工作区到测试环境

执行脚本帮助确认可用服务名和参数：

```powershell
Get-Help .\scripts\test\deploy-test.ps1 -Detailed
```

主要参数为 `-Services`、`-ConfigPath`、`-SkipChecks`、`-KeepPackage`、`-TimeoutSeconds` 和
`-WhatIf`。`-Services` 支持 `auto`、`all`、`web`、`admin`、`space`、`api`、`worker`、
`beat-worker`、`live` 和 `proxy`。

部署当前工作区的典型入口：

```powershell
.\scripts\test\deploy-test.ps1
.\scripts\test\deploy-test.ps1 -Services api
```

脚本应支持只部署受影响服务，具体参数以帮助输出为准。部署流程必须：

1. 校验私有配置已被忽略且未被 Git 跟踪。
2. 记录当前 commit、dirty 状态、时间和受影响服务，不记录 Secret。
3. 排除 `.git`、`.env*`、`node_modules`、缓存、构建产物和本地私有配置后创建临时部署包。
4. 通过 SSH/SCP 将部署包传到测试服务器的 Plane 测试目录。
5. 获取部署锁，避免多个 Agent 并发覆盖同一测试实例。
6. 测试实例尚未初始化时，仅使用 `PLANE_TEST_BOOTSTRAP_RELEASE` 指定的官方镜像建立基线，不在小型服务器上全量构建源码。
7. 基线存在后只构建明确指定的受影响服务；禁止 `-Services all` 全量源码构建。前端改动优先通过 Windows 本地前端连接测试 API 完成 L2。
8. 检测 migration，按脚本策略执行数据库保护和迁移；API、Worker、Beat 和 Migrator 必须使用同一后端镜像。
9. 等待容器、HTTP/API 和关键路由健康检查。
10. 成功时输出脱敏部署 ID、工作区版本、服务列表和测试 URL。
11. 失败时返回非零退出码并恢复上一个可用应用版本；数据库回滚限制必须明确报告。

部署成功后，Tester 必须使用脚本输出的指定端口 URL（默认远程端口 `18080`），不能猜测地址或把私有
配置内容复制到报告。若云安全组未开放该端口且本任务不允许修改服务器网络策略，Tester 使用
`localhost:8000` SSH 隧道完成验收，并将公网直连记录为受环境限制，而不是擅自修改防火墙。本地前端的
API 与 Live 连接都使用该隧道。

## 何时使用哪一级测试

| 等级            | 触发时机                                       | 最低内容                                                   | 环境                           |
| --------------- | ---------------------------------------------- | ---------------------------------------------------------- | ------------------------------ |
| L1 快速检查     | 每轮实现完成后                                 | format、lint、types/Ruff、直接相关单测、目标 build         | Windows 本地，不启动完整 Plane |
| L2 模块运行验收 | 前端、共享 UI/状态或单模块用户行为             | 启动本地前端，连接稳定测试 API，验证真实页面               | Windows 本地前端 + 远程依赖    |
| L3 提案集成验收 | 后端、权限、migration、任务、Live 或跨模块变更 | 直接部署受影响服务，执行 API/页面/实时场景和数据副作用验证 | 隔离测试服务器                 |
| L4 发布级回归   | 高风险变更、合并前或正式发布前                 | 全库检查、完整测试集、迁移演练、关键业务回归               | 测试服务器和正式发布流程       |

默认采用能覆盖风险的最低等级，不因小改动重复部署完整 Plane：

- 纯文档、纯类型或纯工具函数通常执行 L1。
- 仅前端页面/组件修改通常执行 L1 + L2，不部署后端。
- 普通 API/Worker 修改执行 L1 + L3，只更新相关服务。
- 权限、数据库 migration、实时协议、公共 API/类型、安全和跨模块修改执行 L1 + L3；合并前升级到 L4。
- Dockerfile、Compose、依赖锁或基础镜像变化必须实际重建受影响镜像，不能使用源码热更新结果代替。

若环境缺失导致必需等级无法执行，结果是 `unverified`，不是 `pass`。

## OpenSpec 独立测试交接

实现 Agent 负责实现代码、增加自动化测试并完成 L1。所有实现任务结束后，必须创建一个全新的 Tester
子 Agent 接管最终测试。Tester 与实现 Agent 共享工作区和本机权限，因此这是职责与判断独立，不是进程、
凭据或安全隔离。

主 Agent 给 Tester 的初始上下文应保持最小，只提供：

- OpenSpec change 名称和 `openspec/changes/<change>/` 路径。
- 本文件、`testing-quality.md` 和适用模块规范路径。
- 被测工作区已准备完成的说明；不得给 Tester 预设“实现正确”的结论。

Tester 必须自行：

1. 读取 change 的 proposal、design、specs 和 tasks，建立 Requirement/Scenario 映射。
2. 检查工作区状态，选择 L1-L4，并说明选择理由。
3. 使用本 Runbook 的脚本启动本地前端或直接部署测试服务器。
4. 独立执行命令、页面、API、权限、数据或实时场景测试。
5. 不修改产品代码；发现失败时保留证据并交回实现 Agent。
6. 将报告写入 `openspec/changes/<change>/verification.md`。

实现 Agent 修复失败后，不得让原 Tester 直接继续并宣布通过；主 Agent 必须创建另一个全新的 Tester 子
Agent，基于最新工作区重新验证失败场景和必要回归。

## `verification.md` 模板

```markdown
# Verification

- Tester: <agent identifier>
- Environment: <Windows/test environment; no secret values>
- Date/worktree: <date, commit and dirty state>
- Selected level: <L1/L2/L3/L4 and reason>
- Deployment: <deployment ID and affected services, or not applicable>

| Requirement/Scenario | Verification                  | Result               | Evidence                    |
| -------------------- | ----------------------------- | -------------------- | --------------------------- |
| <spec reference>     | <command/request/page action> | pass/fail/unverified | <sanitized output/artifact> |

## Commands

- `<exact command>`: pass/fail

## Failures

- <failure and reproduction, or None>

## Residual risks

- <remaining risk, or None>

## Verdict

<pass/fail/unverified>
```

OpenSpec `tasks.md` 的最终验收记录必须链接或引用本报告。任一必需场景为 `fail` 或 `unverified` 时，
change 不得标记完成或归档。

## 健康检查、失败与回滚

部署后至少验证：

- 本次更新的容器处于健康/运行状态。
- Plane 指定端口可访问，关键入口不返回 5xx。
- 容器内部 API 根路径 `http://api:8000/` 返回预期健康结果，并验证本次受影响端点。
- 外部 `${PLANE_TEST_BASE_URL}/` 可访问并返回 Plane Web 页面；不能把 Web HTML 响应误当作 API JSON 健康端点。
- 涉及 Worker/Live 时验证任务消费或 WebSocket 连接，而非只检查进程存在。
- 涉及 migration 时验证 schema/数据前后状态和应用兼容性。

应用版本健康检查失败时，远程脚本应恢复上一个应用版本。数据库 migration 通常不能仅靠切换应用文件
自动撤销；Tester 必须按 design 中的回滚限制报告，不得声称已完整回滚数据库。

任何自动回滚不得触碰 Plane 测试根目录外的文件、容器、网络、卷或数据库。

## 测试完成与清理

测试完成后：

- 保留测试服务器和共享依赖运行，供后续快速部署；不要每次销毁完整环境。
- 终止不再需要的本地前端进程，或明确向用户提供仍在运行的 URL 和进程信息。
- 删除开发机上的临时部署包；不得删除私有配置。
- 在 `verification.md` 和 `tasks.md` 记录部署 ID、命令、结果和剩余风险。
- 不在报告中附加完整环境转储、私有配置或未脱敏服务器日志。

## 常见问题

### 本地页面能打开但登录失败

检查本地 Origin 是否已加入测试 API 的 CORS/CSRF 配置，Cookie 的 secure、same-site 和 domain 是否允许
当前 HTTP/HTTPS 与主机组合，并检查浏览器请求是否实际发往测试 API。

### 部署后仍是旧代码

核对脱敏部署 ID、commit/dirty 状态和更新的服务列表；检查目标服务是否使用了新构建或新挂载源码，
以及反向代理是否指向正确 Compose project 和指定端口。

### 服务健康但功能失败

健康检查只证明基础可达。根据 OpenSpec 场景继续检查 API 响应、权限、Worker、数据库副作用、Live 连接和
浏览器控制台/网络请求。功能失败必须记录为 `fail`。

### 部署锁冲突

不要强删未知锁。确认没有其他部署仍在运行后，使用脚本提供的恢复机制；无法确认时停止并报告，避免两个
Agent 同时更新共享测试实例。
