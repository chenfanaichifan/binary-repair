# 同一网络固定访问

## 固定入口

```text
http://huademacbook-pro.local:8124/?token=<LAN_TOKEN>
```

IP 备用入口（DHCP 可能变化）：

```text
http://10.11.0.237:8124/?token=<LAN_TOKEN>
```

token 保存在本机：

```text
var/lan.token   (chmod 0600, git-ignored)
```

## 启动

```bash
./start-lan.sh
```

脚本会：

- 使用固定端口 `8124`，绑定 `0.0.0.0`；
- 复用 `var/lan.token`，不会每次重启换 token；
- 允许 `huademacbook-pro.local`、`10.11.0.237` 和 localhost；
- 数据目录固定为 `var/lan-data`；
- 打印 hostname 与 IP 两个入口。

## 为什么用 `.local`

`huademacbook-pro.local` 是 Bonjour/mDNS 主机名，IP 变化时仍可解析（macOS、iOS 和安装 Bonjour 的 Windows 支持）。  
如果对方设备不解析 `.local`，使用 IP 入口；若路由器重新分配 IP，建议在路由器上为该 Mac 做 DHCP 地址保留。

## 注意

- 这是同一局域网入口，不经过 ngrok；不要把它暴露到公网。
- token 是访问凭证，不要发到公开群或提交到 Git。
- 防火墙当前关闭；如果开启防火墙，需要允许 Python/uvicorn 接受传入连接。
- 端口冲突时可用 `BINARYREPAIR_LAN_PORT=8125 ./start-lan.sh`。
