# 局域网共享剪贴板 (LAN Clipboard Sync) Spec

## Why
在同一局域网内，用户经常需要在 Windows 和 macOS 设备之间复制粘贴文本、图片、文件等内容，但现有方案依赖云服务或需要额外硬件。本项目提供一个轻量级的 CLI 工具，通过局域网实现剪贴板内容的自动同步。

## What Changes
- 新增基于 Python 的跨平台 CLI 剪贴板同步工具
- UDP 广播实现局域网设备自动发现
- TCP 协议实现剪贴板内容和文件的可靠传输
- AES 对称加密 + 首次配对 Diffie-Hellman 密钥交换保障传输安全
- 支持文本、图片、富文本、文件四类剪贴板内容同步
- 一对多广播模式：一台设备复制，所有已配对设备自动同步
- PyInstaller 打包为单一可执行文件，无需安装 Python 运行环境

## Impact
- Affected specs: 无（新项目）
- Affected code: 全新代码库，无现有代码影响

## ADDED Requirements

### Requirement: 设备发现
系统 SHALL 通过 UDP 广播在局域网内自动发现运行本工具的其他设备。

#### Scenario: 新设备上线
- **WHEN** 用户启动程序
- **THEN** 程序在局域网内发送 UDP 广播包，其他在线设备收到后回复自身信息（设备名、IP、端口、公钥）

#### Scenario: 设备离线检测
- **WHEN** 某设备意外断开网络或关闭程序
- **THEN** 其他设备通过心跳超时检测到该设备离线，并从在线列表移除

### Requirement: 设备配对与密钥交换
系统 SHALL 在首次与陌生设备通信前完成配对，交换加密密钥。

#### Scenario: 发起配对请求
- **WHEN** 用户通过 CLI 命令向指定设备发起配对
- **THEN** 双方通过 Diffie-Hellman 算法交换密钥，生成共享的 AES 密钥
- **THEN** 目标设备 CLI 提示用户确认配对请求
- **THEN** 配对成功后，密钥持久化存储在本地配置文件中

#### Scenario: 拒绝配对
- **WHEN** 目标设备用户拒绝配对
- **THEN** 发起方收到拒绝通知，不建立加密通信

### Requirement: 文本内容同步
系统 SHALL 在用户复制文本时自动将内容同步到所有已配对设备。

#### Scenario: 复制纯文本
- **WHEN** 用户在设备 A 上复制一段文本
- **THEN** 设备 A 检测到剪贴板变化，将文本内容 AES 加密后通过 TCP 发送给所有已配对设备
- **THEN** 接收设备解密后将内容写入本地剪贴板

### Requirement: 富文本内容同步
系统 SHALL 支持保留格式的富文本（RTF/HTML）同步。

#### Scenario: 复制带格式文本
- **WHEN** 用户从浏览器或文档编辑器复制带格式内容
- **THEN** 系统同时获取纯文本和富文本格式，加密后发送
- **THEN** 接收端写入剪贴板时保留格式

### Requirement: 图片内容同步
系统 SHALL 支持剪贴板中图片的同步。

#### Scenario: 复制图片到剪贴板
- **WHEN** 用户截图或将图片复制到剪贴板
- **THEN** 系统检测到图片内容，读取图片二进制数据
- **THEN** 加密后通过 TCP 发送给所有已配对设备
- **THEN** 接收端将图片写入本地剪贴板

### Requirement: 文件内容同步
系统 SHALL 支持剪贴板中文件引用的同步（文件路径列表+文件内容传输）。

#### Scenario: 复制文件
- **WHEN** 用户在资源管理器/Finder 中复制文件
- **THEN** 系统读取剪贴板中的文件路径列表
- **THEN** 依次通过 TCP 直传每个文件的内容到已配对设备
- **THEN** 接收端将文件保存到临时目录，并将文件路径写入剪贴板

### Requirement: 设备命名
系统 SHALL 支持自动获取 hostname 作为设备名，并允许用户手动修改。

#### Scenario: 首次启动默认命名
- **WHEN** 用户首次启动程序，未手动设置设备名
- **THEN** 系统自动使用本机 hostname 作为设备名

#### Scenario: 手动修改设备名
- **WHEN** 用户执行改名命令
- **THEN** 设备名更新并持久化，广播通知其他设备名称变更

### Requirement: CLI 命令接口
系统 SHALL 提供以下 CLI 子命令。

#### Scenario: 启动同步服务
- **WHEN** 用户执行 `clipshare start`
- **THEN** 程序以后台进程方式启动，开始监听剪贴板变化和网络请求

#### Scenario: 列出在线设备
- **WHEN** 用户执行 `clipshare list`
- **THEN** 显示局域网内所有在线设备及其状态（已配对/未配对/在线/离线）

#### Scenario: 配对设备
- **WHEN** 用户执行 `clipshare pair <device-name>`
- **THEN** 向指定设备发起配对请求

#### Scenario: 修改设备名
- **WHEN** 用户执行 `clipshare name <new-name>`
- **THEN** 更新本地设备名

#### Scenario: 停止服务
- **WHEN** 用户执行 `clipshare stop`
- **THEN** 停止后台进程

#### Scenario: 查看状态
- **WHEN** 用户执行 `clipshare status`
- **THEN** 显示当前运行状态、已配对设备列表、本机设备名

### Requirement: 跨平台剪贴板访问
系统 SHALL 在 Windows 和 macOS 上正确读写剪贴板中的文本、图片、富文本和文件引用。

#### Scenario: macOS 剪贴板操作
- **WHEN** 运行在 macOS 上
- **THEN** 使用 AppKit (via pyobjc) 或 `osascript` 访问剪贴板

#### Scenario: Windows 剪贴板操作
- **WHEN** 运行在 Windows 上
- **THEN** 使用 Win32 API (via pywin32) 访问剪贴板

### Requirement: 单文件分发
系统 SHALL 通过 PyInstaller 打包为独立的可执行文件，用户无需安装 Python。

#### Scenario: 用户获取程序
- **WHEN** 用户下载对应平台的可执行文件
- **THEN** 直接双击或在终端中运行，无需安装任何依赖