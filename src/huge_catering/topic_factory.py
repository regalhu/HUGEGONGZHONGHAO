from __future__ import annotations

import json
from pathlib import Path

from .history import HistoryEntry


BATCH_SIZE = 10


SCENES = [
    ("breakfast", "早餐档", "早餐档想赚钱，老板别忽略这10个细节", "早餐看似简单，真正赚钱靠的是速度、稳定和复购。"),
    ("lunch", "午市经营", "午市翻台上不去，先查这10个地方", "午市拼的是效率，慢一分钟就可能少一桌。"),
    ("dinner", "晚市经营", "晚市客单提不上去，老板先改这10件事", "晚市不只看人多，更要看客单、体验和复购。"),
    ("night_snack", "夜宵经营", "夜宵店想稳住利润，先抓这10条", "夜宵生意看起来热闹，但损耗、人员和安全都要盯紧。"),
    ("takeaway_pack", "外卖包装", "外卖包装做不好，复购很难高", "包装不是附属品，它决定顾客收到菜时的第一感受。"),
    ("queue", "排队等位", "顾客愿不愿意等，关键看这10个动作", "等位管理做得好，排队是人气；做不好，排队就是差评。"),
    ("private_room", "包间经营", "包间不赚钱，老板要先算这10笔账", "包间占面积、占服务，也应该承担更清楚的利润目标。"),
    ("community_store", "社区店", "社区餐饮要做长久，先守住这10点", "社区店靠的不是一次热闹，而是邻里复购和稳定口碑。"),
    ("mall_store", "商场店", "商场餐饮成本高，老板要盯紧这10件事", "商场店流量好，但租金、人效和转化都要精细算。"),
    ("street_store", "街边店", "街边小店想活得舒服，先做好这10条", "街边店更考验门头、熟客、效率和现金流。"),
    ("new_store", "新店冷启动", "新店开业别只图热闹，先抓这10个结果", "开业活动不是越大越好，关键是把第一批顾客留下来。"),
    ("old_store", "老店翻新", "老店生意变淡，老板先问这10个问题", "老店下滑不是一天发生的，要从产品、服务和顾客变化里找答案。"),
    ("single_product", "单品店", "单品店想做稳，老板要盯这10个标准", "单品店看似简单，真正难的是长期稳定和持续复购。"),
    ("chain_store", "连锁复制", "餐饮想开第二家，先过这10道关", "能开一家店不等于能复制，标准和团队要先跑通。"),
    ("small_team", "小团队管理", "小餐饮人手少，老板更要抓这10个动作", "小团队不能靠硬扛，要靠清楚分工和关键动作。"),
    ("high_rent", "高租金门店", "租金高的店，老板必须算清这10件事", "高租金不是不能做，但模型必须更准、效率必须更高。"),
    ("low_margin", "低毛利品类", "毛利低的餐饮，先用这10条保利润", "低毛利品类更怕浪费、返工和无效优惠。"),
    ("seasonal", "季节波动", "淡旺季变化大，餐饮老板要提前做这10件事", "季节变化不是借口，提前准备才有主动权。"),
    ("holiday", "节假日经营", "节假日生意好，老板更要盯住这10点", "节假日最容易忙中出错，越热闹越要稳。"),
    ("weather", "天气影响", "下雨降温没客流，餐饮店可以先改这10件事", "天气会影响客流，但老板可以提前设计应对动作。"),
    ("membership", "会员运营", "会员不是发卡，老板要做好这10件事", "会员运营的核心不是办卡数量，而是顾客回来得更勤。"),
    ("drink_addon", "饮品小吃", "饮品小吃卖不好，客单很难提", "小吃和饮品是利润补充，也能提升顾客体验。"),
    ("children_family", "家庭客群", "做家庭客，餐饮店要先照顾这10个细节", "家庭客看重的不只是口味，还有安全、空间和服务分寸。"),
    ("young_customers", "年轻客群", "想抓年轻顾客，别只学网红装修", "年轻顾客要新鲜感，也要真实体验和可分享的记忆点。"),
    ("office_workers", "白领客群", "做白领生意，午晚市要分开算", "白领客群看重效率、稳定和价格带，不能只靠口味。"),
    ("training_meeting", "班前会", "餐饮班前会别空喊，讲清这10件事", "班前会短一点、准一点，饭口执行才会好一点。"),
    ("waste_control", "损耗控制", "餐饮损耗降不下来，先查这10个漏洞", "损耗不是月底才发现的，是每天一点点漏掉的。"),
    ("refunds", "退菜退款", "退菜退款变多，老板先查这10个原因", "退菜退款背后往往是出品、服务和沟通的问题。"),
    ("equipment", "设备维护", "设备总在饭口坏，老板要提前做这10件事", "设备维护不是后勤小事，它直接影响出餐和顾客体验。"),
    ("training_sop", "岗位标准", "岗位标准写不清，员工就很难做稳定", "标准不是贴墙上看的，是饭口能用、员工能照做的。"),
]


ANGLES = [
    ("money", "赚钱"),
    ("speed", "效率"),
    ("retention", "复购"),
    ("standard", "标准"),
    ("risk", "避坑"),
    ("service", "体验"),
    ("team", "团队"),
    ("data", "数据"),
    ("cost", "成本"),
    ("growth", "增长"),
]


def ensure_fresh_topic_batch(
    topic_library_path: Path,
    *,
    history: list[HistoryEntry],
    batch_size: int = BATCH_SIZE,
) -> list[dict[str, object]]:
    current = _read_raw_topics(topic_library_path)
    used_ids = {entry.topic_id for entry in history}
    available = [topic for topic in current if str(topic.get("id")) not in used_ids]
    if available:
        return current

    used_titles = {_base_title(entry.title) for entry in history}
    new_topics = _build_next_batch(used_ids=used_ids, used_titles=used_titles, batch_size=batch_size)
    topic_library_path.parent.mkdir(parents=True, exist_ok=True)
    topic_library_path.write_text(
        json.dumps(new_topics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return new_topics


def _build_next_batch(
    *,
    used_ids: set[str],
    used_titles: set[str],
    batch_size: int,
) -> list[dict[str, object]]:
    topics: list[dict[str, object]] = []
    for scene_index, scene in enumerate(SCENES):
        for angle_index, angle in enumerate(ANGLES):
            topic_id = f"auto_{scene[0]}_{angle[0]}"
            if topic_id in used_ids:
                continue
            title = _title_for(scene, angle)
            if title in used_titles:
                continue
            topics.append(_topic_payload(scene, angle, scene_index, angle_index))
            if len(topics) == batch_size:
                return topics
    raise RuntimeError("No unused article topics left in the built-in topic factory.")


def _topic_payload(
    scene: tuple[str, str, str, str],
    angle: tuple[str, str],
    scene_index: int,
    angle_index: int,
) -> dict[str, object]:
    scene_id, scene_name, scene_title, scene_intro = scene
    angle_id, angle_name = angle
    title = _title_for(scene, angle)
    digest = f"胡哥今天聊{scene_name}的{angle_name}。不是讲大道理，都是老板明天能检查的动作。"
    intro = f"老板，{scene_intro}今天这10句，咱们专门从{angle_name}这个角度，把{scene_name}该抓的地方说透一点。"
    advices = _advices_for(scene_name, angle_name, scene_index, angle_index)
    return {
        "id": f"auto_{scene_id}_{angle_id}",
        "name": f"{scene_name}·{angle_name}",
        "title": title,
        "digest": digest,
        "intro": intro,
        "advices": advices,
    }


def _title_for(scene: tuple[str, str, str, str], angle: tuple[str, str]) -> str:
    if angle[0] == "money":
        return scene[2]
    return f"{scene[1]}想做好{angle[1]}，老板先听这10句劝"


def _advices_for(scene_name: str, angle_name: str, scene_index: int, angle_index: int) -> list[list[str]]:
    openers = [
        "先把目标说清楚",
        "别只看表面热闹",
        "流程要让员工照着做",
        "顾客感受要当天听",
        "成本口子要提前堵",
        "数据不能只月底看",
        "员工动作要练到位",
        "问题要追到现场",
        "小改动要坚持复盘",
        "老板要守住节奏",
    ]
    bodies = [
        "{scene}不是靠感觉管的。今天到底要抓{angle}里的哪一个结果，老板先讲清楚，团队才不会各忙各的。",
        "人多、单多、声音大，不一定代表{angle}好。真正要看的是顾客满不满意，钱有没有留下来。",
        "{scene}最怕每个人都有自己的做法。动作不统一，出品和服务就会忽高忽低。",
        "顾客当场的反应，比月底报表更早。等到差评出来再改，成本就高了。",
        "浪费、返工、错单、等待，都是{angle}里的暗洞。老板不盯，它就每天漏一点。",
        "每天看一个关键数：客单、复购、损耗、出餐时间，选一个盯住，比什么都泛泛看更有用。",
        "员工不是不想做好，是很多时候不知道标准。老板要把好动作拆开教，不能只喊加油。",
        "问题不要停在谁没做好，要追到哪个环节没设计好。找到环节，才改得长久。",
        "今天改一句话术，明天改一个摆放，后天改一个检查点。{scene}变好，靠的是连续小步。",
        "老板越急，店越乱。把节奏稳住，把标准守住，{angle}才会慢慢长出来。",
    ]
    shift = (scene_index + angle_index) % len(openers)
    result: list[list[str]] = []
    for index in range(10):
        source_index = (index + shift) % 10
        title = openers[source_index]
        body = bodies[source_index].format(scene=scene_name, angle=angle_name)
        result.append([title, body])
    return result


def _read_raw_topics(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _base_title(title: str) -> str:
    return title.split("｜", 1)[0].strip()
