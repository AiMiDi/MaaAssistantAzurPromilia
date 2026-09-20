# 配方与图标数据来源

当前游戏版本为 **CBT3**。用户已核对并指定 [蓝色星原 CBT3 Wiki](https://ap-cbt3.csxylic.com/) 为本项目后续物品、配方及相关图标的主要数据来源。站点标注的数据版本为 0.3.0；更换测试版本时需要重新核对。

## 已整理的数据

`assets/resource/data/workbench_goods.json` 包含当前工作台商品页的 7 个配方，以及尘石砖、风铜锭、木炭 3 个相关中间产物。每个条目保留配方 ID、产出物品 ID、材料数量、建筑、基础制作时间、批次上限、解锁条件、原始页面链接与图标 URL。该清单不是全游戏商品全集。

图标地址从原始配方页面读取。另已缓存 22 个商品原始 PNG，位于 `assets/resource/image/wiki_goods/`，来源、尺寸和 SHA-256 记录于 `assets/resource/data/wiki/goods_icons.json`；尚未接入 GUI 或作为经过验证的匹配模板。第三方游戏图标不因引用而变成本项目原创资产。

Wiki 声明其为粉丝制作的非官方站点，游戏素材版权归 ©Manjuu / ©蛮啾网络所有；本项目 MIT 许可不覆盖这些第三方游戏图标。

“可选材料”与固定材料分别保存。包含可选材料的配方标记 `requires_material_choice`，后续规划器必须明确选择后才能计算消耗，不得默认为免费制作或把所有候选同时消耗。当前木炭条目属于这一类。

## 更新方式

在仓库根目录运行：

```powershell
.\.venv\Scripts\python.exe -X utf8 tools/import_goods_wiki.py
```

脚本仅获取清单中的公开配方页并输出结构化事实和图标地址。`--cached` 可从本地 `.cache/recipe_*.html` 重建；页面缺失关键字段时失败，不覆盖已有数据。更新结果应通过 Git diff 审核，不能把网站更新直接变为正在运行任务的新消耗规则。

Wiki 提供静态规则，游戏界面提供账号当前库存、解锁情况、队列和完成结果。基础制作时间不用于直接判定完成，因为实际时间会受奇波效率等因素影响。目标制作执行仍须依据游戏状态验证。

## 家园资料准备包

[资料清单与配方表](WIKI_REFERENCE.md)对应更广范围的只读参考数据；[接入计划](HOME_PREPARATION_PLAN.md)按收获、行情、生产、派驻、孵化与心得拆分下一步工作。

```powershell
# 从已缓存页面重建参考数据；去掉 --offline 时只补取缺失页面
.\.venv\Scripts\python.exe -X utf8 tools/prepare_home_reference.py --offline
# 缓存商品图标，校验 PNG 并生成来源清单
.\.venv\Scripts\python.exe -X utf8 tools/cache_goods_icons.py
# 完全离线预览：目标库存木雕 2；已有木雕 0、木板 6、软木 12
.\.venv\Scripts\python.exe -X utf8 tools/plan_craft.py --target 1200001 --quantity 2 --stock 1200001=0 --stock 350000=6 --stock 300000=12
```

参考数据生成器复用 `.cache` 中的页面，清单时间表示本地整理时间，不表示每页刚刚重新下载。需要刷新时移走对应缓存后重新获取，并审核差异。规划命令不连接游戏；输入的库存是示例，不代表当前账号库存。
