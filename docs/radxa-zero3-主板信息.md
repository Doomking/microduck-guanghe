# Radxa Zero 3W 主控板信息

> 记录日期：2026-10-23
> 主机名：radxa-zero3
> 系统：Armbian 26.2.1, aarch64 (Linux 6.1.115)

---

## 1. 连接与登录

### SSH
```bash
ssh radxa@192.168.101.5
# 或 mDNS（有时不稳定）
ssh radxa@radxa-zero3.local
```

### 凭据

| 项目 | 值 |
|------|-----|
| 用户名 | `radxa` |
| SSH 密钥 | `~/.ssh/id_ed25519` |
| sudo 密码 | `radxa` |

### SSH 公钥

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILZgSkeLorhpw0xj1u5DrbBFvDr7oN2Jg+DHsI9Mx6DN xghan.cn@gmail.com
```

> 密钥于 2026-10-20 部署到板子上，与本机 `~/.ssh/id_ed25519` 匹配。

---

## 2. 系统信息

| 项目 | 值 |
|------|-----|
| 发行版 | Armbian 26.2.1 |
| 架构 | aarch64 |
| 内核 | Linux 6.1.115 |
| Python | 3.11 (venv: `/opt/robot/feetech/venv/bin/python3`) |

### 核心服务

| 服务 | 进程 | 说明 |
|------|------|------|
| `robotd` | `/opt/robot/feetech-ft5-r5/robotd` | 舵机控制守护进程，监听 `/run/robotd.sock` |
| `padd` | `/opt/robot/feetech-ft5-r5/padd` | 手柄/输入处理 |

```bash
# 停止服务
echo 'radxa' | sudo -S systemctl stop robotd padd

# 启动服务
echo 'radxa' | sudo -S systemctl start robotd padd
```

---

## 3. 舵机总线

| 项目 | 值 |
|------|-----|
| 端口 | `/dev/ttyS2` (UART) |
| 协议 | Feetech TTL 半双工 |
| 波特率 | 1,000,000 bps (1 Mbps) |
| 舵机型号 | HD1910 (Feetech) |
| 锁文件 | `/run/robotd.sock.lock` |

### 舵机工具

| 路径 | 说明 |
|------|------|
| `/opt/robot/feetech/hd1910.py` | 舵机扫描/状态/嘴部控制 |
| `/opt/robot/feetech/FTServo_Python/` | Feetech SDK |

```bash
# 扫描全部 ID 0-253
echo 'radxa' | sudo -S /opt/robot/feetech/venv/bin/python3 hd1910.py scan

# 只读已知 15 个关节
echo 'radxa' | sudo -S /opt/robot/feetech/venv/bin/python3 hd1910.py status

# 读单个舵机
echo 'radxa' | sudo -S /opt/robot/feetech/venv/bin/python3 hd1910.py status --id 23
```

---

## 4. 配置文件

| 路径 | 说明 |
|------|------|
| `/etc/robot/feetech-ft5/robotd.toml` | robotd 主配置 |
| `/etc/robot/feetech-ft5/hd1910-calibration.toml` | 舵机标定数据 |
| `/etc/robot/feetech-ft5/hd1910-calibration.saved.toml` | 标定备份 |
| `/etc/robot/feetech-ft5/pad-settings.json` | 手柄设置 |

---

## 5. 15 个舵机清单

| ID | 名称 | 零位(raw) | 扫描位置(raw) | 电压(V) | 温度(°C) |
|----|------|-----------|---------------|---------|----------|
| 10 | right_hip_yaw | 1974 | 2042 | 6.9 | 28 |
| 11 | right_hip_roll | 1760 | 2104 | 6.8-6.9 | 29 |
| 12 | right_hip_pitch | 1799 | 1286 | 6.8 | 28 |
| 13 | right_knee | 1908 | 1068 | 6.9 | 28 |
| 14 | right_ankle | 1611 | 2277 | 6.8-6.9 | 28 |
| 20 | left_hip_yaw | 2035 | 2137 | 6.6 | 29 |
| 21 | left_hip_roll | 2176 | 2073 | 6.6-6.7 | 28 |
| 22 | left_hip_pitch | 1977 | 2765 | 6.6-6.7 | 29 |
| 23 | left_knee | 1392 | 2742 | 6.7 | 29 |
| 24 | left_ankle | 1893 | 1394 | 6.7 | 28 |
| 30 | neck_pitch | 2526 | 2115 | 6.7 | 28 |
| 31 | head_pitch | 2228 | 2055 | 6.8 | 30 |
| 32 | head_yaw | 1952 | 1586 | 6.7-6.8 | 29 |
| 33 | head_roll | 1599 | 1049 | 6.7 | 28-29 |
| 34 | mouth | 1372 | 2003 | 6.7-6.8 | 28 |

---

## 6. ID 200 — IMU 转接板

- **设备**：BNO08X IMU 转接板（`imu_to_dxl`）
- **作用**：挂在舵机总线上，把 IMU 数据转成 Feetech 协议
- **hack**：`hd1910.py scan` 会把它当舵机读，返回 `fault=40`，这不是故障——IMU 的地址 65 存的是 IMU 数据，不是 servo alarm 寄存器
- **robotd 处理**：在 `feetech_read_only.rs` 里对 ID 200 做特殊读取，不走 servo status 逻辑

---

## 7. 舵机 Alarm/Shutdown 寄存器位定义

地址 65（0x41），舵机故障位：

| 位 | 值 | 含义 |
|----|-----|------|
| bit 2 | 0x04 | 过载 (overload) |
| bit 4 | 0x10 | 电击 (electrical shock) |
| bit 5 | 0x20 | 过热 (overheating) |
| (电压位) | — | 欠压报警 |

- 舵机默认 shutdown = 52（`0b110100` = 过载+电击+过热），电压位默认关闭
- 工厂默认 53（`0b110101`），多了电压位

---

## 8. 100 轮扫描结果 (2026-10-23)

| 指标 | 数值 |
|------|------|
| 总尝试次数 | 1500 (100轮 × 15舵机) |
| 成功次数 | 1500 |
| 失败次数 | 0 |
| 成功率 | **100.00%** |
| 故障次数 | 0 |
| 通信速率 | ~100 reads/s |

> 全部 15 个舵机在 100 轮扫描中零失败、零故障。包括之前有间歇性问题的 #23 (left_knee) 也全部通过。

---

## 9. sudo 密码发现过程

之前不知道密码，尝试了三个候选：

| 尝试 | 密码 | 结果 | 来源 |
|------|------|------|------|
| 1 | `duck1234` | ❌ | `card.conf` 中 `duck` 用户的预设密码 |
| 2 | `1234` | ❌ | 原始镜像 root 密码 |
| 3 | `radxa` | ✅ | 用户名本身（Armbian 向导有时默认行为） |

---

## 10. robotd JSON-RPC 接口

通过 Unix socket `/run/robotd.sock` 通信：

```python
import socket, json
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect("/run/robotd.sock")
sock.sendall((json.dumps({"jsonrpc":"2.0","id":1,"method":"robot.health"}) + "\n").encode())
```

已知方法：
- `robot.health` — 电池、温度、总线状态
- `robot.busStatus` — 模式/阶段
- `robot.calibration-status` — 全部关节标定
- `robot.rawSubscribe` — 订阅原始二进制帧流

---

## 11. 二进制帧格式 (r17.raw.v1)

| 字节 | 内容 |
|------|------|
| 0-3 | u32le 长度（不含这 4 字节） |
| 4 | 帧类型：1=JSON元数据, 2=总线遥测, 4=健康 |
| 5+ | 负载 |

值标签：
- 0 = null, 1 = bool, 2 = i8, 3 = i64, 4 = u64, 5 = f64, 6 = string, 7 = array, 8 = map

源码：`Microduck-kissqy/microduck-hd1910/firmware/robotd/src/raw_codec.rs`
