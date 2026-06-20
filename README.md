# Clipshare

轻量级跨平台局域网共享剪贴板工具。无需云端服务器，在同一局域网内即可实现 macOS 与 Windows 之间的剪贴板同步。

## 功能

- 剪贴板同步：纯文本、富文本、图片、文件引用
- 自动发现：UDP 广播自动发现局域网内其他设备
- 安全加密：Diffie-Hellman 密钥交换 + AES-GCM 加密传输
- 跨平台：macOS 和 Windows 原生支持
- 零依赖运行：PyInstaller 打包为独立可执行文件

## 安装

### 方式一：源码运行

```bash
git clone https://github.com/1281174451Ala/clipshare.git
cd clipshare
pip install -e .
clipshare --help
```

### 方式二：独立可执行文件

从 [Releases](https://github.com/1281174451Ala/clipshare/releases) 下载对应平台的二进制文件，直接运行。

## 使用

```bash
# 启动同步服务
clipshare start

# 查看在线设备
clipshare list

# 配对设备
clipshare pair <设备名称>

# 修改本机设备名
clipshare name <新名称>

# 查看运行状态
clipshare status

# 停止服务
clipshare stop
```

### 典型流程

1. 两台设备分别执行 `clipshare start`
2. 在其中一台执行 `clipshare list` 查看对方设备
3. 执行 `clipshare pair <对方设备名>` 完成配对
4. 在一台设备上复制内容，另一台设备剪贴板自动同步

## 构建

### macOS

```bash
pip install pyinstaller cryptography pyperclip Pillow
./scripts/build.sh
```

产物：`dist/clipshare`

### Windows

双击 `scripts\build.bat` 或在 PowerShell 中运行：

```powershell
.\scripts\build.ps1
```

产物：`dist\clipshare.exe`

## 运行测试

```bash
python3 tests/run_tests.py
```

## 架构

```
clipshare/
├── cli.py          # CLI 入口，命令解析
├── daemon.py       # 守护进程，组件编排
├── discovery.py    # UDP 广播设备发现 + 心跳
├── sync.py         # TCP 同步引擎，加密传输
├── crypto.py       # DH 密钥交换 + AES-GCM 加密
├── protocol.py     # 消息序列化协议
├── clipboard.py    # 跨平台剪贴板读写
├── config.py       # 配置管理（JSON 持久化）
└── constants.py    # 常量定义
```

## 安全

- 所有数据传输经过 AES-256-GCM 加密
- 配对使用 Diffie-Hellman 密钥交换，密钥不离开本地
- 无需云端服务器，数据仅在局域网内传输
- 配对密钥存储在本地 `~/.clipshare/config.json`

## 依赖

- Python 3.8+
- cryptography（AES 加密）
- pyperclip（跨平台剪贴板）
- Pillow（图片处理）
- PyInstaller（打包，可选）

## License

MIT