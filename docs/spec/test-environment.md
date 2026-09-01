# 测试环境 Runbook

本 Runbook 用于所有产生运行时行为的产品变更。Windows 主机只负责发起部署和必要的浏览器访问，不需要安装
Django、pytest、Ruff、Docker、Docker Compose 或 WSL2。纯文档、静态配置等不产生运行时行为的改动不进入
本流程；其余改动实现完成后直接部署受影响服务，再由未参与实现的 Tester 子 Agent 验证本次需求目标。

## 首次初始化

### 本地文件

测试环境的所有本地文件都位于项目根目录，不写入用户目录或 C 盘的隐藏位置：

```text
.secrets/plane-test.env       服务器和测试账号私密配置
.runtime/test/                tools、ssh/known_hosts、logs 和临时 packages
scripts/test/test-environment.example.env  可提交的配置模板
```

`.secrets/` 和 `.runtime/` 必须被根 `.gitignore` 忽略，且不得被 Git 跟踪或打进部署包。首次使用时创建私密配置：

```powershell
New-Item -ItemType Directory -Force .\.secrets | Out-Null
Copy-Item .\scripts\test\test-environment.example.env .\.secrets\plane-test.env
```

Plane 容器使用的运行环境文件保留在测试服务器 `/opt/plane-test/shared/.env`，由部署脚本创建和维护；它不下载到
Windows，也不进入 Git。日常只维护项目内的 `.secrets/plane-test.env`。

在 `.secrets/plane-test.env` 中填写服务器连接信息。以下变量定义固定测试身份和数据；变量名以模板为准：

- `PLANE_TEST_ADMIN_EMAIL` / `PLANE_TEST_ADMIN_PASSWORD`
- `PLANE_TEST_MEMBER_EMAIL` / `PLANE_TEST_MEMBER_PASSWORD`
- `PLANE_TEST_GUEST_EMAIL` / `PLANE_TEST_GUEST_PASSWORD`
- `PLANE_TEST_WORKSPACE_SLUG`，未设置时使用 `ai-test`
- `PLANE_TEST_PROJECT_IDENTIFIER`，未设置时使用 `AITEST`

Admin 用于管理场景，Member 用于普通协作，Guest 用于低权限验证。首次真实部署前密码可以留空，脚本会生成
强密码并回写项目内的私密配置；以后继续复用这些值。AI 可以在测试时读取账号登录，但不得把值输出到聊天、
日志、截图、OpenSpec 或任何跟踪文件。

### 首次部署与持久数据

测试服务器必须是 Linux，并已安装 Docker Engine 和 Docker Compose。首次和以后都使用同一个命令：

```powershell
.\scripts\test\deploy-test.ps1
```

首次运行会建立 Plane 测试实例，并在服务健康后幂等创建固定账号、工作区、项目和 `[AI-TEST]` 基础数据。
后续运行只补齐缺失对象，不重复创建数据。数据库、对象存储和相关数据卷持续保留，不因日常部署重建或清空。

远端初始化和所有写操作只能发生在私密配置指定的 Plane 测试根目录及 Compose project 内。不得扫描、停止、
修改或删除服务器上的其他项目、容器、网络、卷和数据。禁止 `docker system prune` 和任何 volume prune。部署前
可在磁盘低于安全阈值时清理未使用的 BuildKit cache 和 dangling images；运行容器、被引用镜像和数据卷不受影响。

## 按需部署

运行时实现完成后立即运行：

```powershell
.\scripts\test\deploy-test.ps1
```

默认 `-Services auto`，并以 `origin/preview` 为默认比较基线。脚本同时识别 merge-base 至 `HEAD` 的已提交改动和
当前工作区的未提交改动，再选择需要部署的运行时服务。可以用 `-BaseRef` 指定其他基线。

脚本负责校验私密配置、执行最小预检、打包当前工作区、上传、迁移、更新服务、健康检查和幂等补种测试数据。
当共享包变更无法可靠推断运行时消费者时，`auto` 会停止并要求通过 `-Services` 明确列出实际消费者；不要因此
默认部署所有应用。锁文件、根依赖或部署拓扑变化仍可触发 `all`。AI 不需要判断测试等级，也不需要在部署前后
重复运行完整 build、全库检查或本地 Docker 测试。

部署前不要求在 Windows 主机执行 Django、pytest、Ruff、后端自动化测试或本地 Docker 测试。当前主机缺少这些
依赖不是错误或阻塞；除非用户明确要求，否则也不要为了本次交付安装它们。

部署的是当前工作区快照，包括未提交但未被忽略的改动；`.git`、`.secrets`、`.runtime`、依赖缓存和构建缓存
必须排除。成功输出只包含脱敏部署 ID、服务和测试地址。完整参数以脚本帮助为准：

```powershell
Get-Help .\scripts\test\deploy-test.ps1 -Detailed
```

`deploy-test.ps1` 成功后会自动建立或复用 `http://localhost:8000` SSH 隧道。`start-local.ps1` 只在需要本地调试
前端时使用，不属于默认验收步骤：

```powershell
.\scripts\test\start-local.ps1 -Apps web
```

隧道由脚本维护为单实例，不需要手工建立。测试端口默认不开放到公网，以避免暴露测试账号，并保持登录 Cookie、
跳转地址和 CORS 使用稳定的本地域名。只有配置了受控公网入口、HTTPS、防火墙来源限制及对应 Base URL 时，才改用
远端地址直接访问。

## 测试

部署成功后，由主 Agent 创建一个未参与实现的新 Tester 子 Agent 执行验收：

1. 读取当前 OpenSpec 的 proposal、specs、design（存在时）和 tasks。
2. 使用部署脚本输出的测试地址确认 Plane 和关键 API 可访问。
3. 从 `.secrets/plane-test.env` 读取适合场景的默认账号，并确认第三方凭据、观察渠道等前置条件；不得输出凭据。
4. 使用完成需求目标所需的最少场景，验证本次改动和确有必要的相邻回归，不设置固定数量。
5. 通过 UI、API 和可观察业务结果执行场景验收；除非用户明确要求，不运行 pytest、Ruff 或其他自动化测试套件。
6. 在交付说明中记录脱敏结果；只有 OpenSpec、用户或风险明确要求时才写入 `verification.md`。

公网端口不可达时，使用部署脚本提供的 `http://localhost:8000` SSH 隧道验收，不擅自修改云安全组或服务器
防火墙。本地前端默认由脚本接入同一测试 API；允许的 CORS、CSRF 和 Cookie 设置由测试环境配置维护。

固定账号、工作区、项目和基础数据不得删除。Tester 创建的临时对象使用 `[AI-TEST]` 前缀，只能清理自己
创建且能够明确识别的对象。无需为下一次测试恢复或重建整个环境。

## 失败处理

- 部署脚本失败：保留脱敏错误，开发 Agent 修复后重新运行同一部署命令；未成功部署的版本不能进入功能验收。
- 场景失败：Tester 记录复现步骤和实际结果，开发 Agent 修复；需要重新部署时只部署受影响服务，原 Tester 只复验失败范围和必要的相邻回归。
- 环境、账号、凭据或观察渠道不可用且导致需求核心目标无法验证：结果记为 `blocked`，记录缺失条件和下一步；
  与核心目标无关或未经授权的外部验证直接跳过，不构成 `blocked`，也不能记为产品 `fail`。
- 部署锁冲突：不要强删未知锁；确认其他部署结束后再重试。
- 应用健康检查失败：脚本可以恢复上一应用版本，但不得清空持久数据。数据库 migration 无法自动逆转时必须明确报告回滚限制。

任何日志和报告都不得包含真实主机、SSH 密码、测试账号密码、Cookie、Token、认证 Header 或连接串。当前允许
root 密码自动化，但密码只能由脚本从项目内私密配置读取，不能进入命令行参数、部署归档或日志。
