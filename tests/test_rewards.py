from types import SimpleNamespace

import numpy as np
import pytest

from rewards import training, completed_counter, claimed_tick, first_travel_claim, travel_milestones
from pathlib import Path
from PIL import Image


class TrainingHarness:
    def __init__(self, pending=True, confirms=True):
        self.context=SimpleNamespace(override_pipeline=lambda _:None)
        self.pending=pending
        self.confirms=confirms
        self.claimed=False
        self.actions=[]
        self.image=np.full((720,1280,3),255,dtype=np.uint8)
    def frame(self): return self.image
    def reco(self,node,image):
        if node=='EventTrainingPage': return True
        if node=='EventTrainingTabs':
            return SimpleNamespace(filtered_results=[SimpleNamespace(text='第1天',box=[300,150,40,20]),SimpleNamespace(text='第2天',box=[400,150,40,20])])
        if node=='EventTrainingClaimText' and self.pending:
            return SimpleNamespace(best_result=SimpleNamespace(box=[820,330,30,20]))
        if node=='EventTrainingCompleted': return self.claimed and self.confirms
        if node in ('EventTrainingTaskTitle','EventTrainingOldTitle'):
            return SimpleNamespace(best_result=SimpleNamespace(text='任务名称'))
    def act(self,node):
        self.actions.append(node)
        if node=='EventTrainingClaim': self.pending=False;self.claimed=True
    def counter(self,*args): return (19,35)
    def wait_for(self,*args): pass
    def navigate(self,*args): pass
    def log(self,*args): pass


def test_training_claim_verifies_result_and_checks_other_days(monkeypatch):
    monkeypatch.setattr('rewards.time.sleep',lambda _:None)
    w=TrainingHarness()
    training(w)
    assert w.actions.count('EventTrainingClaim')==1
    assert w.actions.count('EventTrainingSelectDay')==2
    assert 'EventTrainingScrollDown' not in w.actions


def test_training_empty_does_not_click_claim():
    w=TrainingHarness(pending=False)
    training(w)
    assert 'EventTrainingClaim' not in w.actions


def test_training_refuses_to_repeat_unverified_claim(monkeypatch):
    clock=iter(range(100))
    monkeypatch.setattr('rewards.time.monotonic',lambda:next(clock))
    monkeypatch.setattr('rewards.time.sleep',lambda _:None)
    w=TrainingHarness(confirms=False)
    with pytest.raises(RuntimeError,match='未确认该行'):
        training(w)
    assert w.actions.count('EventTrainingClaim')==1


def test_training_does_not_claim_from_unselected_tab():
    w=TrainingHarness()
    w.image[:]=0
    with pytest.raises(RuntimeError,match='未确认活动分页'):
        training(w)
    assert 'EventTrainingClaim' not in w.actions


@pytest.mark.parametrize('text,ready',[('2/3',False),('7/7',True),('0/0',False),('完成订单(2/2)',True),('进行中',False)])
def test_completed_counter_requires_nonzero_target(text,ready):
    assert completed_counter(text)==ready


def test_claimed_tick_detects_checkmark_but_not_plain_green_icon():
    image=np.zeros((720,1280,3),dtype=np.uint8)
    icon=np.asarray(Image.open(Path(__file__).resolve().parents[1]/'assets/resource/image/common/reward_tick.png').convert('RGB'))[:,:,::-1]
    image[260:280,640:664]=icon
    assert claimed_tick(image,270)
    image[260:280,640:664]=[120,220,20]
    assert not claimed_tick(image,270)


@pytest.mark.parametrize('first_text,ticked', [('任务(1/2)', False), ('任务(2/2)', True)])
def test_sorted_travel_stops_at_first_unfinished_or_claimed_row(monkeypatch,first_text,ticked):
    monkeypatch.setattr('rewards.claimed_tick',lambda *args:ticked)
    rows=SimpleNamespace(filtered_results=[SimpleNamespace(text='后面的已完成(3/3)',box=[300,300,150,20]),SimpleNamespace(text=first_text,box=[300,140,150,20])])
    assert first_travel_claim(rows,None) is None


def test_travel_selects_only_first_available_then_refreshes(monkeypatch):
    monkeypatch.setattr('rewards.claimed_tick',lambda *args:False)
    first=SimpleNamespace(text='可领取(2/2)',box=[300,140,150,20])
    rows=SimpleNamespace(filtered_results=[first,SimpleNamespace(text='未完成(1/2)',box=[300,300,150,20])])
    assert first_travel_claim(rows,None) is first
    rows.filtered_results.pop(0)
    assert first_travel_claim(rows,None) is None


def test_travel_unknown_rows_fail_closed():
    with pytest.raises(RuntimeError,match='首行任务'):
        first_travel_claim(None,None)


def test_travel_claims_eligible_milestone_even_with_no_task_rewards(monkeypatch):
    claimed={390,536}
    w=SimpleNamespace(frame=lambda:None,counter=lambda *args:(190,300),wait_for=lambda *args:None,log=lambda *args:None)
    targets=[]
    def override(nodes): targets.append(nodes['TripMilestoneClaim']['target'][0])
    def act(node):
        if node=='TripMilestoneClaim': claimed.add(targets[-1])
    w.context=SimpleNamespace(override_pipeline=override)
    w.act=act
    monkeypatch.setattr('rewards.claimed_tick',lambda image,y,x0,x1:(x0+x1)//2 in claimed)
    travel_milestones(w)
    assert targets==[682]
    travel_milestones(w)
    assert targets==[682]


@pytest.mark.parametrize('before,after,expected', [((135,200),None,0),((200,200),(200,300),1)])
def test_achievement_milestone_claims_only_when_reached(monkeypatch,before,after,expected):
    from rewards import achievements
    values=iter([before]+([after,after] if after else []))
    monkeypatch.setattr('rewards.achievement_points',lambda w:next(values))
    actions=[]
    w=SimpleNamespace(frame=lambda:None,reco=lambda *args:True,act=actions.append,wait_for=lambda *args:None,navigate=lambda *args:None,log=lambda *args:None)
    achievements(w)
    assert actions.count('AchievementClaim')==expected


def test_achievement_refuses_repeated_claim_when_progress_does_not_change(monkeypatch):
    from rewards import achievements
    monkeypatch.setattr('rewards.achievement_points',lambda w:(200,200))
    actions=[]
    w=SimpleNamespace(frame=lambda:None,reco=lambda *args:True,act=actions.append,wait_for=lambda *args:None,navigate=lambda *args:None,log=lambda *args:None)
    with pytest.raises(RuntimeError,match='进度未变化'):
        achievements(w)
    assert actions.count('AchievementClaim')==1


def test_travel_checks_milestones_even_when_first_task_is_unfinished(monkeypatch):
    from rewards import travel
    events=[]
    def reco(node,image):
        if node=='TripPage':return True
        if node=='TripTabs':return SimpleNamespace(filtered_results=[SimpleNamespace(text='大冒险家',box=[130,240,110,30])])
        if node=='TripCompletedCounter':
            events.append('task')
            return SimpleNamespace(filtered_results=[SimpleNamespace(text='宝箱(1/10)',box=[300,110,180,20])])
    monkeypatch.setattr('rewards.travel_milestones',lambda w:events.append('milestone'))
    actions=[]
    w=SimpleNamespace(frame=lambda:None,reco=reco,act=actions.append,context=SimpleNamespace(override_pipeline=lambda _:None),wait_for=lambda *args:None,navigate=lambda *args:None,log=lambda *args:None)
    travel(w)
    assert events[0]=='milestone'
    assert events[-1]=='milestone'
    assert 'task' in events
    assert 'TripScrollDown' not in actions
    assert 'TripClaimCard' not in actions


def test_training_accepts_batch_claim_that_reorders_instead_of_marking_same_row(monkeypatch):
    monkeypatch.setattr('rewards.time.sleep',lambda _:None)
    w=TrainingHarness(confirms=False)
    w.counter=lambda *args:(21 if w.claimed else 19,35)
    training(w)
    assert w.actions.count('EventTrainingClaim')==1
    assert 'EventTrainingScrollDown' not in w.actions


@pytest.mark.parametrize('status', ['前往','进行中','已领取'])
def test_pass_sorted_status_returns_first_card(monkeypatch,status):
    from rewards import pass_first_status
    first=SimpleNamespace(text=status,box=[210,560,40,20])
    result=SimpleNamespace(filtered_results=[SimpleNamespace(text='领取',box=[350,560,40,20]),first])
    w=SimpleNamespace(reco=lambda *args:result)
    assert pass_first_status(w,None) is first


def test_pass_refuses_missing_first_card():
    from rewards import pass_first_status
    result=SimpleNamespace(filtered_results=[SimpleNamespace(text='领取',box=[350,560,40,20])])
    with pytest.raises(RuntimeError,match='首张任务卡不可见'):
        pass_first_status(SimpleNamespace(reco=lambda *args:result),None)


def test_pass_level_claim_verifies_disappearing_button():
    from rewards import pass_level_rewards
    actions=[]
    claimed=False
    def act(node):
        nonlocal claimed
        actions.append(node)
        if node=='PassClaimAll':claimed=True
    w=SimpleNamespace(frame=lambda:None,act=act,reco=lambda node,image: not claimed if node=='PassClaimAll' else True,wait_for=lambda *args:None,log=lambda *args:None)
    pass_level_rewards(w)
    pass_level_rewards(w)
    assert actions.count('PassClaimAll')==1
    assert actions.count('RewardPopup')==1


def test_pass_no_task_rewards_still_checks_levels_before_and_after(monkeypatch):
    from rewards import travelogue
    events=[]
    image=np.full((720,1280,3),[220,150,80],dtype=np.uint8)
    first=SimpleNamespace(text='进行中',box=[210,560,40,20])
    monkeypatch.setattr('rewards.pass_level_rewards',lambda w:events.append('levels'))
    w=SimpleNamespace(frame=lambda:image,reco=lambda node,image:SimpleNamespace(filtered_results=[first]) if node=='PassTaskStatus' else True,act=events.append,wait_for=lambda *args:None,navigate=lambda *args:None,log=lambda *args:None)
    travelogue(w)
    assert events[0]==events[-1]=='levels'
    assert all(node in events for node in ['PassDaily','PassWeekly','PassPeriod'])
    assert 'PassClaimTask' not in events


@pytest.mark.parametrize('confirmed',[True,False])
def test_pass_task_claim_requires_progress_before_retry(monkeypatch,confirmed):
    from rewards import travelogue
    clock=iter(range(1000))
    monkeypatch.setattr('rewards.time.monotonic',lambda:next(clock))
    monkeypatch.setattr('rewards.time.sleep',lambda _:None)
    monkeypatch.setattr('rewards.pass_level_rewards',lambda _:None)
    actions=[]
    selected='PassDaily'
    claimed=False
    image=np.full((720,1280,3),[220,150,80],dtype=np.uint8)
    def act(node):
        nonlocal selected,claimed
        actions.append(node)
        if node in ('PassDaily','PassWeekly','PassPeriod'):selected=node
        if node=='PassClaimTask':claimed=True
    def reco(node,image):
        if node=='RewardPopup':return None
        if node=='PassTaskStatus':
            status='领取' if selected=='PassDaily' and not (confirmed and claimed) else '前往'
            return SimpleNamespace(filtered_results=[SimpleNamespace(text=status,box=[210,560,40,20])])
        return True
    monkeypatch.setattr('rewards.pass_progress',lambda *args:(14,400 if claimed and confirmed else 100))
    w=SimpleNamespace(frame=lambda:image,reco=reco,act=act,context=SimpleNamespace(override_pipeline=lambda _:None),wait_for=lambda *args:None,navigate=lambda *args:None,log=lambda *args:None)
    if confirmed:travelogue(w)
    else:
        with pytest.raises(RuntimeError,match='停止重复点击'):travelogue(w)
    assert actions.count('PassClaimTask')==1
