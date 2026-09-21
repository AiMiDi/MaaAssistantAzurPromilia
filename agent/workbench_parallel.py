"""Plan small stock targets and dispatch independent batches to idle workbenches."""
import math
import re
import time

from crafting import load_catalog, plan_target

NODES = {'350000': 'SoftwoodBoard', '1200001': 'ChickCarving',
         '1200002': 'WolfFigurine', '1200017': 'WindChime',
         '1200027': 'InscribedRing', '1200029': 'CrystalBall', '1200030': 'SoftScarf'}
GOODS = tuple(item for item in NODES if item != '350000')
NODES.update({'351000':'StoneBrick','353000':'CopperIngot','350006':'Charcoal'})

def production_catalog():
    catalog = load_catalog()
    # CBT3 in-game material selector: explicitly choose softwood, never guess fuel.
    catalog['350006'] = dict(catalog['350006'], ingredients=[dict(item_id='300000', name='软木', quantity=3)], requires_material_choice=False)
    return catalog


def plan_many(catalog, targets, inventory):
    simulated = inventory.copy()
    steps, skipped = [], {}
    for item, quantity in targets.items():
        plan = plan_target(catalog, item, quantity, simulated)
        if not plan['ready']:
            skipped[item] = plan
            continue
        for step in plan['steps']:
            recipe = catalog[step['item_id']]
            for material in recipe['ingredients']:
                simulated[material['item_id']] -= material['quantity'] * step['quantity']
            simulated[step['item_id']] += step['quantity']
            steps.append(step.copy())
    return steps, skipped


def schedule_wave(catalog, steps, inventory, stations):
    """Reserve inputs per station. Unfinished output is never available in this wave."""
    available = inventory.copy()
    remaining = [step.copy() for step in steps]
    assignments = []
    for index, station in enumerate(stations):
        # Downstream work can consume existing buffers while other stations replenish.
        for step in reversed(remaining):
            if step['quantity'] <= 0:
                continue
            recipe = catalog[step['item_id']]
            if isinstance(station, dict) and station['kind'] != recipe['station']:
                continue
            possible = min(available.get(m['item_id'], 0) // m['quantity'] for m in recipe['ingredients'])
            # Balance a large batch across the idle stations; one-item jobs occupy one.
            quantity = min(step['quantity'], possible, recipe['max_batch'],
                           math.ceil(step['quantity'] / (len(stations) - index)))
            if quantity <= 0:
                continue
            assignments.append(dict(station=station, item_id=step['item_id'], quantity=quantity))
            step['quantity'] -= quantity
            for material in recipe['ingredients']:
                available[material['item_id']] -= material['quantity'] * quantity
            break
    return assignments, [s for s in remaining if s['quantity'] > 0], available


class WorkbenchUI:
    def __init__(self, workflow):
        self.w = workflow
        self.current_station = None

    def buildings(self):
        self.current_station = None
        if self.w.reco('ProductionPage', self.w.frame()):
            self.w.act('ProductionClose')
            self.w.wait_for(['HomeBuildingsPage'])

        if not self.w.reco('HomeBuildingsPage', self.w.frame()):
            self.w.navigate('HomeCorePage')
            self.w.act('HomeOpenBuildings')
            self.w.wait_for(['HomeBuildingsPage'])
        self.w.act('ProductionBuildingsTop')

    def discover(self):
        self.buildings()
        result = self.w.reco('ProductionBuildings', self.w.frame())
        boxes = sorted([dict(kind=row.text, box=list(row.box)) for row in result.filtered_results], key=lambda b: (b['box'][1], b['box'][0])) if result else []
        if not boxes:
            raise RuntimeError('当前建筑页没有识别到工作台')
        return boxes

    def open(self, station):
        expected_page = 'WorkbenchPage' if station['kind'] == '工作台' else 'FurnacePage'
        if self.current_station == station and self.w.reco(expected_page, self.w.frame()):
            return
        self.buildings()
        x, y, width, height = station['box']
        kind = station['kind']
        if y > 500:
            before = self.w.reco('ProductionAnchors', self.w.frame())
            self.w.act('ProductionBuildingsDown')
            after = self.w.reco('ProductionAnchors', self.w.frame())
            shifts = []
            for left in before.filtered_results if before else []:
                for right in after.filtered_results if after else []:
                    if left.text == right.text and abs(left.box[0]-right.box[0]) < 10:
                        shifts.append(right.box[1]-left.box[1])
            if len(shifts) < 2 or max(shifts)-min(shifts) > 5:
                raise RuntimeError('无法通过建筑编号确认滚动位置')
            y += round(sum(shifts)/len(shifts))
        node = dict(recognition='And', all_of=['SupportedFrame', 'HomeBuildingsPage',
                    dict(recognition='Or', any_of=[
                        dict(recognition='OCR', expected='^'+kind+'$', roi=[x-8,y-5,width+16,height+10]),
                        dict(recognition='OCR', expected='待收取|工作中', roi=[x-20,y+65,160,65])])],
                    action='Click', target=[x+width//2+50,y+height//2+65], post_delay=700)
        self.w.context.override_pipeline({'WorkbenchOpenSelected': node})
        self.w.act('WorkbenchOpenSelected')
        self.w.wait_for(['WorkbenchPage' if kind == '工作台' else 'FurnacePage'])
        if kind == '工作台': self.w.act('WorkbenchTabGoods')
        self.current_station = station

    def state(self):
        image = self.w.frame()
        if self.w.reco('ProductionDone', image): return 'done'
        if self.w.reco('ProductionIdle', image): return 'idle'
        if self.w.reco('ProductionQueue', image): return 'busy'
        raise RuntimeError('工作台首个槽位状态不明')

    def select(self, item):
        node = 'WorkbenchSelect' + NODES[item]
        if not self.w.reco(node, self.w.frame()):
            return False
        self.w.act(node)
        self.w.wait_for(['WorkbenchSelected' + NODES[item]])
        self.w.act('ProductionMin')
        if item == '350006':
            self.w.act('FuelChoiceOpen')
            self.w.wait_for(['FuelChoicePage'])
            self.w.act('FuelSelectSoftwood')
            self.w.act('FuelChoiceConfirm')
            self.w.wait_for(['FurnacePage'])
        return True

    def owned(self):
        result = self.w.reco('ProductionOwned', self.w.frame())
        match = re.fullmatch(r'拥有数量\s*[:：]?\s*(\d+)', result.best_result.text if result else '')
        if not match: raise RuntimeError('无法读取工作台库存')
        return int(match.group(1))

    def materials(self, recipe, quantity=1):
        if recipe.get('requires_material_choice') or not 1 <= len(recipe['ingredients']) <= 2:
            raise RuntimeError('工作台材料布局尚未适配')
        result = {}
        for index, material in enumerate(recipe['ingredients']):
            stock, cost = self.w.counter('ProductionMaterial' + ('2' if index else ''))
            if cost != material['quantity'] * quantity:
                raise RuntimeError('材料数量与 Wiki 不一致：' + material['name'])
            result[material['item_id']] = stock
        return result

    def start(self, assignment, catalog):
        self.open(assignment['station'])
        if self.state() != 'idle':
            raise RuntimeError('工作台已有队列，保留队列')
        item, quantity = assignment['item_id'], assignment['quantity']
        if not self.select(item): raise RuntimeError('配方不在当前工作台可见列表')
        for _ in range(quantity - 1): self.w.act('ProductionPlus')
        materials = self.materials(catalog[item], quantity)
        if any(materials[m['item_id']] < m['quantity'] * quantity for m in catalog[item]['ingredients']):
            raise RuntimeError('分配后材料库存变化，未开始当前批次')
        self.w.act('ProductionStart')
        self.w.wait_for(['ProductionQueue', 'ProductionDone'])

    def wait(self, station, quantity):
        self.open(station)
        deadline = time.monotonic() + 240
        unreadable = 0
        while time.monotonic() < deadline:
            image = self.w.frame()
            if self.w.reco('ProductionDone', image): return
            try:
                completed, total = self.w.counter('ProductionQueue', image)
                unreadable = 0
                if total != quantity: raise ValueError('队列总数与本轮分配不一致')
                if completed == total: return
            except RuntimeError:
                unreadable += 1
                if unreadable >= 5: raise RuntimeError('无法确认队列状态，保留已排入的制作')
            time.sleep(0.5)
        raise TimeoutError('工作台仍在制作，保留已有队列')


def run_parallel(workflow, policy):
    quantity = int(policy.get('quantity', 1))
    if not 1 <= quantity <= 300: raise ValueError('目标库存应为1～300')
    selected = policy.get('item_id', '1200001')
    requested = list(GOODS) if selected == 'all' else [str(selected)]
    if any(item not in NODES for item in requested): raise ValueError('未知工作台配方')
    execute = policy.get('execute', False) is True
    ui = WorkbenchUI(workflow)
    stations = ui.discover()
    workflow.log(f'识别到 {len(stations)} 座可识别生产设施')
    states = []
    for station in stations:
        ui.open(station)
        states.append(ui.state())
    if 'busy' in states:
        raise RuntimeError('已有未完成队列，无法确认其成品是否计入目标；保留队列，收获后重试')
    if 'done' in states:
        if not execute:
            workflow.log('工作台有待收获成品，预览前请先收获；未重复安排')
            return
        workflow.collect()
    catalog = {item: recipe for item, recipe in production_catalog().items() if item in NODES}
    def open_recipe_station(item):
        matching = [s for s in stations if not isinstance(s, dict) or s['kind'] == catalog[item]['station']]
        if not matching: return False
        ui.open(matching[0])
        return True
    inventory, targets, inspected = {}, {}, set()
    def update(item, count):
        if item in inventory and inventory[item] != count:
            raise RuntimeError('读取期间材料库存不一致：' + item)
        inventory[item] = count
    def inspect(item):
        if item in inspected: return True
        if item not in catalog: return False
        if not open_recipe_station(item) or not ui.select(item): return False
        inspected.add(item)
        update(item, ui.owned())
        for material, stock in ui.materials(catalog[item]).items(): update(material, stock)
        for material in catalog[item]['ingredients']:
            dependency = material['item_id']
            if dependency in NODES and not inspect(dependency):
                # Existing stock remains usable even when its producing facility is absent.
                catalog.pop(dependency, None)
                workflow.log('中间材料制作入口不可用，仅使用已读取库存：' + material['name'])
        return True
    for item in requested:
        if inspect(item): targets[item] = quantity
        else: workflow.log('配方未解锁或不在当前可见列表，跳过：' + catalog[item]['name'])
    steps, skipped = plan_many(catalog, targets, inventory)
    material_names = {m['item_id']:m['name'] for r in catalog.values() for m in r['ingredients']}
    for item, plan in skipped.items():
        detail = '、'.join(f"{material_names.get(key,key)} ×{value}" for key,value in plan['shortages'].items())
        if plan['unknown_inventory']:
            detail += ' 未知库存：' + '、'.join(material_names.get(key,key) for key in plan['unknown_inventory'])
        workflow.log('材料不足，跳过 ' + catalog[item]['name'] + '：' + detail)
    if not steps:
        workflow.log('没有需要新增且材料足够的商品')
        return
    workflow.log('计划：' + ' → '.join(f"{s['name']} ×{s['quantity']}" for s in steps))
    if not execute:
        workflow.log('仅预览，未开始制作')
        return
    waves = 0
    while steps:
        assignments, remaining, reserved = schedule_wave(catalog, steps, inventory, stations)
        if not assignments or waves >= 30: raise RuntimeError('无法继续分配生产任务')
        for assignment in assignments:
            ui.start(assignment, catalog)
            workflow.log(f"生产设施{stations.index(assignment['station'])+1}已排入：{catalog[assignment['item_id']]['name']} ×{assignment['quantity']}")
        # All starts precede all waits: independent workbenches can produce concurrently.
        for assignment in assignments: ui.wait(assignment['station'], assignment['quantity'])
        workflow.collect()
        expected = reserved.copy()
        for assignment in assignments:
            item = assignment['item_id']
            expected[item] = expected.get(item, 0) + assignment['quantity']
        for item in dict.fromkeys(a['item_id'] for a in assignments):
            open_recipe_station(item)
            if not ui.select(item): raise RuntimeError('收获后未找到配方')
            actual = ui.owned()
            if actual < expected[item]: raise RuntimeError('收获后成品数量没有达到本轮预期')
            expected[item] = actual
            workflow.log(f'已验证收获：{catalog[item]["name"]}，当前库存 {actual}')
        inventory, steps = expected, remaining
        waves += 1
    workflow.log('本轮可制作商品已完成；不足材料的商品已报告并跳过')
