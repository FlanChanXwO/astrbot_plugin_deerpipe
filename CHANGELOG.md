# Changelog

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
