# 读取顺序接口

复用现有 robot.busCommand 和常驻管理通道，不调用编号／中位维护程序。

| 操作 | HTTP 接口 | 请求体 | 原生 action |
| --- | --- | --- | --- |
| 查询实际顺序 | POST /api/service/read-order/status | `{}` | read-order-status |
| 指定舵机移到末尾 | POST /api/service/read-order | `{"id":10,"session":"当前统计会话","revision":0}` | read-order-last |

查询返回 read_order 的 applied、desired、revision、applied_revision 和 pending，以及当前通信统计。applied 仅在实际请求发送后更新。写入返回 accepted 和 read_order；界面查询实际生效状态，不重发写入。

IMU 200 固定首位，累计未回包须超过 10 次；session 和 revision 来自当前查询。新接口仅管理读取 ID 的排列与保存文件，不改变寄存器地址、读取长度、串口时限及反馈解码。保存文件为参数目录旁的 telemetry-read-order.json，使用临时文件和替换保存，普通固件升级不覆盖它。
