# 🦌 鹿乃子月历

<div align="center">

<img src="https://raw.githubusercontent.com/FlanChanXwO/astrbot_plugin_deerpipe/master/logo.png" width="400" alt="鹿乃子月历"/>

<br/>

<img src="https://count.getloli.com/@astrbot_plugin_deerpipe?name=astrbot_plugin_deerpipe&theme=rule34&padding=7&offset=0&align=top&scale=1&pixelated=1&darkmode=auto" alt="Moe Counter">

**一款可爱的每日打卡插件，记录你的健康生活每一天，生成精美的月度打卡日历。**

[![License: AGPL](https://img.shields.io/badge/License-AGPL-blue.svg)](https://opensource.org/licenses/agpl-3.0)
![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue)
![AstrBot](https://img.shields.io/badge/AstrBot-%E2%89%A54.10.4-green)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey)
[![Last Commit](https://img.shields.io/github/last-commit/FlanChanXwO/astrbot_plugin_deerpipe)](https://github.com/FlanChanXwO/astrbot_plugin_deerpipe/commits/master)

</div>

本插件完全开源免费，欢迎 Issue 和 PR。

---

## 📸 预览

<div align="center">
  <table>
    <tr>
      <td align="center">
        <img src="https://raw.githubusercontent.com/FlanChanXwO/astrbot_plugin_deerpipe/master/assets/img_1.png" width="400" alt="日历预览"/>
        <br/>
        <sub>打卡日历</sub>
      </td>
      <td align="center">
        <img src="https://raw.githubusercontent.com/FlanChanXwO/astrbot_plugin_deerpipe/master/assets/img_2.png" width="400" alt="批量报告预览"/>
        <br/>
        <sub>批量打卡报告</sub>
      </td>
    </tr>
  </table>
</div>

---

## ✨ 功能特性

- 📅 **精美日历** - 可视化展示每月打卡记录，支持自定义样式
- 🤝 **好友互助** - 支持帮好友打卡，批量操作一键完成
- 🎨 **批量报告** - 多人打卡时生成精美的批量结算报告
- 🔄 **补卡功能** - 支持补录遗漏的打卡记录
- 📊 **数据统计** - 自动统计打卡次数、连续天数等数据
- 💾 **数据导入导出** - 支持 JSON 格式备份和恢复数据
- 🤖 **LLM 工具** - 提供 AI 工具函数，支持智能查询打卡数据
- 🔒 **隐私设置** - 可设置是否允许他人帮自己打卡

---

## 📦 安装

### 方式一：通过 AstrBot 插件市场安装（推荐）

在 AstrBot 管理面板中搜索 `鹿乃子月历` 并安装。

### 方式二：手动安装

1. 克隆本仓库到 AstrBot 的插件目录：
   ```bash
   cd AstrBot/data/plugins
   git clone https://github.com/FlanChanXwO/astrbot_plugin_deerpipe.git
   ```

2. 重启 AstrBot 或重载插件

---

## 🛠️ 配置项

在 AstrBot 管理面板的「配置」页面，找到 `鹿乃子月历` 插件配置：

### AI 行为配置 (`ai_behavior`)

| 配置项 | 类型 | 说明 | 默认值 |
|--------|------|------|--------|
| `ai_behavior.allow_ai_help_deer` | 布尔值 | 是否允许 AI 帮用户打卡 | `true` |
| `ai_behavior.allow_ai_be_deered` | 布尔值 | 是否允许用户帮 AI 打卡 | `false` |
| `ai_behavior.allow_ai_help_self` | 布尔值 | 是否允许 AI 帮用户自己打卡 | `true` |
| `ai_behavior.custom_prompt` | 字符串 | 自定义 LLM Prompt，影响 AI 对打卡行为的认知和回复风格 | `""` |

### 限制配置 (`limits`)

| 配置项 | 类型 | 说明 | 默认值 |
|--------|------|------|--------|
| `limits.daily_retro_limit` | 整数 | 每日最多补卡次数（0-31，0表示禁止补卡） | `1` |

### 日历配置 (`calendar`)

| 配置项 | 类型 | 说明 | 默认值 |
|--------|------|------|--------|
| `calendar.count_display_mode` | 字符串 | 打卡次数显示模式：`additive`（附加模式，显示为+1）或 `count`（计数模式，显示为x2） | `"additive"` |
| `calendar.show_check_mark` | 布尔值 | 是否在签到区块显示打勾图标 | `true` |

**显示模式说明：**
- **附加模式** (`additive`)：打卡2次显示为 打勾图标 + "+1"
- **计数模式** (`count`)：打卡2次显示为 打勾图标 + "x2"

**打勾图标说明：**
- 开启 `show_check_mark`：签到日期会显示打勾图标 ✓
- 关闭 `show_check_mark`：签到日期只显示打卡次数，不显示打勾图标

---

## 📝 使用方法

### 基础命令

| 命令 | 说明 |
|------|------|
| `/deer` 或 `/🦌` 或 `🦌` | 自我打卡 |
| `/deer @用户` 或 `🦌 @用户` | 帮他人打卡 |
| `/允许被🦌` | 允许他人帮自己打卡 |
| `/禁止被🦌` | 禁止他人帮自己打卡 |
| `/设置被鹿 开 @用户` | 管理员：允许指定用户被帮打卡 |
| `/设置被鹿 关 @用户` | 管理员：禁止指定用户被帮打卡 |
| `/补鹿 <日期>` | 补录指定日期的打卡 |
| `/鹿历` | 查看本月打卡日历 |
| `/上月鹿历` | 查看上月打卡日历 |

### 快速打卡

直接发送以下消息即可快速打卡：

```
🦌          # 自我打卡
鹿           # 自我打卡
撸🦌         # 自我打卡
帮🦌 @用户    # 帮他人打卡
```

### 批量打卡

同时 @ 多个用户，即可生成批量打卡报告：

```
帮🦌 @用户1 @用户2 @用户3
```

### 数据管理

```
/管理鹿管数据 导出    # 导出所有数据为 JSON
/管理鹿管数据 导入    # 导入 JSON 数据（需附带文件）
```

---

## 🤖 LLM 工具

本插件为 AI 提供以下工具函数：

- `deer_self` - 用户自我打卡
- `deer_other` - 帮其他用户打卡
- `retro_deer` - 补打卡
- `set_allow_help` - 设置是否允许被帮打卡
- `get_user_deer_data` - 获取用户打卡数据和统计

在 AstrBot 的 LLM 配置中开启工具调用即可使用。

---

## 📄 开源协议

本项目基于 [AGPL](LICENSE) 协议开源。

---
