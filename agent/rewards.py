"""Bounded, page-specific reward claims with observed postconditions."""
import re
import time
from pathlib import Path

import numpy as np
from PIL import Image


def green_mask(rgb):
    r,g,b=[rgb[:,:,i].astype('int16') for i in range(3)]
    return ((g-r>35)&(g-b>8)&(g>130)&(b>70)).astype('uint16')


def claimed_tick(image, y, x0=600, x1=778):
    root=Path(__file__).resolve().parents[1]
    base=root/'resource' if (root/'resource').exists() else root/'assets/resource'
    template=green_mask(np.asarray(Image.open(base/'image/common/reward_tick.png').convert('RGB')))
    crop=green_mask(image[max(0,y-35):y+25,x0:x1,::-1])
    if crop.shape[0]<template.shape[0]: return False
    windows=np.lib.stride_tricks.sliding_window_view(crop,template.shape)
    hits=np.einsum('ijxy,xy->ij',windows,template)
    union=windows.sum(axis=(-1,-2))+template.sum()-hits
    return bool((hits/np.maximum(union,1)).max()>=0.70)


def ocr(expected, roi):
    return dict(recognition='OCR', expected=expected, roi=roi)


def read(w, name, image, node):
    w.context.override_pipeline({name:node})
    return w.reco(name, image)


def training(w):
    if not w.reco('EventTrainingPage', w.frame()):
        w.navigate('MenuPage')
        w.act('OpenHandbook')
        w.wait_for(['ActivityPage'])
        w.act('OpenEventTasks')
        w.wait_for(['EventTrainingPage'])
    tabs = w.reco('EventTrainingTabs', w.frame())
    if not tabs:
        raise RuntimeError('未识别到活动天数分页')
    claims = 0
    for tab in tabs.filtered_results:
        x,y,width,height = tab.box
        w.context.override_pipeline({'EventTrainingSelectDay':dict(
            recognition='And',all_of=['SupportedFrame','EventTrainingPage',
                ocr('^'+re.escape(tab.text)+'$', [x-5,y-5,width+10,height+10])],
            action='Click',target=[x+width//2,y+height//2],post_delay=800)})
        w.act('EventTrainingSelectDay')
        w.wait_for(['EventTrainingPage'])
        image = w.frame()
        selected = image[max(0,y-3):y+height+3,max(0,x-6):x+width+6]
        if np.mean(np.min(selected,axis=2)>190) < 0.45:
            raise RuntimeError('未确认活动分页已选中：'+tab.text)
        w.act('EventTrainingScrollUp')
        while True:
            image=w.frame()
            if not w.reco('EventTrainingPage',image):
                raise RuntimeError('活动页面已变化')
            pending=w.reco('EventTrainingClaimText',image)
            if not pending: break
            if claims>=60: raise RuntimeError('活动领取次数超限')
            bx,by,bw,bh=pending.best_result.box
            before_title=read(w,'EventTrainingTaskTitle',image,
                dict(**ocr('.+', [280,by-25,320,45]),order_by='Vertical'))
            if not before_title:
                raise RuntimeError('未识别到活动待领取任务名称')
            title=before_title.best_result.text
            before_total=w.counter('EventTrainingTotal',image)[0]
            w.act('EventTrainingClaim')
            deadline=time.monotonic()+8
            stable=0
            while time.monotonic()<deadline:
                image=w.frame()
                if w.reco('RewardPopup',image):
                    w.act('RewardPopup')
                    continue
                completed=read(w,'EventTrainingCompleted',image,
                    ocr('^已完成$', [bx-10,by-5,bw+25,bh+10]))
                page=w.reco('EventTrainingPage',image)
                changed=False
                if page:
                    after_total=w.counter('EventTrainingTotal',image)[0]
                    old=read(w,'EventTrainingOldTitle',image,ocr('^'+re.escape(title)+'$',[280,200,320,380]))
                    # A single click can claim several rows and immediately reorder the list.
                    changed=after_total>before_total or not old or bool(completed)
                stable=stable+1 if changed else 0
                if stable>=2: break
                time.sleep(0.25)
            else: raise RuntimeError('活动领取后未确认该行已完成或列表/总进度变化')
            claims+=1
            w.log('小小侠客养成记 '+tab.text+'：已确认领取后状态变化')
    w.navigate('MenuPage')
    w.log(f'小小侠客养成记检查完成，确认领取操作 {claims} 次')


def completed_counter(text):
    match=re.search(r'(\d+)\s*/\s*(\d+)',text)
    return bool(match and int(match[2])>0 and int(match[1])>=int(match[2]))


def first_travel_claim(rows, image):
    """The game sorts claimable rows first; never inspect past the first stop row."""
    if not rows or not rows.filtered_results:
        raise RuntimeError('未识别到旅录首行任务，停止操作')
    row = min(rows.filtered_results, key=lambda r: r.box[1])
    if not completed_counter(row.text) or claimed_tick(image, row.box[1]+row.box[3]//2):
        return None
    return row


def travel(w):
    if not w.reco('TripPage',w.frame()):
        w.navigate('MenuPage');w.act('OpenHandbook');w.wait_for(['ActivityPage'])
        w.act('TripOpenEvent');w.act('TripGo');w.wait_for(['TripPage'])
    travel_milestones(w)
    tabs=w.reco('TripTabs',w.frame())
    if not tabs: raise RuntimeError('未识别到旅录分类')
    claims=0
    def stage():
        result=w.reco('TripStage',w.frame())
        if not result: raise RuntimeError('无法确认旅录章节')
        return result.best_result.text
    for tab in tabs.filtered_results:
        x,y,width,height=tab.box
        w.context.override_pipeline({'TripSelectTab':dict(recognition='And',
            all_of=['SupportedFrame','TripPage',ocr('^'+re.escape(tab.text)+'$',[x-5,y-5,width+10,height+10])],
            action='Click',target=[x+width//2,y+height//2],post_delay=1200)})
        w.act('TripSelectTab');w.wait_for(['TripPage'])
        has_chapters=tab.text=='星轨旅录'
        if has_chapters:
            for _ in range(12):
                before=stage();w.act('TripPrevious')
                if stage()==before: break
            else: raise RuntimeError('旅录章节回溯超过上限')
        for chapter in range(15):
            w.act('TripScrollUp')
            while True:
                image=w.frame()
                if not w.reco('TripPage',image): raise RuntimeError('旅录页面已变化')
                rows=w.reco('TripCompletedCounter',image)
                row=first_travel_claim(rows,image)
                if not row: break
                if claims>=80: raise RuntimeError('旅录领取次数超限')
                rx,ry,rw,rh=row.box
                if ry<105 or ry+rh>580: raise RuntimeError('旅录完成条目被裁切')
                node=dict(recognition='And',all_of=['SupportedFrame','TripPage',
                    ocr('^'+re.escape(row.text)+'$',[rx-3,ry-3,rw+6,rh+6])],
                    action='Click',target=[rx+rw//2,ry+rh//2],post_delay=500)
                w.context.override_pipeline({'TripClaimCard':node});w.act('TripClaimCard')
                w.wait_for(['RewardPopup']);w.act('RewardPopup')
                w.wait_for(['TripPage'])
                time.sleep(1.2)
                deadline=time.monotonic()+10;stable=0
                while time.monotonic()<deadline:
                    image=w.frame()
                    old=read(w,'TripOldCard',image,ocr('^'+re.escape(row.text)+'$',[285,105,315,475]))
                    changed=not old or claimed_tick(image,old.best_result.box[1]+old.best_result.box[3]//2)
                    stable=stable+1 if changed and w.reco('TripCompletedCounter',image) else 0
                    if stable>=3: break
                    time.sleep(0.3)
                else: raise RuntimeError('旅录领取后旧任务仍存在，停止重复领取')
                claims+=1;w.log('星之旅录已领取：'+row.text)
            travel_milestones(w)
            if not has_chapters: break
            before=stage();w.act('TripNext')
            if stage()==before: break
        else: raise RuntimeError('旅录章节遍历超过上限')
    travel_milestones(w)
    w.navigate('MenuPage')
    w.log(f'星之旅录任务检查完成，领取 {claims} 项')


def travel_milestones(w):
    for threshold,x in [(50,390),(120,536),(190,682),(220,826),(260,970),(300,1125)]:
        image=w.frame()
        current,cap=w.counter('TripPoints',image)
        if cap!=300: raise RuntimeError('旅录积分上限变化')
        if current<threshold: continue
        if claimed_tick(image,667,x-38,x+38): continue
        w.context.override_pipeline({'TripMilestoneClaim':dict(recognition='And',
            all_of=['SupportedFrame','TripPage','TripPoints'],action='Click',target=[x,663],post_delay=500)})
        w.act('TripMilestoneClaim');w.wait_for(['RewardPopup']);w.act('RewardPopup');w.wait_for(['TripPage'])
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            if claimed_tick(w.frame(),667,x-38,x+38): break
            time.sleep(0.3)
        else: raise RuntimeError('旅录积分奖励领取后未确认勾选标记')
        w.log(f'星之旅录 {threshold} 积分奖励已领取')


def achievement_points(w):
    result = w.reco('AchievementPoints', w.frame())
    match = re.fullmatch(r"\+?(\d+)\s*/\s*(\d+)", result.best_result.text) if result else None
    if not match:
        raise RuntimeError('无法读取成就积分')
    return int(match[1]), int(match[2])


def achievements(w):
    if not w.reco('AchievementPage', w.frame()):
        w.navigate('MenuPage')
        w.act('AchievementOpen')
        w.wait_for(['AchievementPage'])
    for _ in range(10):
        current, target = achievement_points(w)
        if target <= 0:
            raise RuntimeError('成就积分目标无效')
        if current < target:
            w.log(f'成就积分 {current}/{target}，阶段奖励尚未达标')
            break
        w.act('AchievementClaim')
        w.wait_for(['RewardPopup'])
        w.act('RewardPopup')
        w.wait_for(['AchievementPage'])
        after, next_target = achievement_points(w)
        if after >= current and next_target <= target:
            raise RuntimeError('成就阶段奖励领取后进度未变化')
        w.log(f'成就 {target} 积分阶段奖励已领取')
    else:
        raise RuntimeError('成就奖励领取超过上限')
    w.navigate('MenuPage')
