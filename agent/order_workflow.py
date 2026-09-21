"""Order board execution with per-card Wiki validation and fresh stock checks."""
import json
from pathlib import Path
import re
import time
from datetime import datetime

import numpy as np

from orders import load_orders, assess_order
from workflows import parse_counter


def ocr(text, roi, **extra):
    return dict(recognition='OCR', expected=text, roi=roi, **extra)


def read(workflow, image, node, override):
    result = workflow.context.run_recognition(node, image, {node: override})
    return result if result and result.hit else None


def save_forecast(workflow):
    image = workflow.frame()
    result = read(workflow, image, 'OrderTomorrow', ocr('.+', [475,420,640,50]))
    if not result:
        raise RuntimeError('无法读取明日预告，保留财报页')
    text = ' '.join(r.text for r in result.filtered_results)
    root = Path(__file__).resolve().parents[1]
    output = root / 'debug/market_forecast.json'
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps({'observed_at': datetime.now().astimezone().isoformat(),
                                 'tomorrow_text': text, 'price_verified': False},
                                ensure_ascii=False, indent=2), encoding='utf-8')
    workflow.log('已记录明日备货预告：' + text)


def open_board(workflow):
    for _ in range(7):
        image = workflow.frame()
        if workflow.reco('OrderBoardPage', image):
            return
        if workflow.reco('OrderSettlement', image):
            workflow.act('OrderSettlementConfirm')
        elif workflow.reco('OrderNews', image):
            save_forecast(workflow)
            workflow.act('OrderNewsClose')
        elif workflow.reco('OrderMerchantPage', image):
            workflow.act('OrderSelectBoard')
        elif workflow.reco('OrderNearby', image):
            workflow.act('OrderOpen')
        else:
            raise RuntimeError('请先走到看板旁，出现 F 订单看板，或打开订单页面')
    raise RuntimeError('订单入口状态重复出现，已停止')


def card_read(workflow, image, title, catalog):
    x, y, width, height = title.box
    # Each card's counter and button are below its title. Skip clipped cards.
    if y < 155 or y + 185 > 625:
        return None
    center = x + width // 2
    counter_roi = [center - 52, y + 87, 104, 32]
    counter = read(workflow, image, 'OrderCardCounter',
                   ocr(r'^\d+\s*/\s*\d+$', counter_roi))
    if not counter:
        raise RuntimeError('订单数量未识别：' + title.text)
    values = parse_counter(counter.best_result.text)
    if values is None or values[1] <= 0:
        raise RuntimeError('订单数量不可靠：' + title.text)
    available, amount = values
    variants = [r for r in catalog if r['name'] == title.text and len(r['materials']) == 1
                and r['materials'][0]['quantity'] == amount]
    items = {r['materials'][0]['item_id'] for r in variants}
    if len(items) != 1:
        raise RuntimeError('订单名称或需求与 Wiki 不符：' + title.text)
    item = next(iter(items))
    decision = assess_order(catalog, title.text, {item: amount}, {item: available})
    title_roi = [x - 8, y - 5, width + 16, height + 10]
    button_roi = [center - 82, y + 139, 165, 44]
    return dict(name=title.text, item_id=item, available=available, quantity=amount,
                ready=decision['ready'], title_roi=title_roi, counter_roi=counter_roi,
                button_roi=button_roi)


def submit(workflow, card):
    image = workflow.frame()
    before = read(workflow, image, 'OrderCoins', ocr(r'^\d+$', [1145,23,100,28]))
    if not before:
        raise RuntimeError('无法读取提交前硬币数量')
    before = int(before.best_result.text)
    # Re-recognize exact card, current stock and submit button immediately before input.
    node = dict(recognition='And', all_of=['SupportedFrame', 'OrderBoardPage',
                ocr('^' + re.escape(card['name']) + '$', card['title_roi']),
                ocr(r'^' + str(card['available']) + r'\s*/\s*' + str(card['quantity']) + '$', card['counter_roi']),
                ocr('^提交订单$', card['button_roi'])], box_index=4,
                action='Click', target=True, post_delay=1000)
    workflow.context.override_pipeline({'OrderCardSubmit': node})
    workflow.act('OrderCardSubmit')
    deadline = time.monotonic() + 8
    stable = 0
    while time.monotonic() < deadline:
        image = workflow.frame()
        if workflow.reco('RewardPopup', image):
            workflow.act('RewardPopup')
            continue
        gone = not read(workflow, image, 'OrderCardTitle',
                        ocr('^' + re.escape(card['name']) + '$', card['title_roi']))
        coins = read(workflow, image, 'OrderCoins', ocr(r'^\d+$', [1145,23,100,28]))
        stable = stable + 1 if gone and coins and int(coins.best_result.text) > before else 0
        if stable >= 2:
            workflow.log(f"订单已提交：{card['name']} ×{card['quantity']}；硬币 {before} → {coins.best_result.text}")
            return
        time.sleep(0.25)
    raise RuntimeError('提交后未确认订单消失和硬币增加，停止重复提交')


def replenish(workflow, missing):
    from crafting import load_catalog
    from workbench import NODES, run_target
    recipes = load_catalog()
    candidates = {}
    for card in missing:
        item = card['item_id']
        if item in NODES:
            candidates[item] = max(candidates.get(item, 0), card['quantity'])
        elif item in recipes:
            workflow.log('该材料有 Wiki 配方，但制作入口尚未适配：' + recipes[item]['name'])
        else:
            workflow.log('无法在已适配制作流程中补足：' + card['name'])
    if not candidates:
        return False
    # Menus do not move the character; returning to the scene preserves board proximity.
    workflow.act('OrderClose')
    for item, quantity in candidates.items():
        workflow.log(f'为订单补足 {recipes[item]["name"]}，目标库存 {quantity}')
        run_target(workflow, {'item_id': item, 'quantity': quantity, 'execute': True})
    workflow.navigate('MenuPage')
    workflow.act('CloseMenuToScene')
    workflow.wait_for(['OrderNearby'])
    return True


def run_orders(workflow, craft=True, round_index=0):
    catalog = load_orders()
    names = sorted({row['name'] for row in catalog})
    title_node = ocr('^(?:' + '|'.join(re.escape(x) for x in names) + ')$', [415,155,820,460])
    open_board(workflow)
    workflow.act('OrderScrollUp')
    submitted = 0
    missing = {}
    scrolls = 0
    while True:
        image = workflow.frame()
        if not workflow.reco('OrderBoardPage', image):
            raise RuntimeError('订单页面已变化')
        titles = read(workflow, image, 'OrderCardTitle', title_node)
        cards = []
        for title in titles.filtered_results if titles else []:
            card = card_read(workflow, image, title, catalog)
            if card:
                cards.append(card)
        ready = next((c for c in cards if c['ready']), None)
        if ready:
            if submitted >= 20:
                raise RuntimeError('订单提交次数超限')
            submit(workflow, ready)
            submitted += 1
            continue  # Stocks of all remaining cards may change after consuming materials.
        for card in cards:
            missing[card['name']] = card
        before = image[170:600,420:1225].copy()
        workflow.act('OrderScrollDown')
        after = workflow.frame()[170:600,420:1225]
        scrolls += 1
        if np.abs(before.astype(float) - after.astype(float)).mean() < 0.8:
            break
        if scrolls >= 8:
            raise RuntimeError('订单列表未确认底部，停止滚动')
    for card in missing.values():
        workflow.log(f"待补材料：{card['name']}，已有 {card['available']}/{card['quantity']}，缺 {card['quantity'] - card['available']}")
    if craft and missing:
        if round_index >= 5:
            raise RuntimeError('订单制作轮次超限，保留剩余订单')
        if replenish(workflow, list(missing.values())):
            return run_orders(workflow, craft=True, round_index=round_index + 1)
    workflow.log(f'订单检查完成，本轮提交 {submitted} 项')
    return list(missing.values())
