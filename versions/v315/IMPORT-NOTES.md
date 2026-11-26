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
- 本目录原为上游官方原版；**P4 补丁移植已完成**（2026-11-26，见文末记录）：`console/` 与随包固件已含 Nova Lite 手柄补丁。`versions/v313/` 仍为原版参考。

## 手柄桥源码位置（P4 相关）

- 原生源码归档（`firmware/`）**不含** gamesir-xboxd 桥的 C 源码（gamepad-r7 下仅 tests）。
- 桥的 C 源码随固件包发布：`console/updates/Microduck-Robotd-FT6-R17.tar.gz` 内 `Microduck-Robotd-FT6-R17/gamepad-r7/gamesir-xboxd.c`（同包还有桥二进制、`70-gamesir-xbox-bridge.rules`、`gamesir-xboxd.service`）。
- fork 已打补丁的 43 代桥源码在仓库 `microduck-hd1910/firmware/gamepad-r7/gamesir-xboxd.c`。P4 移植时以包内 C 源码为基线对比打补丁。

## P4 移植记录（2026-11-26）

- 基线：固件包内官方 `gamepad-r7/gamesir-xboxd.c`（V238，B 未分配，sha `5594fb99…`）。
  移植 43 fork 的同一 6 行补丁（2 个 `#define` + 名称匹配三条件），见 `patches/nova-lite.patch`。
  **B 键行为跟随官方 127（未分配）**，与 43 代旧基线不同；官方 `tests/test_b_unmapped.c` 在实机编译运行 PASS。
- 重建：Radxa Zero 3W（Debian 12，glibc 2.36）原生 `gcc 12.2.0 -O2 -pthread`，PIE，NEEDED 仅 libc.so.6，glibc 下限 2.34。
  新二进制 sha `f7d7d101ebd768325d1cd0f269df94500b62a2244099f7ee3b5281590fba9a4c`（71,872 B）。
- 重打固件包：188 成员，替换 6 个（桥二进制、`.c`、udev 规则、`BUILD.json`、`ELF-CHECK.json`、`SHA256SUMS`），其余 182 个逐字节不变。
  新包 sha `c26c1f80516ffe59d0549ea5ed6ce0850482118b1696664b95cc15e6f1debdca`（30,110,809 B）。
  `BUILD.json`/`ELF-CHECK.json` 的 `built_binaries` 与 ELF 清单同步更新；`gamepad-r7/gamesir-xboxd` 从 unchanged/reused 移入 rebuilt；新增 `fork_gamepad_rebuild` 记录。
  顶层 `gamepad_binary_sha256` 在 127 中指向 padd（上游历史命名），保持不动。
- 中控侧：`gamepad_repair.py` 与 43 fork 补丁版逐字节相同（sha `c94c3b24…`）；`static/gamepad-repair.js` 改 1 行文案；
  `BUILD_MANIFEST.json` 更新 `service_package_sha256`、`files` 中 3 个 sha 与 `fork_note`。
- **构建标识不变**：`1fa843-feetech-ft6-control.127` / 中控 `1.0.315`；`release_identity.py`、`DEPLOYMENT-IDENTITY.json` 未改动。
- 验证：包内 SHA256SUMS 逐行、`elf_integrity.validate_bundle`、`firmware_packages.bundle_info()` 门禁均通过。
- `hardware_verified: false`：本包尚未刷入实机；刷写升级是独立决定（当前鸭子仍运行 control.43 + 补丁）。
- 已知外观项（与 43 一致，未改）：`gamesir-xbox-status` 与虚拟 Xbox 名称文案仍只提 Nova 2 Lite，仅影响诊断显示。
