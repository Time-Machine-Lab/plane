# AI 测试与 OpenSpec 验收规范

## 目标

测试只回答一个问题：部署到测试环境的当前代码，是否满足 OpenSpec 中本次变更的可观察场景。
项目不使用测试等级，不把 Windows 本地 Docker、全库检查、完整构建或重复检查作为日常验收前置条件。

## 唯一流程

```text
开发完成 -> 一次部署 -> 独立 Tester 验收 -> 通过或返工
```

1. 开发 Agent 完成实现，并按实际需要添加直接相关的自动化测试。
2. 开发 Agent 运行 `scripts/test/deploy-test.ps1`。脚本的预检、打包、服务选择、迁移和健康检查视为一次完整部署动作，不在其他阶段重复执行。
3. 部署成功后，独立 Tester 读取当前 OpenSpec 的 proposal、specs、design（存在时）和 tasks。
4. Tester 使用测试环境的默认账号和持久数据，只验证必需场景、基础可达性及与失败场景直接相关的回归。
5. Tester 不修改产品代码。失败交回开发 Agent；修复并重新部署后，由原 Tester 复测失败场景和必要回归。

纯文档或确认不影响运行时的维护变更可以不部署，直接验证文档或静态结果。

## 开发 Agent 职责

- 保持实现与 OpenSpec 场景一致。
- 复用受影响模块已有测试模式，只增加能防止实际回归的测试。
- 不为交接重复运行全库 format、lint、types、build 或完整测试套件。
- 部署失败时先处理部署问题，不能把未部署的代码交给 Tester 宣称验收。
- 交接时只提供 change 路径、部署 ID、测试地址和已知环境限制，不预设“实现正确”的结论。

## Tester 职责

- 独立读取 OpenSpec 场景和本 Runbook，不重跑开发阶段的静态检查。
- 确认 Plane 和相关 API 可访问，然后使用默认测试账号登录。
- 按用户可见结果验证当前变更；涉及权限时切换对应角色，涉及数据时检查实际数据结果。
- 不修改产品代码、部署脚本或测试环境配置。
- 不清空或重建共享测试环境；测试产生的数据使用统一测试前缀，并只清理自己创建且确定可删除的数据。
- 报告结果时只使用 `pass` 或 `fail`。环境不可用或必需场景无法执行时属于 `fail`，同时说明阻塞原因。

## 验收范围

Tester 默认只检查：

- 部署脚本报告成功，测试地址可以访问且关键入口不返回 5xx。
- 默认测试账号能够登录并进入固定测试工作区。
- OpenSpec 中本次变更的每个必需场景都有实际页面、API、权限、数据或实时行为证据。
- 本次场景没有明显破坏紧邻的已有行为。

健康检查只证明环境可达，不能代替功能验收。代码审查、类型推断和“看起来正确”也不能作为通过证据。

## 验收记录

Tester 将精简结果写入 `openspec/changes/<change>/verification.md`：

```markdown
# Verification

- Tester: <agent identifier>
- Deployment: <sanitized deployment ID>
- Verdict: pass/fail

| Scenario                      | Result    | Evidence                         |
| ----------------------------- | --------- | -------------------------------- |
| <OpenSpec scenario reference> | pass/fail | <sanitized page/API/data result> |

## Failures

- <reproduction and observed result, or None>

## Residual risks

- <remaining risk, or None>
```

证据不得包含服务器地址、SSH 信息、账号、密码、Cookie、Token、认证 Header、连接串或私有配置内容。
任一必需场景失败时，不得完成或归档 change。
