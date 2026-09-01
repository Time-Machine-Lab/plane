# 共享包开发规范

## 适用范围

适用于 `packages/*`。共享包是应用之间的稳定契约，变更影响通常高于单一应用修改。

## 依赖方向

建议保持以下单向关系：

```text
types / constants / utils
          ↓
services / shared-state / hooks
          ↓
ui / propel / editor
          ↓
apps
```

- `packages` 不得导入 `apps`。
- 基础包应避免依赖高层 UI 或状态包。
- 跨包依赖使用 `workspace:*`，外部依赖使用 `catalog:`。
- 通过包的 `src/index.ts` 或明确子路径导出公共 API，不依赖其他包内部文件结构。
- 新依赖或导出可能影响多个消费者；先确认实际消费者，契约变化时按需运行最小的消费方类型或构建检查。

## 包职责

- `types`：纯类型契约，不放运行时状态和 API 调用。
- `constants`：稳定常量和端点；依赖环境的值由应用配置，不在此硬编码。
- `utils`：无状态、可测试的纯工具；领域副作用不应伪装成 helper。
- `services`：HTTP/API 客户端和传输映射，不持有 React UI 状态。
- `shared-state`：跨应用 MobX store、actions 和派生状态。
- `hooks`：跨应用 React hooks，避免与单一页面结构耦合。
- `ui`、`propel`：共享视觉组件、token 和 Storybook。
- `editor`：编辑器 schema、extensions、序列化和样式。
- `i18n`：语言声明、namespace、locale 资源和同步脚本。
- `logger`、`decorators`：Node 服务基础设施。
- `tailwind-config`、`typescript-config`：共享构建和设计配置。
- `codemods`：可重复的机械迁移工具，每个 transform 必须有 fixture/test。

## 公共 API 与兼容性

- 修改前搜索全部消费者，区分 internal symbol 和 public export。
- 重命名或删除公共 export 时先提供 deprecated alias，并在独立变更中清理消费者。
- 类型收紧必须确认现有合法调用仍可编译；不要用大范围类型断言解决升级错误。
- 公共组件 props 保持可组合且有合理默认值，避免暴露应用专用 store 或路由对象。
- 新工具只有形成稳定复用时才进入共享包，单一调用点先留在应用内。

## UI 与 Storybook

- `@plane/ui` 新共享组件应有 story，覆盖默认、边界、禁用、loading 和交互状态。
- `@plane/propel` 使用自己的设计 token 和 Storybook，不跨包复制 token。
- 修改 Tailwind 颜色层级时阅读 `packages/tailwind-config/AGENTS.md`。
- 组件满足键盘、焦点、aria、主题和响应式要求；不把业务文案硬编码到通用组件。

## 状态与服务

- MobX store 明确 observable、action、computed 和清理生命周期。
- service 返回稳定 typed data 或明确 error，不直接触发 toast、路由或 UI 副作用。
- store 不直接拼接 endpoint；通过 service 访问后端。
- 缓存 key、实体 ID 和更新顺序属于共享契约，修改时覆盖并发和失效场景。

## i18n

- 修改 `packages/i18n/src/locales/**/*.json` 前遵守仓库 translate 工作流。
- 新 key 添加到正确 namespace，并保持所有 locale key、变量和 ICU 结构同步。
- 运行 `pnpm --filter=@plane/i18n check:sync` 和类型生成检查。

## 快速自检与验收

- 开发 Agent 可以检查修改的包和直接受影响消费者来定位问题；CI 不默认构建所有消费者。
- 公共类型或 export 变化时，CI 运行受影响消费方类型/构建检查；已有 Vitest 和 codemod fixture 通过 affected test 运行。
- UI/Propel 的 Storybook 和 i18n 同步检查只在对应能力被直接修改时运行。
- 影响运行时消费者的改动完成后立即部署对应消费者；独立 Tester 子 Agent 在测试环境验证受影响包及必要消费者，不重复本地开发检查。

## 完成清单

- 包职责、公共 export 和依赖方向清晰。
- 已检查所有消费者且没有 deep import。
- 公共行为在具有明确回归价值时具有测试或 Storybook 场景，低风险改动不强制新增。
- 相关消费场景已由未参与实现的 Tester 子 Agent 独立验收；无需运行环境的改动不要求部署。
