# MaaAssistantAzurPromilia

蓝色星原：旅谣 PC 助手，基于 [MaaPracticeBoilerplate](https://github.com/MaaXYZ/MaaPracticeBoilerplate) 和 [MaaFramework](https://github.com/MaaXYZ/MaaFramework)，首批适配 bilibili 电脑版。

**早期开发版，已有 MFAAvalonia 图形界面。** 家园优先接入，尚未发布稳定版本。

## 当前进展

- 家园日常：**一键收获 → 选择候选食物制作 → 收取成品 → 一键补餐**。已有完整流程真机成功记录。
- 低成本候选：小份波波饼（小麦×4，饱腹+25）、惊奇爆谷（玉米×6，饱腹+10）；各自可开关，可调整优先顺序。每轮选择第一个材料足够的候选。
- 制作支持最大数量或一份；材料不足换下一候选，现有队列不取消，最多等待 90 秒。超时保留队列，本轮先补充现有食物，下轮再收取成品。
- 餐桌调用游戏自带“一键添加”，可能使用背包里的饼干、果实等可用料理；无料理时明确报告。
- 邮件全部领取和“来自星海的礼赠”签到已实测单步领取；完整流程的已领取分支也已通过回归。
- 日常登录任务单步已领取；日常活跃度宝箱仍在调试，暂不列入可执行 GUI 任务。
- 任务运行时自动恢复并置顶游戏，完成/失败/停止后恢复原置顶状态，可在界面关闭。

## 本机启动

首次准备需要 Windows x64、Python 3.10+、.NET Runtime 10 x64。已安装依赖后无需重复安装。

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

然后双击 [Start.cmd](Start.cmd)。启动器组装 `install/` 并打开 MFAAvalonia。该目录依赖项目根目录的 `.venv/`，目前不是独立便携发行包。

1. 启动游戏，登录并进入中文主界面。
2. 在助手中选择 `bilibili PC（中文）`、`电脑版 · 前台控制` 和 `AzurPromilia` 窗口。
3. 勾选 **家园日常**，设置候选配方、制作数量和置顶开关，再点击开始。
4. 默认不要同时勾选“家园日常”和“仅一键收获/补餐”，后两项用于单独运行。

## 分辨率与当前限制

识别以 1280×720 为基准，通过 MaaFramework 等比例缩放适配 16:9。当前真机实测为 1920×1080；1280×720、2560×1440 等其他 16:9 分辨率尚未逐一真机验证。非 16:9、黑屏或未知页面会停止输入。

当前烹饪入口基于已观察的家园布局：第一个烹饪锅位于生产建筑第二排第一格，配方第一页可见。其他布局、未解锁家园、餐桌满格等状态尚需更多样本。运行时不要同时操作游戏；输入使用 Seize，会占用鼠标焦点。

日常活跃奖励完整遍历、自动补种、奇波调度、其他烹饪配方和其他画幅在后续计划中，详见 [模块划分](docs/MODULES.md)。

## 开发与验证

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -X utf8 tools\validate_schema.py --schema-dir tools/schema --resource-dirs assets/resource/pipeline --interface-files assets/interface.json
# 只读检查当前画面
.\.venv\Scripts\python.exe -X utf8 tools\run_task.py --inspect
# 真正执行家园任务
.\.venv\Scripts\python.exe -X utf8 tools\run_task.py --entry HomeRoutine
```

开发运行器保存最终截图到 `debug/`；失败时保留当前页面供排查。请勿提交含账号信息的整屏截图或个人配置。

## 项目方向

采用“识别页面 → 执行操作 → 验证结果”的任务流程。运行库、截图、日志、账号信息与本地配置不进入版本控制。

开发结构参考 [MaaEnd](https://github.com/MaaEnd/MaaEnd) 的模块化任务与状态识别设计；游戏节点根据蓝色星原实际画面重新实现。

## 许可

项目代码遵循 [MIT](LICENSE) 许可。MaaFramework、通用界面及其他依赖的许可归各自项目所有。游戏名称与画面素材归游戏权利人所有。
