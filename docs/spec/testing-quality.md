# AI 测试与 OpenSpec 验收规范

## 目标

测试流程只回答两个问题：代码层面的高风险行为是否有可重复的自动化证据，以及部署后的核心用户旅程是否满足
OpenSpec。项目不使用测试等级，不把全库检查、完整构建、本地 Docker 或重复命令作为日常验收前置条件。

## 证据归属

同一种证据只由一个阶段负责：

| 关注点                        | 唯一负责人          | 证据                  |
| ----------------------------- | ------------------- | --------------------- |
| 暂存文件的格式和 lint         | pre-commit          | hook 结果             |
| 受影响模块的 lint、类型和构建 | CI                  | workflow 结果         |
| 逻辑、校验、序列化和安全机制  | 自动化测试（CI）    | focused test 结果     |
| migration、启动和健康状态     | `deploy-test.ps1`   | 脱敏部署结果          |
| 用户可见工作流                | 独立 Tester         | `verification.md`     |
| 第三方真实连通性              | Tester 的一次 smoke | 可观察的发送/接收结果 |

开发 Agent 可以在实现过程中运行 focused 命令来定位问题，但这些诊断不需要由 Tester 重跑。例行验收也不通过
正常成功日志、代码审查或类型推断重复证明用户行为。

## 默认流程

```text
OpenSpec 场景和风险边界
  -> 开发与 focused 自动化测试
  -> CI 执行受影响检查和已有测试
  -> 一次部署受影响服务
  -> Tester 前置条件检查
  -> 3-7 条最小用户旅程
  -> 通过、失败返工或环境阻塞
```

1. OpenSpec 描述可观察行为和重要风险边界，不写 L1-L4、逐任务命令矩阵或完整手工排列组合。
2. 开发 Agent 复用受影响模块已有的测试模式，添加能防止实际回归的自动化测试。
3. CI 运行受影响静态检查和仓库已有自动化测试；普通变更不要求全库 `pnpm check`、`pnpm build` 或完整 Docker 套件。
4. 运行时变更通过 `scripts/test/deploy-test.ps1` 部署一次。纯文档、CI 配置或确认不影响运行时的维护变更不部署。
5. Tester 先确认凭据、账号、观察渠道和环境可用，再把必需场景组合成 3-7 条最小用户旅程执行。
6. 失败由开发 Agent 修复并重新部署；原 Tester 只复测失败旅程和一条必要的相邻回归。

## 自动化测试边界

优先自动化以下内容：

- 权限、Secret 脱敏、工作区/数据隔离和 migration 等高风险边界。
- 纯逻辑、输入校验、序列化、事件选择、状态转换和错误映射。
- 可通过 mock 稳定验证的超时、DNS、网络错误和第三方错误响应。
- 对核心工作流有明确回归价值，且受影响模块已经具备测试基础设施的行为。

下列内容默认不增加自动化负担：

- 为一个页面单独引入新的前端测试框架或运行环境。
- 对等价校验错误做完整排列组合。
- 在本地、部署脚本、Tester 和发布门禁中重复同一组检查。
- 例行手工注入第三方超时、DNS 或网络故障；这些由 mocked contract test 负责。
- 与本次变更无关的全库测试、全量构建或 coverage 指标。

缺少自动化基础设施不等于产品验收失败。此时保留关键运行时旅程，并把是否建设共享测试能力作为独立工程决策，
而不是附加到单个需求。

## Tester 职责

- 独立读取 OpenSpec 的必需场景，不修改产品代码、部署脚本或测试环境配置。
- 前置确认 Plane/API、所需账号、第三方凭据和观察渠道可用；不输出任何凭据。
- 一个用户旅程可以覆盖多个相邻场景，避免按字段、按钮或错误类型逐项重复操作。
- 只验证用户可见结果、关键权限/数据边界和一条紧邻回归，不重跑 lint、类型、构建或自动化测试。
- 第三方集成只做一次真实连通性 smoke；异常排列由自动化 contract test 覆盖。
- 正常结果正确时不分析 Worker/容器日志；只有可观察结果错误且日志有助于定位时才收集脱敏日志。
- 只清理自己创建且可明确识别的测试数据，不清空或重建共享环境。

## 结果语义

- `pass`：部署后的行为与需求一致。
- `fail`：环境和前置条件可用，但产品行为与需求不一致。
- `blocked`：缺少凭据、账号、观察渠道、服务可达性或其他环境前置条件，无法判断产品行为。

`blocked` 不是产品缺陷，也不能当作通过。任一必需旅程为 `fail` 或 `blocked` 时，不得完成或归档 change。

## 验收记录

Tester 将精简结果写入 `openspec/changes/<change>/verification.md`：

```markdown
# Verification

- Tester: <agent identifier>
- Deployment: <sanitized deployment ID or N/A>
- Verdict: pass/fail/blocked

| Journey                | Covered scenarios     | Result            | Evidence                      |
| ---------------------- | --------------------- | ----------------- | ----------------------------- |
| <minimal user journey> | <scenario references> | pass/fail/blocked | <sanitized observable result> |

## Failures

- <reproduction and observed product result, or None>

## Blockers

- <missing prerequisite, owner, and next action, or None>

## Residual risks

- <accepted remaining risk, or None>
```

证据不得包含服务器地址、SSH 信息、账号、密码、Cookie、Token、认证 Header、连接串或私有配置内容。
