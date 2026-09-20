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
    "Popcorn": ("惊奇爆谷", "HomeCookingChoosePopcorn", "HomeCookingPopcorn"),
}


def recipe_order(policy):
    priority = policy.get("priority", "Cookie")
    ordered = [priority] + [key for key in RECIPES if key != priority]
    return [key for key in ordered if key in RECIPES and policy.get(key, True)]


class SupportedFrame(CustomRecognition):
    def analyze(self, context, argv):
        ok = supported_frame(argv.image)
        return self.AnalyzeResult((0, 0, 1280, 720) if ok else None,
                                  {"supported_16_9": ok})


class Workflow:
    def __init__(self, context, timeout=240):
        self.context = context
        self.deadline = time.monotonic() + timeout

    def check(self):
        if self.context.tasker.stopping:
            raise RuntimeError("任务已停止")
        if time.monotonic() >= self.deadline:
            raise TimeoutError("任务超时，保留当前页面供检查")

    def frame(self):
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
        if not job.succeeded or not supported_frame(image):
            raise RuntimeError("需要非黑屏的 16:9 游戏画面；建议 1920×1080 或 1280×720")
        return image

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

    def cook(self, maximum=True):
        self.navigate("HomeCorePage")
        self.act("HomeOpenBuildings")
        self.wait_for(["HomeBuildingsPage"])
        self.act("HomeOpenCooking")
        self.wait_for(["HomeCookingPage"])
        image = self.frame()
        busy = self.reco("HomeCookingQueue", image)
        if not busy:
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
                if self.reco("HomeCookingInsufficient", self.frame()):
                    self.log(label + "材料不足，尝试下一候选")
                    continue
                available, needed = self.counter("HomeCookingMaterials")
                if available >= needed > 0:
                    selected = label
                    break
            if selected is None:
                self.log("本轮没有可制作的候选食物，继续补充现有料理")
                return
            self.act("HomeCookingMax" if maximum else "HomeCookingMin")
            available, needed = self.counter("HomeCookingMaterials")
            if needed == 0 or available < needed:
                raise RuntimeError("制作数量超出材料库存")
            self.act("HomeCookingStart")
            self.wait_for(["HomeCookingQueue"])
            self.log("已加入制作队列：" + selected)
        else:
            self.log("烹饪锅已有队列，保留原队列并等待完成")
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            completed, total = self.counter("HomeCookingQueue")
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
        self.act("HomeFoodAddAll")
        page, _ = self.wait_for(["HomeFoodAdded", "HomeFoodUnavailable"], timeout=4)
        self.log("餐桌一键添加完成" if page == "HomeFoodAdded" else "没有可填充的料理，本次未补充食物")
        self.act("HomeCloseFood")
        self.wait_for(["HomeCorePage"])

    def home(self, params):
        self.collect()
        if params.get("cook", True):
            self.cook(params.get("maximum", True))
        self.feed()
        self.log("家园流程完成：收获 → 制作或检查队列 → 补餐")

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

    def wait_signin_settled(self):
        deadline = time.monotonic() + 10
        consecutive = 0
        while time.monotonic() < deadline:
            image = self.frame()
            if self.reco("SignInPage", image) and not self.reco("SignInClaimProbe", image):
                consecutive += 1
                if consecutive >= 3:
                    return
            else:
                consecutive = 0
            time.sleep(0.4)
        raise TimeoutError("签到卡片仍可领取或页面未稳定")


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
        workflow = Workflow(context)
        try:
            params = json.loads(argv.custom_action_param or "{}")
            kind = params.get("kind")
            if kind == "home":
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
            else:
                raise ValueError("未知任务类型：" + str(kind))
            return True
        except Exception as exc:
            if not context.tasker.stopping:
                workflow.log("任务未完成：" + str(exc))
            return False


def register(target):
    target.register_custom_recognition("SupportedFrame", SupportedFrame())
    target.register_custom_action("RunRoutine", RunRoutine())
