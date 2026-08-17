# 前端开发规范

## 适用范围

适用于 `apps/web`、`apps/admin`、`apps/space`，以及修改 `packages/ui`、
`packages/propel`、`packages/editor` 等可视能力时的前端部分。

## 应用边界

| 应用    | 端口 | 责任边界                                 |
| ------- | ---- | ---------------------------------------- |
| `web`   | 3000 | 团队工作台和主要业务流程                 |
| `admin` | 3001 | 实例级管理和配置，不承载普通用户业务页面 |
| `space` | 3002 | 对外公开内容，默认按不可信访问者处理     |

代码只属于一个应用时留在应用目录；跨两个以上应用稳定复用时，按职责下沉到共享包。

## 路由与页面

- 使用 React Router 7 的 route config；路由入口为各应用的 `app/routes.ts`。
- `web` 保持 `coreRoutes`、`extendedRoutes` 和现有 merge 机制，不绕过扩展点修改路由优先级。
- 页面文件负责路由参数、数据装配和布局组合，复杂业务组件放入相邻领域组件目录。
- catch-all 404 路由必须保持在最后。
- 路由参数、搜索参数和外部跳转目标必须验证；不要直接信任 URL 输入。
- 新旧 URL 兼容时使用明确的 redirect route，并为兼容期限留下说明。

## 组件与设计系统

- 优先复用目标区域已经使用的 `@plane/ui` 或 `@plane/propel`，不要在业务应用复制共享组件。
- 新增通用 `@plane/ui` 组件时增加 Storybook story；Propel 区域沿用其 Storybook 和 token。
- 不在单个功能 PR 中顺便把整块 UI 从一个设计系统迁移到另一个设计系统。
- 图标优先使用项目已依赖的 Lucide 或设计系统图标。
- 交互控件必须支持键盘操作、可见焦点、合理 aria 属性和可读 label。
- 响应式布局必须验证小屏和桌面；动态文本不得遮挡、溢出或引发布局跳动。

### Canvas、Surface、Layer

修改视觉层级时必须同时遵守 `packages/tailwind-config/AGENTS.md`：

- `bg-canvas` 只允许出现在应用根容器一次。
- 页面顶层区域使用 surface；同一视觉平面的 surface 不互相嵌套。
- surface 内需要抬升的元素使用与该 surface 对应的 layer。
- modal、popover 等独立 stacking plane 可以使用自己的 surface/layer。
- 使用语义 token，不在组件内散落只适合单一主题的硬编码颜色。

## 状态、服务和数据流

- 跨应用共享 MobX 状态放在 `@plane/shared-state`；应用专用 store 留在应用内。
- API 调用优先通过 `@plane/services` 或目标应用既有 service，不在展示组件中直接拼 URL。
- `@plane/services` 负责传输和响应映射，store 负责状态与业务动作，组件负责展示和交互。
- 远程数据缓存沿用相邻代码的 SWR/MobX 组合，避免同一资源出现多套缓存真相。
- optimistic update 必须定义失败回滚，防止 UI 与服务端长期不一致。
- effect 和订阅必须清理；避免 render 中产生副作用或创建不稳定对象。

## TypeScript 与 React

- Props、loader/action 数据、服务响应和 store API 必须有明确类型。
- 优先组合和小组件，避免承担获取数据、权限、表单和复杂展示的超大组件。
- 派生值优先计算而不是复制进 state；不要用 effect 同步可直接推导的状态。
- hooks 只在顶层调用，自定义 hook 命名以 `use` 开头，并保持单一职责。
- 列表 key 必须稳定，不使用数组索引标识会重排的业务实体。
- 用户可见错误要可操作；技术细节写入 logger/监控，不直接暴露堆栈。

## 国际化

- 用户可见文案必须使用 `@plane/i18n`，不得在业务组件新增硬编码英文或中文。
- 新 key 按现有 namespace 放置并运行同步检查。
- 保持所有 locale 的 key 结构一致；占位符、HTML tag 和 ICU plural 变量必须一致。
- 日期、时间、数字和复数使用 locale-aware API，不手工拼接格式。

## 前端安全

- 富文本和外部 HTML 必须走现有 sanitize 流程。
- 外部 URL、附件、重定向和 `target=_blank` 链接执行协议白名单及安全属性检查。
- 不在 localStorage 持久化敏感凭据；认证与权限行为沿用现有 provider/service。
- 公开 `space` 页面不得因为客户端传参访问未发布或无权限的数据。

## 快速自检与验收

开发 Agent 只运行与改动直接相关的快速检查，例如目标应用的类型检查或已有组件测试。修改构建配置、
依赖、路由装配或准备发布时，再按需运行目标应用 build；Storybook 只在共享组件隔离行为需要验证时运行。
不要把 format、lint、types、build 和 Storybook 固定组合成每次变更的完整命令矩阵。

日常最终证据来自部署后的 OpenSpec 场景验收。Tester 在测试环境验证真实路由、权限、异步状态、关键交互和
受影响视口，不重复开发 Agent 的静态检查。

## 前端完成清单

- 路由、权限、loading、empty、error 和 disabled 状态完整。
- 文案已国际化，键盘和屏幕阅读器行为合理。
- 共享能力放置正确，没有应用间相对导入。
- 没有新增 lint warning、运行时 console error 或 hydration 问题。
- 部署后的 OpenSpec 场景和关键视口已由独立 Tester 验收。
