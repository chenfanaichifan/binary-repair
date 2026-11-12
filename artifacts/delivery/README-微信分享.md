# 微信分享操作单

## 直接发到群里（推荐顺序）

1. 打开微信电脑版，进入目标群。
2. 把下面两个文件拖进输入框：
   - `BinaryRepair-Workbench-2026-11-12.zip`
   - 可选：`docs/showcase/01-workbench.png` 作为封面图
3. 打开 `群消息-可直接粘贴.txt`，复制全文，粘贴到群消息框。
4. 发送前确认：
   - 公开链接只用于**演示实例**（mock，无真实 key/样本）；
   - ZIP 中没有 `.venv`、token、历史数据库、真实 key；
   - 组员在同一 Wi-Fi 时可优先用局域网链接，外网用 ngrok 链接。
5. 发送。

## 当前在线演示

- 外网：见 `群消息-可直接粘贴.txt` 中的 ngrok 链接（临时，服务停止即失效）。
- 局域网：`http://10.11.0.237:8124/?token=...`（需同一 Wi-Fi，macOS 防火墙需允许 Python 入站）。
- 演示服务的独立数据目录：`/tmp/binaryrepair-wechat-demo`，与本机 8123 实例隔离。

## 停止在线演示

```bash
kill $(lsof -tiTCP:8124 -sTCP:LISTEN)
kill $(lsof -tiTCP:4040 -sTCP:LISTEN)  # ngrok
```

## 重新启动（如链接失效）

```bash
# 终端 1：演示实例
cd binary-repair-gui
BINARYREPAIR_BACKEND=mock \
BINARYREPAIR_DATA_DIR=/tmp/binaryrepair-wechat-demo \
BINARYREPAIR_SESSION_TOKEN="$(cat /tmp/binaryrepair-wechat-demo/share.token)" \
BINARYREPAIR_ALLOW_TUNNEL=1 \
BINARYREPAIR_ALLOWED_HOSTS=10.11.0.237 \
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8124

# 终端 2：公网隧道
ngrok http 8124 --host-header=127.0.0.1
```

把新的 ngrok 地址替换到群消息；token 不变。
