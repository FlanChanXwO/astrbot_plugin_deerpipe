# 🧪 测试包

本目录包含 `astrbot_plugin_deerpipe` 插件的单元测试。

## ✅ 测试结果

**所有测试已通过** - 共 **72 个测试用例**全部通过，覆盖核心工具函数、业务逻辑、数据库操作和配置验证。

```
============================= 72 passed in 0.07s =============================
```

## 🚀 快速开始

无需安装 AstrBot，直接运行：

```bash
# 从插件根目录运行
python tests/run_tests.py

# 或在 tests 目录内运行
cd tests
python run_tests.py
```

## 📁 目录结构

```
tests/
├── __init__.py              # 测试包初始化
├── conftest.py              # pytest 配置和共享 fixtures
├── README.md                # 本文件
├── run_tests.py             # 跨平台测试运行器
├── run_tests.bat            # Windows 测试运行脚本
├── run_tests.sh             # Unix/Linux/macOS 测试运行脚本
├── test_standalone.py       # 核心测试（36个测试）✅
├── test_extended.py         # 扩展测试（36个测试）✅
├── test_utils.py            # 工具函数测试（依赖 AstrBot）
├── test_database.py         # 数据库管理器测试（依赖 AstrBot）
├── test_service.py          # 业务服务层测试（依赖 AstrBot）
├── test_custom_commands.py  # 自定义命令管理器测试（依赖 AstrBot）
└── mocks/                   # Mock 数据和模拟实现
    ├── __init__.py
    └── data.py              # Mock 数据工厂和模拟类
```

## 📊 测试详情

### `test_standalone.py`（36 个测试）

#### 工具函数测试（27 个）

- **TestNormalizeUserId** (3个) - 用户ID标准化
  - `test_normalize_string_user_id` ✅
  - `test_normalize_int_user_id` ✅
  - `test_normalize_other_types` ✅

- **TestParseAllowFlag** (3个) - 布尔标志解析
  - `test_allow_true_values` ✅ (true, 1, yes, on)
  - `test_allow_false_values` ✅ (false, 0, no, off)
  - `test_allow_invalid_values` ✅

- **TestValidateDay** (5个) - 日期验证
  - `test_valid_days` ✅
  - `test_invalid_days` ✅
  - `test_leap_year` ✅
  - `test_century_leap_year` ✅
  - `test_invalid_month` ✅

- **TestExtractMentionUserIds** (4个) - 提取 @ 用户
  - `test_extract_single_at` ✅
  - `test_extract_multiple_ats` ✅
  - `test_extract_empty_list` ✅
  - `test_extract_with_all` ✅

- **TestCalculateConsecutiveDays** (6个) - 连续天数计算
  - `test_empty_calendar` ✅
  - `test_single_day` ✅
  - `test_consecutive_days` ✅
  - `test_non_consecutive_days` ✅
  - `test_multiple_consecutive_segments` ✅
  - `test_mixed_consecutive` ✅

- **TestIsLeapYear** (3个) - 闰年判断
  - `test_common_leap_years` ✅
  - `test_common_non_leap_years` ✅
  - `test_century_years` ✅

- **TestGetDaysInMonth** (3个) - 月份天数
  - `test_31_day_months` ✅
  - `test_30_day_months` ✅
  - `test_february` ✅

#### 业务逻辑测试（9 个）

- **TestDeerRecordLogic** (2个) - 打卡记录逻辑
  - `test_record_creation` ✅
  - `test_record_with_count` ✅

- **TestUserConfigLogic** (2个) - 用户配置逻辑
  - `test_default_config` ✅
  - `test_custom_config` ✅

- **TestPluginConfigStructure** (2个) - 配置结构
  - `test_default_config` ✅
  - `test_custom_groups_structure` ✅

- **TestCalendarLogic** (3个) - 日历逻辑
  - `test_calendar_stats_calculation` ✅
  - `test_frequency_calculation` ✅
  - `test_most_active_day` ✅

### `test_extended.py`（36 个测试）

#### 数据库逻辑测试（5 个）

使用内存 SQLite 数据库：

- **TestDatabaseLogic**
  - `test_create_tables` ✅
  - `test_insert_record` ✅
  - `test_upsert_record` ✅
  - `test_get_monthly_records` ✅
  - `test_user_config_crud` ✅

#### 导出/导入数据测试（4 个）

- **TestExportImportData**
  - `test_export_data_structure` ✅
  - `test_export_json_serialization` ✅
  - `test_import_data_validation` ✅
  - `test_import_invalid_data` ✅

#### 统计计算测试（6 个）

- **TestStatisticsCalculation**
  - `test_total_count_calculation` ✅
  - `test_days_recorded_calculation` ✅
  - `test_average_per_day` ✅
  - `test_frequency_calculation` ✅
  - `test_most_active_day` ✅
  - `test_empty_calendar_stats` ✅

#### 日期边界测试（5 个）

- **TestDateBoundaries**
  - `test_month_boundaries` ✅
  - `test_year_boundaries` ✅
  - `test_date_comparison` ✅
  - `test_last_day_of_month` ✅
  - `test_first_day_of_month` ✅

#### 批量操作测试（3 个）

- **TestBatchOperations**
  - `test_batch_user_processing` ✅
  - `test_batch_with_errors` ✅
  - `test_empty_batch` ✅

#### 字符串格式化测试（4 个）

- **TestStringFormatting**
  - `test_calendar_header_format` ✅
  - `test_stats_format` ✅
  - `test_date_format_iso` ✅
  - `test_message_format_with_variables` ✅

#### 配置验证测试（4 个）

- **TestConfigurationValidation**
  - `test_valid_config_ranges` ✅
  - `test_invalid_config_values` ✅
  - `test_display_mode_options` ✅
  - `test_boolean_config_values` ✅

#### 文件操作测试（2 个）

- **TestFileOperations**
  - `test_temp_file_creation` ✅
  - `test_json_file_read_write` ✅

#### 权限逻辑测试（3 个）

- **TestPermissionLogic**
  - `test_help_allowed_logic` ✅
  - `test_admin_check_logic` ✅
  - `test_self_operation_check` ✅

## 🔧 运行特定测试

```bash
# 运行所有独立测试
python -m pytest tests/test_standalone.py tests/test_extended.py -v

# 运行特定测试文件
python -m pytest tests/test_standalone.py -v
python -m pytest tests/test_extended.py -v

# 运行特定测试类
python -m pytest tests/test_standalone.py::TestValidateDay -v

# 运行特定测试方法
python -m pytest tests/test_standalone.py::TestValidateDay::test_leap_year -v

# 运行扩展测试中的特定类
python -m pytest tests/test_extended.py::TestDatabaseLogic -v
python -m pytest tests/test_extended.py::TestStatisticsCalculation -v

# 显示 print 输出
python -m pytest tests/test_standalone.py -v -s

# 生成覆盖率报告
python -m pytest tests/test_standalone.py --cov=tests.test_standalone --cov-report=term
```

## 📈 测试统计

| 测试文件 | 类别 | 数量 | 覆盖功能 |
|---------|------|------|----------|
| `test_standalone.py` | 工具函数 | 27 | normalize, parse, validate, extract, consecutive days |
| `test_standalone.py` | 业务逻辑 | 9 | record, config, calendar stats |
| `test_extended.py` | 数据库 | 5 | SQLite CRUD, records, config |
| `test_extended.py` | 数据导入/导出 | 4 | JSON serialization, validation |
| `test_extended.py` | 统计计算 | 6 | count, average, frequency, most active |
| `test_extended.py` | 日期边界 | 5 | month boundaries, year boundaries |
| `test_extended.py` | 批量操作 | 3 | batch processing, errors |
| `test_extended.py` | 字符串格式化 | 4 | header, stats, date format |
| `test_extended.py` | 配置验证 | 4 | ranges, options, booleans |
| `test_extended.py` | 文件操作 | 2 | temp files, JSON read/write |
| `test_extended.py` | 权限逻辑 | 3 | help allowed, admin, self check |
| **总计** | **11 类** | **72** | **✅ 全部通过** |

## 📝 添加新测试

在 `test_standalone.py` 或 `test_extended.py` 中添加独立测试：

```python
class TestMyNewFeature:
    """测试新功能."""

    def test_something(self):
        """测试某个功能."""
        result = my_function(input_data)
        assert result == expected_output

    def test_edge_case(self):
        """测试边界情况."""
        assert my_function(0) == expected_result
```

## 🎯 特点

- ✅ **零依赖** - 不依赖 AstrBot 或任何外部框架
- ✅ **快速** - 72 个测试在 0.07 秒内完成
- ✅ **独立** - 每个测试相互独立
- ✅ **全面** - 覆盖核心工具函数、业务逻辑、数据库操作
- ✅ **真实数据库** - 使用内存 SQLite 测试真实数据库操作
- ✅ **易用** - 简单的 pytest 命令即可运行

## 🐛 调试测试

```bash
# 详细输出
python -m pytest tests/test_standalone.py -v --tb=short

# 进入 PDB 调试
python -m pytest tests/test_standalone.py --pdb

# 只运行失败的测试
python -m pytest tests/test_standalone.py --lf

# 显示 print 输出
python -m pytest tests/test_standalone.py -v -s

# 显示所有测试（包括通过的和失败的）
python -m pytest tests/ -v --tb=short
```

---

**现在可以直接运行：** `python tests/run_tests.py`

**总计：72 个测试全部通过 ✅**
