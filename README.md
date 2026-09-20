# MaaAssistantAzurPromilia

蓝色星原：旅谣 PC 助手，基于 [MaaPracticeBoilerplate](https://github.com/MaaXYZ/MaaPracticeBoilerplate) 和 [MaaFramework](https://github.com/MaaXYZ/MaaFramework)，首批适配 bilibili 电脑版。

**开发中。** 目前正在完成邮件、签到、日常任务与活跃度奖励的识别、领取及异常处理。尚未发布可供普通用户使用的稳定版本。

## 当前进展

- Win32 游戏窗口连接与 FramePool 截图已在本机验证。
- 已实测领取“来自星海的礼赠”签到奖励、邮件奖励和日常登录任务奖励。
- 正在完善完整任务编排、重复运行检查及日常活跃度宝箱领取。
- 识别坐标以 1280×720 为基准，通过 MaaFramework 等比例缩放适配 16:9 分辨率；其他比例尚未验证。

## 项目方向

采用“识别页面 → 执行操作 → 验证结果”的任务流程。运行库、截图、日志、账号信息与本地配置不进入版本控制。

开发结构参考 [MaaEnd](https://github.com/MaaEnd/MaaEnd) 的模块化任务与状态识别设计；游戏节点根据蓝色星原实际画面重新实现。

## 许可

项目代码遵循 [MIT](LICENSE) 许可。MaaFramework、通用界面及其他依赖的许可归各自项目所有。游戏名称与画面素材归游戏权利人所有。
