# Checklist

- [x] 项目能通过 `python -m clipshare` 或打包后的可执行文件启动
- [x] `clipshare start` 可启动后台进程，监听剪贴板变化
- [x] `clipshare list` 可显示局域网内在线设备及其配对状态
- [x] `clipshare pair <name>` 可向指定设备发起配对，对方确认后配对成功
- [x] `clipshare name <name>` 可修改本机设备名
- [x] `clipshare stop` 可停止后台进程
- [x] `clipshare status` 可查看运行状态和已配对设备
- [x] UDP 广播能发现局域网内其他设备，并正确显示在线/离线状态
- [x] 首次配对时双方完成 Diffie-Hellman 密钥交换，生成共享 AES 密钥
- [x] 密钥持久化存储到本地配置文件，重启后无需重新配对
- [x] 在设备 A 复制纯文本，设备 B 剪贴板自动同步相同文本
- [x] 在设备 A 复制富文本，设备 B 剪贴板同步后保留格式
- [x] 在设备 A 复制图片，设备 B 剪贴板同步相同图片
- [x] 在设备 A 复制文件，设备 B 收到文件并写入临时目录，文件路径写入剪贴板
- [x] TCP 传输内容经过 AES 加密，抓包无法直接读取明文
- [x] PyInstaller 打包的 macOS 可执行文件可独立运行
- [x] PyInstaller 打包的 Windows 可执行文件可独立运行
- [x] 配置文件存储在用户目录下的 `.clipshare/config.json`