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

## 版本源码导入（2026-11-26）

- `versions/v313/`、`versions/v315/` 已导入上游官方 Release ZIP 的完整包内源码（`console/` + `firmware/`），ZIP SHA256 与官方 API digest 核对一致；溯源、布局与关键身份见各目录 `IMPORT-NOTES.md`。
- 两代共用 control.127 固件包（`Microduck-Robotd-FT6-R17.tar.gz`，sha256 `42cd56d5…`）与同一份原生源码归档（sha256 `b3818b78…`）；V315 相对 V313 仅中控更新。
- 手柄桥 C 源码不在原生源码归档里，而在固件包内 `gamepad-r7/gamesir-xboxd.c`；P4 移植以该文件为基线，对照本仓库 `microduck-hd1910/firmware/gamepad-r7/gamesir-xboxd.c`（已打补丁的 43 代）。
- V297/V302 为过渡 Beta（固件复用 control.102，源码已在 git `versions/v260`），未导入，按上游 README 从 Release ZIP 获取。
- `versions/v313/` 保持上游原版参考；`versions/v315/` 已完成 P4 手柄补丁移植（见下节）。main 工作树（control.43 + 补丁）不受影响。

## P4：V315 / control.127 手柄补丁移植（2026-11-26）

在 `versions/v315/` 上把 43 fork 的 Nova Lite 补丁移植到官方 control.127 基线，**构建标识不变（control.127 / 中控 1.0.315）**：

1. 桥 C 源码：以包内官方 V238 源码为基线，套用同一 6 行名称匹配补丁（`versions/v315/patches/nova-lite.patch`）。**B 键跟随官方 127 保持未分配**；官方 `test_b_unmapped` 实机 PASS。
2. udev 规则 +1 行（与 43 逐字节相同）；`console/gamepad_repair.py` 与 43 补丁版逐字节相同；`static/gamepad-repair.js` 改 1 行文案。
3. 重打 `versions/v315/console/updates/Microduck-Robotd-FT6-R17.tar.gz`：188 成员中替换 6 个，其余 182 个逐字节不变；同步 `SHA256SUMS`、`BUILD.json`、`ELF-CHECK.json`、`console/BUILD_MANIFEST.json`。
   - 新包 sha256 `c26c1f80…`（30,110,809 B）；新桥二进制 sha256 `f7d7d101…`（71,872 B，gcc 12.2 实机原生编译，**glibc ≥ 2.34**）。
   - `hardware_verified: false`：尚未刷入实机；当前鸭子仍运行 control.43 + 补丁，升级到 127 是独立决定。
4. 详细记录见 `versions/v315/IMPORT-NOTES.md` 文末 P4 节。
