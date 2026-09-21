from types import SimpleNamespace
import pytest
from crafting import load_catalog
from workbench_parallel import plan_many, schedule_wave, run_parallel, production_catalog


def test_furnace_dependencies_expand_before_finished_goods():
    catalog = production_catalog()
    inventory = {'1200017':0, '353000':0, '303000':9, '350006':0, '300000':9}
    steps, skipped = plan_many(catalog, {'1200017':1}, inventory)
    assert not skipped
    assert [(s['name'], s['quantity']) for s in steps] == [('木炭',3),('风铜锭',3),('浮音风铃',1)]
    stations = [{'kind':'工作台'}, {'kind':'熔炉'}, {'kind':'熔炉'}]
    assignments, remaining, reserved = schedule_wave(catalog, steps, inventory, stations)
    assert all(a['station']['kind'] == '熔炉' and a['item_id'] == '350006' for a in assignments)
    assert sum(a['quantity'] for a in assignments) == 3
    assert reserved['300000'] == 0
    assert [s['item_id'] for s in remaining] == ['353000','1200017']


def test_independent_furnace_and_workbench_jobs_share_wave():
    catalog = production_catalog()
    steps = [dict(item_id='350000',quantity=1),dict(item_id='351000',quantity=1)]
    stations = [{'kind':'工作台'}, {'kind':'熔炉'}]
    assignments, remaining, _ = schedule_wave(catalog,steps,{'300000':3,'301000':3},stations)
    assert [a['item_id'] for a in assignments] == ['350000','351000']
    assert not remaining


def test_existing_intermediate_buffer_starts_downstream_with_replenishment():
    catalog = production_catalog()
    inventory = {'1200001':0, '350000':6, '300000':42}
    steps, skipped = plan_many(catalog, {'1200001':4}, inventory)
    assert not skipped
    assignments, remaining, reserved = schedule_wave(catalog, steps, inventory, ['A','B'])
    assert [(a['item_id'], a['quantity']) for a in assignments] == [('1200001',1),('350000',14)]
    assert reserved['350000'] == 1  # Only actual stock, not the 14 unfinished boards.
    assert [(s['item_id'],s['quantity']) for s in remaining] == [('1200001',3)]


def test_parallel_wave_reserves_shared_inputs_and_splits_batches():
    catalog = load_catalog()
    steps = [dict(item_id='1200001', quantity=4)]
    assignments, remaining, reserved = schedule_wave(catalog, steps, {'350000':20}, ['A','B'])
    assert [a['quantity'] for a in assignments] == [2,2]
    assert reserved['350000'] == 0
    assert remaining == []
    assert steps[0]['quantity'] == 4


def test_dependencies_wait_until_next_wave():
    catalog = load_catalog()
    steps = [dict(item_id='350000',quantity=5),dict(item_id='1200001',quantity=1)]
    assignments, remaining, reserved = schedule_wave(catalog,steps,{'300000':15,'350000':0},['A','B'])
    assert all(a['item_id']=='350000' for a in assignments)
    assert any(s['item_id']=='1200001' for s in remaining)
    assert reserved['350000']==0


def test_multiple_recipes_do_not_double_reserve_raw_material():
    catalog = {k:v for k,v in load_catalog().items() if k in ('350000','1200001','1200027')}
    steps, skipped = plan_many(catalog,{'1200001':1,'1200027':1},
                              {'1200001':0,'350000':0,'300000':15,'1200027':0,'302025':5})
    assert '1200027' in skipped
    assert [s['item_id'] for s in steps] == ['350000','1200001']


class FakeUI:
    def __init__(self, state='idle', boards=20, carvings=0):
        self.inventory={'1200001':carvings,'350000':boards,'300000':100}
        self.selected=None
        self.events=[]
        self.pending=[]
        self.initial_state=state
    def discover(self): return ['A','B']
    def open(self,station): pass
    def state(self): return self.initial_state
    def select(self,item): self.selected=item;return True
    def owned(self): return self.inventory[self.selected]
    def materials(self,recipe,quantity=1):
        return {m['item_id']:self.inventory[m['item_id']] for m in recipe['ingredients']}
    def start(self,a,catalog):
        self.events.append(('start',a['station']))
        self.pending.append(a)
    def wait(self,station,quantity): self.events.append(('wait',station))
    def collect(self):
        catalog=load_catalog()
        for a in self.pending:
            for m in catalog[a['item_id']]['ingredients']:
                self.inventory[m['item_id']]-=m['quantity']*a['quantity']
            self.inventory[a['item_id']]+=a['quantity']
        self.pending=[]


def run_fake(monkeypatch, ui, **policy):
    monkeypatch.setattr('workbench_parallel.WorkbenchUI',lambda w:ui)
    w=SimpleNamespace(log=lambda s:None,collect=ui.collect)
    run_parallel(w,dict(item_id='1200001',quantity=4,**policy))


def test_dispatches_all_stations_before_waiting(monkeypatch):
    ui=FakeUI()
    run_fake(monkeypatch,ui,execute=True)
    assert ui.events == [('start','A'),('start','B'),('wait','A'),('wait','B')]
    assert ui.inventory['1200001']==4


def test_preview_never_starts_production(monkeypatch):
    ui=FakeUI()
    run_fake(monkeypatch,ui,execute=False)
    assert not ui.events


def test_workbench_keeps_existing_queue(monkeypatch):
    ui=FakeUI(state='busy')
    with pytest.raises(RuntimeError,match='已有未完成队列'):
        run_fake(monkeypatch,ui,execute=True)
    assert not ui.events


def test_satisfied_target_does_not_craft_again(monkeypatch):
    ui=FakeUI(carvings=4)
    run_fake(monkeypatch,ui,execute=True)
    assert not ui.events


def test_existing_buffer_usable_without_intermediate_recipe(monkeypatch):
    ui=FakeUI(boards=20)
    select=ui.select
    ui.select=lambda item: False if item=='350000' else select(item)
    run_fake(monkeypatch,ui,execute=True)
    assert ui.inventory['1200001']==4
