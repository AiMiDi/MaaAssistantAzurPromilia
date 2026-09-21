# MaaAssistantAzurPromilia

蓝色星原：旅谣 PC 助手，基于 [MaaPracticeBoilerplate](https://github.com/MaaXYZ/MaaPracticeBoilerplate) 和 [MaaFramework](https://github.com/MaaXYZ/MaaFramework)，首批适配 bilibili 电脑版。

**早期开发版，已有 MFAAvalonia 图形界面。** 家园优先接入，尚未发布稳定版本。

## 当前进展

- 家园日常：**收获（含牧场篮子）→ 按需制作小麦饼 → 仅用饼干补餐**。餐桌已满或已有饼干足够时不新增制作。
- 喂食只使用小份波波饼（普通金麦×4，当前游戏实测饱腹+25）。小麦不足则跳过，不改做爆谷。
- 制作默认按餐桌当前缺口扣除饼干库存，也可选仅一份；现有队列不取消，最多等待 90 秒。小麦不足报告缺口及对应种子产量，超时保留队列，下轮收取。
- 餐桌选择饼干卡片进行添加，不使用“一键添加”，保留果实、蘑菇等其他食物。
- 邮件全部领取和“来自星海的礼赠”签到已实测领取；签到会等待卡片状态稳定、处理奖励弹窗并返回菜单，重复运行跳过已领取卡片。
- 家园收获包含奇波牧场入口旁的篮子，识别牧场收获清单并确认篮子消失。
- 通过官方启动器直接启动游戏，识别资源更新确认、等待加载并点击开始旅程；登录或验证需要手动完成。
- 日常任务奖励：滚动检查整个列表，只点击“领取”；检查 20/40/60/80/100 活跃度宝箱。已实测领取每日登录奖励和 20 活跃度宝箱，无新增奖励的完整流程已通过；更高档宝箱仍待实际达标验证，界面标记为测试任务。
- 任务运行时自动恢复并置顶游戏，完成/失败/停止后恢复原置顶状态，可在界面关闭。

## 本机启动

首次准备需要 Windows x64、Python 3.10+、.NET Runtime 10 x64。已安装依赖后无需重复安装。

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

然后双击 [Start.cmd](Start.cmd)。启动器组装 `install/` 并打开 MFAAvalonia。该目录依赖项目根目录的 `.venv/`，目前不是独立便携发行包。

1. 设置官方启动器安装目录（默认 `E:\AzurPromilia bilibili`），启用启动游戏；如需登录请手动完成。
2. 在助手中选择 `bilibili PC（中文）`、`电脑版 · 前台控制` 和 `AzurPromilia` 窗口。
3. 勾选 **家园日常**，设置制作数量和置顶开关，再点击开始。
4. 默认不要同时勾选“家园日常”和“仅一键收获/补餐”，后两项用于单独运行。

## 分辨率与当前限制

识别以 1280×720 为基准，通过 MaaFramework 等比例缩放适配 16:9。当前真机实测为 1920×1080；1280×720、2560×1440 等其他 16:9 分辨率尚未逐一真机验证。非 16:9、黑屏或未知页面会停止输入。

当前烹饪入口基于已观察的家园布局：第一个烹饪锅位于生产建筑第二排第一格，配方第一页可见。其他布局、未解锁家园、餐桌满格等状态尚需更多样本。运行时不要同时操作游戏；输入使用 Seize，会占用鼠标焦点。

自动补种、奇波调度、其他烹饪配方和其他画幅在后续计划中，详见 [模块划分](docs/MODULES.md)。

启动阶段允许在较宽画面中通过文字定位更新和开始按钮；日常任务仍要求 16:9。本地打包器会为 MFAAvalonia 2.16.1 生成绝对启动脚本路径，以兼容其 pretask 工作目录。

家园订单已接入任务列表，支持处理首次结算／财报、核对 Wiki、逐张提交库存足够的订单、滚动检查余下订单。包含 672 条 Wiki 需求；制作分支支持六种商品，以及软木板、木炭、尘石砖、风铜锭中间原料；按设施类型并行排产，按合成依赖收获后继续，详情及验证边界见 [订单开发说明](docs/HOME_ORDERS.md)。运行前需走到看板附近或打开订单页面，当前没有场景寻路模块。出货箱任务暂未启用。

补餐到种植的[数量规划](docs/FOOD_SUPPLY_PLAN.md)以当前缺口为准。种子仓库没有指定数量输入，当前不自动整批或半批补种，以免占用其他作物的田地；按奇波消耗估算每日需求暂缓。

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

已按 CBT3 Wiki 整理[家园资料与商品配方](docs/WIKI_REFERENCE.md)、[后续接入计划](docs/HOME_PREPARATION_PLAN.md)和[数据来源及离线规划用法](docs/DATA_SOURCES.md)。资料准备和规划预览不会操作游戏，尚未接通的自动化能力见计划中的验收项。

采用“识别页面 → 执行操作 → 验证结果”的任务流程。运行库、截图、日志、账号信息与本地配置不进入版本控制。

开发结构参考 [MaaEnd](https://github.com/MaaEnd/MaaEnd) 的模块化任务与状态识别设计；游戏节点根据蓝色星原实际画面重新实现。

## 许可

项目代码遵循 [MIT](LICENSE) 许可。MaaFramework、通用界面及其他依赖的许可归各自项目所有。游戏名称与画面素材归游戏权利人所有。
