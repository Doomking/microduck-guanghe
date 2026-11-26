# NOTICE — microduck-guanghe

本仓库是 [kissqy/Microduck-kissqy](https://github.com/kissqy/Microduck-kissqy) 的**个人 fork**（fork 基线 `8df8113`，2026-11-26），仅供个人、非商业用途。

## 许可范围（沿用上游，未改动）

- 上游分项许可索引继续生效：见 `LICENSE`、`microduck-hd1910/LICENSE`、`microduck-hd1910/LICENSES/Personal-NonCommercial.txt`。
- 模型权重逐模型确认来源与授权：`microduck-hd1910/docs/MODEL-PROVENANCE.md`。
- 本 fork 不对任何上游内容重新授权，也不撤回上游已有效授予的 Apache、MIT 等许可。
- `replica/` 子树遵循其自带的 `replica/LICENSE` 与 `replica/NOTICE.md`（原创代码与工具 Apache-2.0，硬件设计资料另行许可）。

## 相对上游的改动（仅手柄相关）

构建标识保持 **`control.43` / 中控 `1.0.167`**，未发布新版本：

1. `gamepad-r7/gamesir-xboxd.c` 与 udev 规则：支持 GameSir Nova Lite（HID `3537:1041`，A+HOME 模式），将其物理输入从游戏客户端隐藏，桥接为标准 Xbox 360 手柄。
2. `console/gamepad_repair.py`、`console/static/gamepad-repair.js`：扫描/配对同时识别 Nova 2 Lite 与 Nova Lite；HID 连接改为 `connect <MAC>`（不再附带 HID UUID 参数，bluetoothctl 5.66 会拒绝并报 `Too many arguments`）。
3. 重打 `console/updates/Microduck-Robotd-FT6-R17.tar.gz`：替换 `gamepad-r7/gamesir-xboxd` 为已在实机验证的新二进制（Radxa Zero 3W / Debian 12 / gcc 12.2 原生编译），并同步更新 `SHA256SUMS`、`BUILD.json`、`ELF-CHECK.json`、`console/BUILD_MANIFEST.json`。
   - 注意：新桥接二进制要求 **glibc ≥ 2.34（Debian 12 及以上）**；上游旧二进制仅要求 2.17。其余 156 个包内文件与上游逐字节一致。

## replica/ 子树

- 来源：[fanhao375/microduck-replica](https://github.com/fanhao375/microduck-replica)，经 [Doomking/microduck-replica](https://github.com/Doomking/microduck-replica) master（`d6154cd`）以 `git subtree add --prefix=replica` 整体引入。
- 主要使用其中的舵机校准与装配资料；其许可与署名以子树内文件为准。

## 同步方式

- 上游 kissqy：`git fetch upstream main && git merge upstream/main`；手柄补丁若冲突，按本 NOTICE 所列范围重新套用。
- replica：`git subtree pull --prefix=replica <replica-remote> master`。

## 声明

个人学习/爱好项目，非官方发布，不提供任何形式的担保。官方发布与商用授权请联系上游作者。
