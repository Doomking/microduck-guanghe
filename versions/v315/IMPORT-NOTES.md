# V315 / control.127 源码导入说明（fork 侧）

- 导入日期：2026-11-26（microduck-guanghe fork）
- 来源：上游 Release `console-studio-v313` 资产 `Microduck-Console-Studio-V315.zip`
  <https://github.com/kissqy/Microduck-kissqy/releases/download/console-studio-v313/Microduck-Console-Studio-V315.zip>
- ZIP SHA256（与官方 API digest 核对一致）：`878e9661085f53ae37570831ce3149bfaddc7b206f21964f039fc7ebdb7db4f9`

## 目录布局

- `console/` = ZIP 内 `Microduck-Console-Studio-V315/` 的完整内容（中控 Python + static/ 前端 + updates/ 固件包 + source/ 原生源码归档 + 许可证）。
  与上游 git `versions/v260` 收纳惯例的差异：本 fork **保留 updates/ 二进制固件包**，便于离线校验与重打包。
- `firmware/` = `console/source/Microduck-Native-Build-Source-V313.tar.gz` 的解包内容（去掉顶层目录），即 control.127 原生固件 Rust 源码，便于浏览、打补丁、与 `versions/v260/firmware` 对比。

## 关键身份（详见 console/BUILD_MANIFEST.json、console/source/SOURCE.json）

- service_build：`1fa843-feetech-ft6-control.127`；console_version：`1.0.315`
- 固件包 `updates/Microduck-Robotd-FT6-R17.tar.gz` SHA256：`42cd56d5bfcabcceb581729437bb16289e8b3efdd9f16552b14a3adc2f7455fb`
- 原生源码归档 SHA256：`b3818b7857760ed0b3b6266d913f42c8141ac22d1faa0f79fe03633384c274e6`
- 上游 source_commit：`318bb3c13830c3d52ee3c706defac1443b69aff6`；固件源码基线目录：上游 `versions/v260/firmware`
- 工具链：Rust 1.99.0 / cargo-zigbuild 0.23.4 / Zig 0.15.1；target `aarch64-unknown-linux-gnu.2.31`
- 本包维护组件为 `updates/Microduck-Maintenance-V315.tar.gz`。V315 相对 V313 仅中控变化（maintenance_worker/positions/components.py、release_identity.py、static 若干、docs）；固件包与原生源码归档逐字节相同。

## 许可与注意

- 许可为 Personal-NonCommercial（见 `console/Personal-NonCommercial.txt`、`console/LICENSE-SCOPE.txt`），fork 仅个人非商业使用。
- 本目录是**上游官方原版，未含 fork 的 Nova Lite 手柄补丁**；直接刷用会回退手柄修复。补丁移植（P4）应基于本目录源码进行。

## 手柄桥源码位置（P4 相关）

- 原生源码归档（`firmware/`）**不含** gamesir-xboxd 桥的 C 源码（gamepad-r7 下仅 tests）。
- 桥的 C 源码随固件包发布：`console/updates/Microduck-Robotd-FT6-R17.tar.gz` 内 `Microduck-Robotd-FT6-R17/gamepad-r7/gamesir-xboxd.c`（同包还有桥二进制、`70-gamesir-xbox-bridge.rules`、`gamesir-xboxd.service`）。
- fork 已打补丁的 43 代桥源码在仓库 `microduck-hd1910/firmware/gamepad-r7/gamesir-xboxd.c`。P4 移植时以包内 C 源码为基线对比打补丁。
