# 实时协作开发规范

## 适用范围

适用于 `apps/live`，包括 Express/WebSocket、Hocuspocus、Yjs、Redis 协调、页面持久化和 PDF 导出。

## 服务边界

- `apps/live` 只处理实时协作和紧密相关的导出能力；权威业务数据与权限仍由 `apps/api` 管理。
- controller 处理协议边界，extension 接入 Hocuspocus 生命周期，service 处理业务编排。
- `schema` 使用 Zod 验证环境变量、HTTP body、管理命令和跨服务响应。
- 跨服务契约优先复用 `@plane/types`，错误、日志和工具优先复用现有共享包。

## 连接、认证与权限

- WebSocket 建连前完成身份校验，文档加入、读取、更新和导出均验证 workspace/project/page 权限。
- 不信任 client 提供的 user、workspace、project 或 document 标识，必须通过 API 或可信 token 校验。
- 认证失败、权限撤销、文档删除时主动关闭相关连接，返回稳定且不泄密的错误。
- CORS、origin、代理 header 和真实客户端 IP 处理与 `apps/proxy`、部署配置保持一致。

## 协作一致性

- Yjs update 按二进制数据处理，不在未理解协议语义时转换或拼接 payload。
- 广播和 Redis pub/sub 必须避免把消息回送给来源连接造成循环。
- reconnect、重复投递和多实例并发是正常情况；处理逻辑必须幂等。
- 持久化顺序、debounce 和 flush 策略的变化必须说明崩溃时可能丢失的数据窗口。
- 文档 key 格式属于跨版本契约，修改时需要迁移和向后兼容方案。

## 生命周期与可靠性

- 初始化顺序保持配置验证、依赖连接、extension/controller 注册、监听端口的明确阶段。
- SIGTERM/SIGINT 必须停止接收新连接、flush 待保存状态并关闭 Redis/数据库/HTTP 资源。
- 未处理 rejection/exception 必须结构化记录；不得让进程在未知状态继续服务。
- 所有 API、Redis、对象存储和 PDF 操作设置超时、资源上限和可诊断错误。
- 大文档、恶意 payload 和并发导出必须有大小、内存和并发保护。

## 日志与安全

- 使用 `@plane/logger`，日志包含 correlation/document ID，但不记录 token 或完整文档正文。
- 广播错误只向客户端暴露必要信息，内部堆栈进入受控日志。
- PDF/富文本渲染必须对 URL、图片、HTML 和文件类型执行现有安全校验。
- 新 controller 使用 `@plane/decorators` 的现有模式，不绕开统一 middleware。

## 测试与验证

- 单元测试放入 `apps/live/tests`，目录与 `src` 能力对应。
- 覆盖认证拒绝、重复 update、Redis 重连、持久化失败、graceful shutdown 和资源限制。
- 涉及协同算法或协议时增加至少两个 client 的集成场景。

```bash
pnpm --filter=live check:format
pnpm --filter=live check:lint
pnpm --filter=live check:types
pnpm --filter=live test
pnpm --filter=live test:coverage
pnpm --filter=live build
```

## 完成清单

- 权限在连接与敏感操作边界均被验证。
- 多实例、重连、重复消息和异常关闭行为可预测。
- 资源已清理，日志无敏感信息，错误可以关联诊断。
- Vitest、类型、Lint 和构建通过。
