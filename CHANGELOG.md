# Changelog

## [1.0.5] - 2026-03-24

### Fixed
- **导入会话并发安全**: 修复多管理员同时执行导入操作时的竞争条件
  - 将单槽位全局变量改为按 user_id 隔离的字典存储 (`_import_sessions`)
  - 添加 `_import_session_lock` 异步锁保护会话状态变更
  - 彻底避免会话错乱和文件被拒绝的问题
- **头像缓存并发击穿**: 修复 `_get_cached_avatar` 缓存未命中时的重复请求问题
  - 引入请求合并机制 (`_avatar_pending_requests`)，相同用户 ID 的并发请求共享同一个网络请求
  - 采用"快速检查 + 请求合并"双层架构，既保证性能又防止缓存击穿
- **临时文件资源泄漏**: 统一使用 try-finally 确保临时文件清理
  - `export_data_cmd` 导出命令使用 `try-finally` 确保临时 JSON 文件删除
  - `on_file_message` 导入命令统一在 finally 块中清理会话状态和临时文件
- **插件卸载资源泄漏**: 修复热重载时 aiohttp session 未关闭的问题
  - `terminate()` 方法现在调用 `close_aiohttp_session()` 关闭全局会话
- **统计数据来源错误**: 修复 `tool_get_user_deer_data` 结果组装逻辑
  - `stats` 字段现在正确使用 `stats_result.get("current_month", {})` 而非 `calendar_result.get("stats")`
  - 确保日历和统计数据分别来自正确的数据源
- **数据库连接泄漏**: 修复 `get_connection()` 初始化异常时的连接泄漏
  - `_ensure_tables()` 抛出异常时，主动关闭已创建的连接再重新抛出
- **LLM 工具配置类型安全**: 修复配置读取时的 AttributeError 风险
  - `_is_ai_help_deer_allowed()` 等配置读取方法现在检查 `isinstance(ai_config, dict)`
  - 配置为字符串/列表等非字典类型时返回合理默认值
- **LLM 工具参数校验**: 修复 `retro_deer` 工具的非法参数处理
  - 添加 `year`/`month` 类型检查，非整数提前拦截
  - 添加 `month` 范围检查 (1-12)，非法月份返回明确错误
  - `calendar.monthrange()` 和 `dt.date()` 调用前校验参数，捕获 ValueError
- **重复打卡问题**: 修复 `deer_other` 工具未对 `target_ids` 去重的问题
  - 现在使用 `seen` 集合去重，避免重复 ID 累加同日打卡次数

### Changed
- **代码复用重构**: 提取 `plain_deer_merged_cmd` 与 `handle_deer_other` 的重复逻辑
  - 新增 `batch_deer_other()` 方法统一处理批量帮打卡逻辑
  - 新增 `DeerResult` TypedDict 类型规范打卡结果数据结构
  - `plain_deer_merged_cmd` 现在调用 `batch_deer_other()`，消除代码重复
- **模板系统严格化**: 替换松散的模板机制
  - 新增 `MessageTemplates` 类统一管理所有文本模板
  - 新增 `TemplateKeyError` 异常，模板键不存在或参数缺失时显式报错
  - 所有模板调用改为 `MessageTemplates.get(key, **kwargs)` 严格格式化
- **补打卡日期硬编码解耦**: 修复 `handle_deer_past` 的日期硬编码问题
  - 新增 `year` 和 `month` 可选参数，支持补签任意年月
  - 默认行为保持为当月，但架构支持跨月扩展
- **数据校验增强**: 完善导入数据校验
  - 新增 `deer_records[i].user_id` 类型检查（必须为字符串）
  - 新增 `_is_valid_date()` 函数验证年月日组合的真实性（如排除 2 月 31 日）
  - 使用 `datetime.date()` 验证日期合法性
- **ID 规范化统一**: 引入 `normalize_user_id()` 辅助函数统一用户 ID 处理
  - 替换所有分散的 `str()` 转换为 `normalize_user_id()`
  - 便于集中管理 ID 规范化逻辑，避免不一致
  - 
### Fixed
- **AT 全体成员处理**: 修复用户 AT 全体成员 (`@all`) 时的权限判断 Bug
  - 现在尝试帮"全体成员"🦌会被直接拒绝，并提示"不能帮全体成员🦌"
  - 避免将 `"all"` 当作普通用户 ID 查询数据库导致误判
- **自己🦌自己权限**: 修复用户 AT 自己时的权限判断逻辑
  - 当用户设置"禁止被帮🦌"但 AT 自己时，现在允许打卡
  - 自己🦌自己不再受 `allow_help` 设置限制

## [1.0.3] - 2026-03-22

### Fixed
- **权限检查漏洞**: 修复 `/deer @用户` 命令未检查目标用户是否允许被帮打卡的问题
  - 现在使用 `/deer @用户` 或 `/🦌 @用户` 时会正确检查目标用户的 `allow_help` 设置
  - 如果目标用户禁止被帮打卡，操作将被拒绝并提示"用户 xxx 不允许被帮🦌"

### Changed
- **插件更名**: 插件名称从"🦌管"更名为"鹿乃子月历"，更加正能量
- **描述优化**: 更新插件描述，突出健康生活的主题

## [1.0.2] - 2026-03-19

### Fixed
- **AI 帮打卡数据缺失**: 修复 LLM 工具 `deer_other` 帮用户打卡时只显示当天记录的问题
  - `deer_other` 现在返回 `calendar_data` 字段，包含每个打卡成功的用户的完整月度打卡数据
  - 显示鹿历时优先展示操作者自己的日历（当操作者在目标列表中时）
  - 优化数据库查询：使用 `get_calendar_data_batch` 批量获取日历数据，避免 N+1 查询问题``

## [1.0.1] - 2026-03-18

### Added
- **AI 行为配置**: 新增 `allow_ai_help_self` 配置项，支持禁用 LLM 帮用户自己打卡（默认启用）
- **文件导入保护**: 导入命令增加 5 分钟会话超时和 10MB 文件大小限制
- **数据校验**: 导入数据时增加字段范围校验（month: 1-12, day: 1-31, count: ≥0）

### Changed
- **命令调整**: `/鹿管数据` 命令组更名为 `/管理鹿管数据`，解决与 `/鹿` 命令的冲突问题
- **并发安全**:
  - `utils._get_aiohttp_session()` 改为异步函数，使用双重检查锁避免并发创建
  - `renderer._avatar_cache` 添加 `asyncio.Lock` 保护
- **缓存管理**: 头像缓存改用 `OrderedDict` 实现 LRU 策略，限制最大 1024 条目
- **异常处理**: 所有 `INTERNAL_ERROR` 返回前记录详细异常日志

### Fixed
- **方法名错误**: 修复 `commands.py` 中 `get_retro_count_today` → `get_today_retro_count` 的调用错误
- **死锁风险**: 修复 `renderer._cleanup_avatar_cache` 嵌套锁导致的死锁问题
- **空目标检查**: `deer_other` 增加空 `target_ids` 检查
- **参数简化**: `_calculate_consecutive_days` 移除未使用的 `year/month` 参数
- **数据库操作**: `set_last_retro_date` 添加 `ensure_user_config` 前置调用
- **导入安全**: `import_all_data` 防止负数 count 累加破坏数据
- **输入校验**: `fetch_avatar_base64` 增加 `user_id` 格式校验
- **日志准确**: `tool_get_user_deer_data` 异常日志记录解析后的值
- **开关识别**: `parse_allow_flag` 扩展支持更多表达方式（开启/关闭/启用/禁用等）
- **装饰器规范**: `@filter.command_group` 方法添加 `event` 参数
- **生命周期**: 插件卸载时调用 `close_aiohttp_session` 释放连接

### Security
- **哈希注释**: `hashlib.md5` 使用处添加注释说明非安全用途

## [1.0.0] - 2026-03-08
- 新建仓库
