# 🦆 microduck-guanghe

**Microduck（飞特 HD1910 机器人鸭）个人 fork** —— 基于 [kissqy/Microduck-kissqy](https://github.com/kissqy/Microduck-kissqy)（fork 基线 `8df8113`，2026-11-26），并引入 [fanhao375/microduck-replica](https://github.com/fanhao375/microduck-replica) 子树。**仅供个人、非商业用途。**

上游原版 README 留存于 [README.upstream.md](README.upstream.md)（英文 [README.en.md](README.en.md)）；制作教程、采购清单、装配资料等仍以上游为准。本 README 只说明 fork 自身。

## 这个 fork 做什么

1. **GameSir Nova Lite 手柄支持**：control.43 与 control.127 两代固件桥接补丁并重打包（43 代已实机验证；127 代实机编译 + 官方测试 PASS，待刷入）。
2. **上游多版本源码存档**：V167 / V260 / V313 / V315 完整包内源码收在 `versions/`，可离线校验与重打包。
3. **Replica 校准资料**：`replica/` 子树，主要使用其中的舵机校准与装配资料。

## 仓库布局

| 路径 | 内容 | 状态 |
|---|---|---|
| `microduck-hd1910/` | 43 代工作树：control.43 + Nova Lite 补丁，含中控 | 当前在用（当前鸭子） |
| `versions/v167/` | 上游 1.0.167 / control.43 完整源码 | 存档 |
| `versions/v260/` | 上游 1.0.260 / control.102 完整源码 | 存档 |
| `versions/v313/` | V313 官方包源码（固件 control.127） | 上游原版参考 |
| `versions/v315/` | V315 官方包源码 + **P4 Nova Lite 补丁** | 可用（新鸭子） |
| `versions/v315/patches/` | 127 代手柄补丁文本参考（C / udev / diff） | 供上游同步时重新套用 |
| `replica/` | microduck-replica 子树 | 许可见子树内文件 |
| `NOTICE.md` | fork 改动记录、许可与署名声明 | |

## 两条版本线与配对

**`control.N` 是鸭子固件，`VNNN` 是电脑中控**，按发布配对。**启动哪个中控，就决定装哪代固件**（随包固件 sha 门禁，不能交叉刷）：

| 中控 | 固件 | 随包固件 sha256 前 8 位 | 用途 |
|---|---|---|---|
| V167 / 1.0.167 | control.43 | `7933d9d0`（补丁；官方 `bcfd5c18`） | 当前鸭子 |
| V260 / 1.0.260 | control.102 | `d301e5e9`（官方） | 存档 |
| V313 / V315 | control.127 | `c26c1f80`（V315 补丁；官方 `42cd56d5`） | 新鸭子 |

⚠️ 固件包文件名都叫 `Microduck-Robotd-FT6-R17.tar.gz`，**只能靠 sha256 / 包内 BUILD.json 区分代际**。查鸭子当前已装版本：

```sh
ssh radxa@<鸭子IP> "cat /opt/robot/feetech-ft5-r5/release_identity.py"
```

## 快速开始

中控需 Python 3.12（本体纯标准库）。两代中控是独立进程，可同时跑在不同端口；**不要用两个中控同时操作同一只鸭子**。

```sh
# 43 代中控（当前鸭子，默认端口 8090）
cd microduck-hd1910/firmware/console
python3.12 console.py --dashboard --feetech --open

# V315 中控（新鸭子 / 试 127，换个端口）
cd versions/v315/console
python3.12 console.py --dashboard --feetech --open --port 8091
```

启动后在页面填写鸭子 SSH 地址与密码连接（也可 `--ssh radxa@<IP>`）。

鸭子侧：

- **系统**：Radxa Zero 3W 官方 **Debian 12** 镜像刷 SD 卡（glibc ≥ 2.34，补丁桥的要求）。
- **固件**：中控页面"随包固件 → 固件安装"（SSH 上传 → sha 校验 → 逐文件原子替换 → 重启），**不刷 SD 卡、保留校准**。
- **手柄**：GameSir Nova 2 Lite / Nova Lite，保持 **A+HOME** 模式；慢闪时按住 **HOME+截图** 2–3 秒进配对；用中控"手柄连接 / 修复"。
- 注意：control.127 上 **B 键官方未分配**（上游 V238 的改动，非 fork 补丁）。

## 固件升级流程（以 43 → 127 为例）

1. 启动 V315 中控，连接目标鸭子；
2. 页面"随包固件 control.127"→ 固件安装：`bundle_info()` sha 门禁 → SSH 上传校验 → `service.sh` / `install-files.py` 逐文件原子替换（保留校准与用户模型）→ robotd 四步就绪 → 重启鸭子；
3. 重启后核对 `release_identity.py` 为 `control.127`。

构建标识不变（control.127 / 1.0.315），本 fork 不发布新版本号。当前鸭子保持 control.43，不升级。

## 上游同步

```sh
git fetch upstream main && git merge upstream/main
# 手柄补丁若冲突，按 NOTICE.md 与 versions/v315/patches/ 重新套用
git subtree pull --prefix=replica <replica-remote> master
```

## 许可与署名

- 上游分项许可继续生效（Personal-NonCommercial 等），见 `LICENSE`、`microduck-hd1910/LICENSES/`、`NOTICE.md`；本 fork 不对上游内容重新授权。
- `replica/` 子树遵循其自带 `replica/LICENSE` 与 `replica/NOTICE.md`。
- 模型权重来源见 `microduck-hd1910/docs/MODEL-PROVENANCE.md`。
- 个人学习/爱好项目，非官方发布，不提供任何形式的担保。官方发布与商用授权请联系上游作者。
