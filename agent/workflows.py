"""Verified UI steps with bounded navigation and explicit result checks.

Recognition and input live in pipeline JSON. This agent only orders steps,
reads counters, and reports branches that cannot be expressed as a fixed chain.
"""
import json
import re
import time

from maa.custom_action import CustomAction
from maa.custom_recognition import CustomRecognition
from window import game_on_top


def supported_frame(image):
    return bool(image is not None and image.shape[:2] == (720, 1280) and image.std() >= 3)


def parse_counter(text):
    match = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", text)
    return tuple(map(int, match.groups())) if match else None


RECIPES = {
    "Cookie": ("小份波波饼", "HomeCookingChooseCookie", "HomeCookingCookie"),
}


def recipe_order(policy):
    # Feeding is deliberately wheat-cookie-only, including old saved GUI policies.
    return ["Cookie"]


class SupportedFrame(CustomRecognition):
    def analyze(self, context, argv):
        ok = supported_frame(argv.image)
        return self.AnalyzeResult((0, 0, 1280, 720) if ok else None,
                                  {"supported_16_9": ok})


class SupportedStartupFrame(CustomRecognition):
    """Text-located startup dialogs may be handled on wider game windows."""
    def analyze(self, context, argv):
        image = argv.image
        ok = bool(image is not None and image.shape[0] == 720
                  and 960 <= image.shape[1] <= 2400 and image.std() >= 3)
        return self.AnalyzeResult((0, 0, image.shape[1], 720) if ok else None, {})


class Workflow:
    def __init__(self, context, timeout=240):
        self.context = context
        self.deadline = time.monotonic() + timeout

    def check(self):
        if self.context.tasker.stopping:
            raise RuntimeError("任务已停止")
        if time.monotonic() >= self.deadline:
            raise TimeoutError("任务超时，保留当前页面供检查")

    def frame(self, startup=False):
        self.check()
        controller = self.context.tasker.controller
        job = controller.post_screencap()
        deadline = time.monotonic() + 10
        while not job.done:
            self.check()
            if time.monotonic() > deadline:
                raise TimeoutError("游戏截图超时")
            time.sleep(0.1)
        image = controller.cached_image
        if not job.succeeded or image is None:
            raise RuntimeError("游戏截图失败")
        if not startup and not supported_frame(image):
            raise RuntimeError("需要非黑屏的 16:9 游戏画面；建议 1920×1080 或 1280×720")
        return image

    def startup(self, timeout=600):
        deadline = time.monotonic() + timeout
        updates = starts = 0
        self.log("等待游戏加载；识别到资源更新时自动确认")
        ready_pages = ["HomeHud", "MenuPage", "HomeCorePage", "HomeBuildingsPage", "WorkbenchPage", "FurnacePage", "TripPage", "AchievementPage",
                       "HomeCookingPage", "HomeSeedsPage", "HomeFoodPage", "MailPage", "DailyPage", "SignInPage",
                       "HomeFarmDetailPage", "HomeCollectionPage", "HomeLevelUp", "MailEmptyDialog",
                       "QuestPage", "TraveloguePage", "ActivityPage", "RewardPopup",
                       "OrderBoardPage", "OrderMerchantPage", "OrderSettlement", "OrderNews", "OrderNearby"]
        while time.monotonic() < deadline:
            image = self.frame(startup=True)
            if self.reco("ConfirmGameUpdate", image):
                if updates >= 3:
                    raise RuntimeError("资源更新提示重复出现，请检查下载是否失败")
                self.act("ConfirmGameUpdate")
                updates += 1
                self.log("已确认游戏资源更新，等待下载和加载")
            elif self.reco("StartGame", image):
                if starts >= 3:
                    raise RuntimeError("开始旅程后未成功进入游戏")
                self.act("StartGame")
                starts += 1
            elif supported_frame(image) and any(self.reco(page, image) for page in ready_pages):
                self.log("游戏已进入可识别页面")
                return
            time.sleep(1)
        raise TimeoutError("等待游戏加载超时，请检查登录、网络及 16:9 分辨率设置")

    def reco(self, node, image):
        self.check()
        result = self.context.run_recognition(node, image)
        return result if result and result.hit else None

    def wait_for(self, nodes, timeout=10):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            image = self.frame()
            for node in nodes:
                result = self.reco(node, image)
                if result:
                    return node, result
            time.sleep(0.25)
        raise TimeoutError("未识别到预期页面：" + " / ".join(nodes))

    def act(self, node):
        self.check()
        # A fresh recognition runs inside the pipeline immediately before input.
        result = self.context.run_task("Step", {"Step": {"next": [node], "timeout": 5000}})
        if not result or not result.status.succeeded:
            raise RuntimeError("操作未完成：" + node)

    def log(self, message):
        print(message, flush=True)
        self.context.run_task("Report", {"Report": {"focus": {"Node.Action.Starting": message}}})

    def counter(self, node, image=None):
        result = self.reco(node, self.frame() if image is None else image)
        if not result:
            raise RuntimeError("无法读取数量：" + node)
        value = parse_counter(result.best_result.text)
        if value is None:
            raise RuntimeError("数量格式异常：" + result.best_result.text)
        return value

    def navigate(self, target):
        routes = [
            ("AchievementPage", "AchievementClose"),
            ("TripPage", "TripClose"),
            ("OrderBoardPage", "OrderClose"),
            ("OrderMerchantPage", "OrderClose"),
            ("WorkbenchPage", "WorkbenchClose"),
            ("FurnacePage", "ProductionClose"),
            ("HomeSeedsPage", "HomeCloseSeeds"),
            ("HomeFarmDetailPage", "HomeCloseFarm"),
            ("HomeCookingPage", "HomeCloseCooking"),
            ("HomeFoodPage", "HomeCloseFood"),
            ("HomeCollectionPage", "HomeCloseCollection"),
            ("HomeLevelUp", "HomeLevelUp"),
            ("HomeBuildingsPage", "HomeBackBuildings"),
            ("HomeCorePage", "HomeBackCore"),
            ("MailEmptyDialog", "MailEmptyDialog"),
            ("MailPage", "CloseMail"),
            ("SignInPage", "CloseSignIn"),
            ("DailyPage", "CloseDaily"),
            ("QuestPage", "QuestBack"),
            ("TraveloguePage", "BackFromTravelogue"),
            ("ActivityPage", "BackFromActivity"),
            ("RewardPopup", "RewardPopup"),
            ("HomeHud", "OpenMenu"),
            ("StartGame", "StartGame"),
        ]
        attempts = {}
        for _ in range(18):
            image = self.frame()
            if self.reco(target, image):
                return
            if target == "HomeCorePage" and self.reco("MenuPage", image):
                self.act("OpenHomeCore")
                continue
            for page, action in routes:
                if self.reco(page, image):
                    attempts[action] = attempts.get(action, 0) + 1
                    if attempts[action] > 3:
                        raise RuntimeError("页面未响应导航操作：" + action)
                    self.act(action)
                    break
            else:
                raise RuntimeError("当前页面不在已验证导航范围，请返回游戏主界面后重试")
        raise RuntimeError("导航次数超限")

    def collect(self):
        self.navigate("HomeCorePage")
        self.act("HomeOpenBuildings")
        self.wait_for(["HomeBuildingsPage"])
        self.act("HomeCollectProduction")
        self.wait_for(["HomeCollectionPage"])
        self.log("家园一键收获完成（生产、耕作与采集产物）")
        self.act("HomeCloseCollection")
        page, _ = self.wait_for(["HomeLevelUp", "HomeBuildingsPage"])
        if page == "HomeLevelUp":
            self.act("HomeLevelUp")
            self.wait_for(["HomeBuildingsPage"])
        self.collect_ranch()

    def collect_ranch(self):
        self.navigate("HomeCorePage")
        if not self.reco("HomeRanchBasket", self.frame()):
            self.log("奇波牧场没有可领取篮子")
            return
        self.act("HomeRanchCollect")
        self.wait_for(["HomeRanchCollectionPage"])
        self.log("奇波牧场产物已领取，已确认牧场收获清单")
        self.act("HomeCloseCollection")
        page, _ = self.wait_for(["HomeLevelUp", "HomeCorePage"])
        if page == "HomeLevelUp":
            self.act("HomeLevelUp")
            self.wait_for(["HomeCorePage"])
        if self.reco("HomeRanchBasket", self.frame()):
            raise RuntimeError("牧场收获后篮子仍存在，请检查领取结果")

    def cook(self, maximum=True, quantity=None):
        self.navigate("HomeCorePage")
        self.act("HomeOpenBuildings")
        self.wait_for(["HomeBuildingsPage"])
        self.act("HomeOpenCooking")
        self.wait_for(["HomeCookingPage"])
        image = self.frame()
        idle = self.reco("HomeCookingIdle", image)
        if not idle and not (self.reco("HomeCookingQueue", image) or
                             self.reco("HomeCookingDone", image)):
            raise RuntimeError("无法确认烹饪槽状态，保留现有队列")
        if idle:
            self.act("HomeCookingAll")
            policy = self.context.get_node_object("RecipePolicy")
            candidates = recipe_order(policy.attach if policy else {})
            selected = None
            for key in candidates:
                label, choose, page = RECIPES[key]
                if not self.reco(choose, self.frame()):
                    self.log(label + "不在当前可见配方中，尝试下一候选")
                    continue
                self.act(choose)
                self.wait_for([page])
                self.act("HomeCookingMin")
                if self.reco("HomeCookingInsufficient", self.frame()):
                    self.log(label + "材料不足，本轮不制作其他食物")
                    if quantity is not None:
                        available, unit = self.counter("HomeCookingMaterials")
                        if unit != 4:
                            raise RuntimeError("小麦饼配方用量不符")
                        gap = max(0, (quantity if maximum else 1) * 4 - available)
                        self.log(f"普通金麦缺口 {gap}，对应 {(gap + 3) // 4} 颗普通金麦种子的产量；需再扣除在田及队列，未添加种子")
                    continue
                available, needed = self.counter("HomeCookingMaterials")
                if available >= needed > 0:
                    selected = label
                    break
            if selected is None:
                self.log("本轮没有可制作的候选食物，继续补充现有料理")
                return
            if quantity is not None:
                requested = quantity if maximum else 1
                if not 1 <= requested <= 100:
                    raise RuntimeError("本轮饼干缺口超出单批100份上限")
                available, unit_cost = self.counter("HomeCookingMaterials")
                if unit_cost != 4:
                    raise RuntimeError("小麦饼材料数量与配方不符")
                if available < requested * 4:
                    wheat_gap = requested * 4 - available
                    self.log(f"补餐还缺普通金麦 {wheat_gap}；按每颗种子4个小麦需 {(wheat_gap + 3) // 4} 颗种子的产量，补种前还需扣除在田和种子队列")
                    requested = min(requested, available // 4)
                if requested <= 0:
                    return
                for _ in range(requested - 1):
                    self.act("HomeCookingPlus")
            else:
                self.act("HomeCookingMax" if maximum else "HomeCookingMin")
            available, needed = self.counter("HomeCookingMaterials")
            if needed == 0 or available < needed or (quantity is not None and needed != requested * 4):
                raise RuntimeError("制作数量超出材料库存")
            self.act("HomeCookingStart")
            self.wait_for(["HomeCookingQueue", "HomeCookingDone"])
            self.log("已加入制作队列：" + selected)
        else:
            self.log("烹饪锅已有队列，保留原队列并等待完成")
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            image = self.frame()
            if self.reco("HomeCookingDone", image):
                self.log("食物已制作完成，重新收获后补餐")
                self.collect()
                return
            completed, total = self.counter("HomeCookingQueue", image)
            if total > 0 and completed == total:
                self.log("食物已制作完成，重新收获后补餐")
                self.collect()
                return
            self.check()
            time.sleep(1)
        self.log("制作仍在进行，保留队列；本轮先补充现有食物，下次运行收取新食物")

    def feed(self):
        self.navigate("HomeCorePage")
        self.act("HomeOpenFood")
        self.wait_for(["HomeFoodPage"])
        before, capacity = self.counter("HomeFoodSatiety")
        if before >= capacity:
            self.log("餐桌已满，无需添加小麦饼")
        elif not self.reco("HomeFoodCookie", self.frame()):
            self.log("当前食物列表没有小份波波饼，保留其他食物")
        else:
            self.act("HomeFoodSelectCookie")
            after, new_capacity = self.counter("HomeFoodSatiety")
            if capacity != new_capacity or after <= before:
                raise RuntimeError("选择小麦饼后未确认餐桌饱腹值增加")
            self.log(f"仅添加小份波波饼：饱腹值 {before} → {after}/{capacity}")
        self.act("HomeCloseFood")
        self.wait_for(["HomeCorePage"])

    def home(self, params):
        self.collect()
        if params.get("cook", True):
            quantity = self.food_needs_cooking()
            if quantity:
                self.cook(params.get("maximum", True), quantity=quantity)
        self.feed()
        self.log("家园流程完成：收获 → 按需制作小麦饼 → 仅用小麦饼补餐")

    def food_needs_cooking(self):
        self.navigate("HomeCorePage")
        self.act("HomeOpenFood")
        self.wait_for(["HomeFoodPage"])
        current, capacity = self.counter("HomeFoodSatiety")
        needed = max(0, (capacity - current + 24) // 25)
        stock = 0
        cookie = self.reco("HomeFoodCookie", self.frame()) if needed else None
        if cookie:
            x, _, width, _ = cookie.box
            result = self.context.run_recognition("HomeFoodCookieStock", self.frame(), {
                "HomeFoodCookieStock": {"roi": [x + width // 2 - 39, 664, 78, 23]}})
            if not result or not result.hit or not re.fullmatch(r"\d+", result.best_result.text):
                raise RuntimeError("无法读取小麦饼库存，停止新增制作")
            stock = int(result.best_result.text)
        self.act("HomeCloseFood")
        self.wait_for(["HomeCorePage"])
        if needed == 0 or stock >= needed:
            self.log(f"餐桌缺口 {capacity-current}，需饼干 {needed}；已有饼干足够，本轮制作、小麦和种子需求均为0")
            return 0
        from food_supply import plan_current_gap
        plan = plan_current_gap(current, capacity, stock)
        self.log(f"餐桌缺口 {plan['satiety_deficit']}，需饼干 {needed}；扣除库存 {stock} 后制作 {plan['cookies_to_make']} 份，需普通金麦 {plan['wheat_required']}")
        return plan['cookies_to_make']

    def mail(self):
        self.navigate("MenuPage")
        self.act("OpenMail")
        self.wait_for(["MailPage"])
        self.act("MailClaim")
        page, _ = self.wait_for(["RewardPopup", "MailEmptyDialog"])
        self.act(page)
        self.log("邮件奖励已领取" if page == "RewardPopup" else "邮件附件已全部领取，无新增奖励")
        self.wait_for(["MailPage"])
        self.act("CloseMail")
        self.wait_for(["MenuPage"])

    def signin(self):
        self.navigate("MenuPage")
        self.act("OpenHandbook")
        self.wait_for(["ActivityPage", "SignInPage"])
        if not self.reco("SignInPage", self.frame()):
            self.act("OpenSignIn")
        self.wait_for(["SignInPage"])
        if self.reco("SignInClaimProbe", self.frame()):
            self.act("SignInClaim")
            # Do not claim success just because the click API succeeded.
            self.wait_signin_settled()
            self.log("签到奖励已领取")
        else:
            self.wait_signin_settled()
            self.log("签到页没有识别到可领取卡片")
        self.act("CloseSignIn")
        self.wait_for(["ActivityPage", "MenuPage"])
        self.navigate("MenuPage")

    def wait_signin_settled(self):
        deadline = time.monotonic() + 10
        consecutive = 0
        popups = 0
        while time.monotonic() < deadline:
            image = self.frame()
            if self.reco("RewardPopup", image):
                if popups >= 2:
                    raise RuntimeError("签到奖励弹窗重复出现")
                self.act("RewardPopup")
                popups += 1
                consecutive = 0
                continue
            if self.reco("SignInPage", image) and not self.reco("SignInClaimProbe", image):
                consecutive += 1
                if consecutive >= 3:
                    return
            else:
                consecutive = 0
            time.sleep(0.4)
        raise TimeoutError("签到卡片仍可领取或页面未稳定")

    def activity(self, image, weekly=False):
        prefix = "Weekly" if weekly else "Daily"
        label_text = "周活跃度" if weekly else "日活跃度"
        result = self.reco(prefix + "Activity", image)
        if not result:
            label = self.context.run_recognition("DailyActivityLabel", image, {
                "DailyActivityLabel": {"recognition":"OCR", "expected":"^"+label_text+"$", "roi":[235,630,180,35]}})
            if label and label.hit:
                left = label.best_result.box[0]
                if 268 <= left <= 355:
                    result = self.context.run_recognition("DailyActivityDigit", image, {
                        "DailyActivityDigit": {"recognition":"OCR", "expected":r"^\d{1,3}$",
                            "only_rec":True, "roi":[239,636,left-243,40]}})
                    if not result or not result.hit: result = None
        if not result or not re.fullmatch(r"\d{1,3}(?:\s*/\s*100)?", result.best_result.text):
            raise RuntimeError("无法读取日常活跃度")
        value = int(result.best_result.text.split("/")[0].strip())
        if value > 100:
            raise RuntimeError("日常活跃度数值超出预期范围")
        return value

    def row_text(self, image, button_box):
        result = self.context.run_recognition("DailyTaskLabel", image, {
            "DailyTaskLabel": {"roi": [630, max(108, button_box.y - 15), 445,
                                      min(54, 605 - max(108, button_box.y - 15))]}})
        return result.best_result.text if result and result.hit else None

    def verify_daily_claim(self, before, title, button_box, weekly=False):
        deadline = time.monotonic() + 8
        stable_change = 0
        while time.monotonic() < deadline:
            image = self.frame()
            if not self.reco("WeeklyActive" if weekly else "DailyActive", image):
                time.sleep(0.3)
                continue
            after = self.activity(image, weekly=True) if weekly else self.activity(image)
            if after > before:
                return
            # At the cap, verify that the claimed row moves away, or its
            # status changes to 已领取. Require multiple stable observations.
            if before == after == 100:
                text = self.row_text(image, button_box)
                claimed = self.context.run_recognition("DailyTaskLabel", image, {
                    "DailyTaskLabel": {"roi": [1090, max(108, button_box.y - 10), 90, 45],
                                       "expected": "^已领取$"}})
                changed = (text is not None and text != title) or (claimed and claimed.hit)
                stable_change = stable_change + 1 if changed else 0
                if stable_change >= 3:
                    return
            time.sleep(0.3)
        raise RuntimeError("日常任务点击后未观察到活跃度增加或已领取状态")

    def daily(self, weekly=False):
        prefix = "Weekly" if weekly else "Daily"
        label = "周常" if weekly else "日常"
        self.navigate("MenuPage")
        self.act("OpenF5")
        self.wait_for(["DailyPage"])
        self.act(prefix + "SelectTab")
        self.wait_for([prefix + "Active"])
        self.act(prefix + "ScrollUp")
        claims = 0
        while True:
            image = self.frame()
            if not self.reco("WeeklyActive" if weekly else "DailyActive", image):
                raise RuntimeError("日常活跃页面发生变化")
            pending = self.reco(prefix + "Claim", image)
            if pending:
                if claims >= 20:
                    raise RuntimeError("日常领取次数超限")
                before = self.activity(image, weekly=True) if weekly else self.activity(image)
                title = self.row_text(image, pending.box)
                if not title:
                    raise RuntimeError("无法识别待领取的日常任务名称")
                self.act(prefix + "Claim")
                if weekly:
                    self.verify_daily_claim(before, title, pending.box, weekly=True)
                else:
                    self.verify_daily_claim(before, title, pending.box)
                claims += 1
                self.log(label + "任务奖励已领取：" + title)
                # Claiming can reorder rows above the current viewport.
                self.act(prefix + "ScrollUp")
                continue
            # Available entries are sorted first. Do not scan past a stopped row.
            if self.reco(prefix + "StoppedRow", image):
                break
            raise RuntimeError("无法确认日常首屏任务状态，停止操作")
        chests = 0
        for level in (20, 40, 60, 80, 100):
            image = self.frame()
            node = prefix + "Chest" + str(level)
            if (self.activity(image, weekly=True) if weekly else self.activity(image)) < level or not self.reco(node, image):
                continue
            self.act(node)
            self.wait_for(["RewardPopup"])
            self.act("RewardPopup")
            self.wait_for([prefix + "Active"])
            if self.reco(node, self.frame()):
                raise RuntimeError("活跃宝箱领取后仍显示可领取")
            chests += 1
            self.log(f"{level} 活跃度宝箱已领取")
        self.act("CloseDaily")
        self.wait_for(["MenuPage"])
        self.log(f"{label}奖励检查完成：领取任务 {claims} 项，宝箱 {chests} 个")


class RunRoutine(CustomAction):
    def run(self, context, argv):
        policy = context.get_node_object("WindowPolicy")
        enabled = policy.attach.get("topmost", True) if policy else True
        try:
            with game_on_top(enabled):
                return self.execute(context, argv)
        except Exception as exc:
            print("窗口操作失败：" + str(exc), flush=True)
            return False

    def execute(self, context, argv):
        workflow = Workflow(context, timeout=840)
        try:
            params = json.loads(argv.custom_action_param or "{}")
            kind = params.get("kind")
            workflow.startup()
            workflow.deadline = time.monotonic() + 240
            if kind == "startup":
                pass
            elif kind == "orders":
                workflow.deadline = time.monotonic() + 1200
                from order_workflow import run_orders
                run_orders(workflow)
            elif kind == "workbench":
                workflow.deadline = time.monotonic() + 1200
                from workbench import run_target
                policy = context.get_node_object("WorkbenchPolicy")
                run_target(workflow, policy.attach if policy else {})
            elif kind == "rewards":
                from rewards import training, travel, achievements
                workflow.deadline = time.monotonic() + 1200
                workflow.mail()
                workflow.signin()
                workflow.daily()
                workflow.daily(weekly=True)
                training(workflow)
                travel(workflow)
                achievements(workflow)
                workflow.log("已适配奖励检查完成")
            elif kind == "achievements":
                from rewards import achievements
                achievements(workflow)
            elif kind == "travel_rewards":
                workflow.deadline = time.monotonic() + 900
                from rewards import travel
                travel(workflow)
            elif kind == "training":
                workflow.deadline = time.monotonic() + 600
                from rewards import training
                training(workflow)
            elif kind == "home":
                workflow.home(params)
            elif kind == "collect":
                workflow.collect()
                workflow.navigate("HomeCorePage")
            elif kind == "feed":
                workflow.feed()
            elif kind == "mail":
                workflow.mail()
            elif kind == "signin":
                workflow.signin()
            elif kind == "weekly":
                workflow.daily(weekly=True)
            elif kind == "daily":
                workflow.daily()
            else:
                raise ValueError("未知任务类型：" + str(kind))
            return True
        except Exception as exc:
            if not context.tasker.stopping:
                workflow.log("任务未完成：" + str(exc))
            return False


def register(target):
    target.register_custom_recognition("SupportedFrame", SupportedFrame())
    target.register_custom_recognition("SupportedStartupFrame", SupportedStartupFrame())
    target.register_custom_action("RunRoutine", RunRoutine())
