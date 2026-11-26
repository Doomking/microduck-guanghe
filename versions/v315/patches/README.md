# V315 / control.127 手柄补丁参考（P4）

本目录是 fork 补丁的**文本参考**，便于 git diff 审阅与未来上游同步时重新套用；
实际生效的文件在 `console/updates/Microduck-Robotd-FT6-R17.tar.gz` 包内（已重打）与 `console/` 下。

- `gamesir-xboxd.c`：官方 127 包内 C 源码（V238，B 未分配）+ 6 行 Nova Lite 名称匹配补丁。
  sha256 `615145623d50f53deb4bff6be443ff6976001ca7c6eedce9338a588d9f963398`。
- `nova-lite.patch`：相对官方 127 C 源码的 unified diff（即全部改动）。
- `70-gamesir-xbox-bridge.rules`：官方规则 + 1 行 Nova Lite 隐藏规则（与 43 fork 逐字节相同）。
  sha256 `54f3f57e22043e7ca931cda60ad42a1bc6823554b2aa6dc5a8ef666ada17daca`。
- 桥二进制只在固件包内：sha256 `f7d7d101ebd768325d1cd0f269df94500b62a2244099f7ee3b5281590fba9a4c`，
  71,872 字节，AArch64 PIE，NEEDED libc.so.6，glibc 下限 2.34。
  重建：在 Radxa Zero 3W（Debian 12）上 `gcc -O2 -pthread gamesir-xboxd.c -o gamesir-xboxd`；
  官方测试 `gcc -O0 -UNDEBUG -Wall -Wextra -pthread tests/test_b_unmapped.c -o t && ./t` 须 PASS。
