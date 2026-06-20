# Tasks

- [x] Task 1: 项目骨架搭建
  - [x] 创建 Python 项目目录结构（src/clipshare/）
  - [x] 编写 `setup.py` / `pyproject.toml`，定义项目依赖
  - [x] 实现 CLI 入口 `clipshare`，使用 argparse 解析子命令（start/list/pair/name/stop/status）
  - [x] 实现配置管理模块，读写本地配置文件（设备名、配对密钥等 JSON 格式）

- [x] Task 2: 设备发现与心跳
  - [x] 实现 UDP 广播模块：定期发送广播包，声明自身信息
  - [x] 实现 UDP 监听模块：接收其他设备的广播包，维护在线设备列表
  - [x] 实现心跳超时检测，移除离线设备

- [x] Task 3: 设备配对与加密
  - [x] 实现 Diffie-Hellman 密钥交换模块
  - [x] 实现 AES 加密/解密模块（用于后续所有数据传输）
  - [x] 实现配对请求/响应流程（TCP 通道）
  - [x] 配对密钥持久化存储

- [x] Task 4: 跨平台剪贴板读写
  - [x] 实现 macOS 剪贴板访问（文本、图片、富文本、文件引用）
  - [x] 实现 Windows 剪贴板访问（文本、图片、富文本、文件引用）
  - [x] 实现统一的剪贴板抽象层，根据平台自动选择实现

- [x] Task 5: 内容同步引擎
  - [x] 实现剪贴板变化监听（轮询检测）
  - [x] 实现 TCP 服务端：接受配对设备连接，接收加密数据
  - [x] 实现 TCP 客户端：向已配对设备发送剪贴板内容
  - [x] 实现内容类型识别与序列化（文本/图片/富文本/文件）
  - [x] 实现文件直传（分块传输 + 进度显示）

- [x] Task 6: CLI 命令实现
  - [x] 实现 `clipshare start`：启动后台守护进程
  - [x] 实现 `clipshare list`：列出在线设备
  - [x] 实现 `clipshare pair <name>`：发起配对
  - [x] 实现 `clipshare name <name>`：修改设备名
  - [x] 实现 `clipshare stop`：停止后台进程
  - [x] 实现 `clipshare status`：查看运行状态

- [x] Task 7: PyInstaller 打包
  - [x] 编写 PyInstaller spec 文件
  - [x] 配置 macOS 和 Windows 打包参数
  - [x] 编写构建脚本

# Task Dependencies
- Task 2 依赖 Task 1（需要配置模块和项目结构）
- Task 3 依赖 Task 2（配对需要先发现设备）
- Task 5 依赖 Task 3 和 Task 4（同步需要加密和剪贴板能力）
- Task 6 依赖 Task 1、Task 2、Task 3、Task 5
- Task 7 依赖 Task 6（所有功能实现完成后打包）
- Task 4 可与 Task 2、Task 3 并行开发