"""app 层 — MatchingService。

应用层：编排领域逻辑 + 端口。
依赖的是 PersonaRepository / Narrator / KnowledgeExtractor 这些**抽象端口**，
不依赖任何具体 adapter —— 这样换数据源、换 AI 实现都不影响这一层。
"""
from __future__ import annotations

from dataclasses import dataclass

from domain.events import MeetingEvent
from domain.models import Persona
from domain.matching import match, MatchResult
from domain.seeds import extract_seeds
from domain.meeting_classifier import classify_meeting
from ports.event_bus import MeetingEventBus
from ports.persona_repository import PersonaRepository
from ports.narrator import Narrator
from ports.knowledge_extractor import KnowledgeExtractor
from ports.venue_suggester import VenueSuggester


@dataclass(frozen=True)
class TruthReport:
    """对照真值表的评估报告。"""
    hit_rate: float
    hits: int
    total: int
    p7_correct: bool
    per_person: dict[str, dict]   # {pid: {expected, actual_top, hit_count}}


class MatchingService:
    def __init__(self, repo: PersonaRepository, narrator: Narrator,
                 extractor: KnowledgeExtractor | None = None,
                 event_bus: MeetingEventBus | None = None,
                 sim_run_id: str = "default",
                 venue_suggester: VenueSuggester | None = None) -> None:
        self._repo = repo
        self._narrator = narrator
        # extractor 是可选的：只有"从文本注册人物"才需要。
        # 设为可选，不破坏只用现成数据的场景（8人集、30人集都不需要它）。
        self._extractor = extractor
        # event_bus 也是可选:只有想用异步路径 (enqueue_narrate) 才需要。
        # 老代码用同步 narrate_match,不传 bus 也能跑。
        self._event_bus = event_bus
        self._sim_run_id = sim_run_id
        # venue_suggester 可选:不传时 suggest_venue 会抛清楚的错
        self._venue_suggester = venue_suggester
        # 簇定义、对立表、互补表加载一次，复用
        self._clusters = repo.clusters()
        self._tension = repo.tension_pairs()
        self._style_complement = repo.style_complement_pairs()

    # ---- 从文本注册新人物 ----
    def register_from_text(self, text: str, persona_id: str,
                           name: str, gender: str = "") -> Persona:
        """用 extractor 把一段自述文本变成 Persona，并放进 repo。

        这是规模化的入口：用户写自述 -> 自动建 KG 子图 -> 进库可参与匹配。
        需要构造时注入 extractor，且 repo 要支持写入（有 add 方法）。
        """
        if self._extractor is None:
            raise RuntimeError(
                "register_from_text 需要在构造 MatchingService 时注入 extractor"
            )
        persona = self._extractor.extract(text, persona_id, name, gender)
        add = getattr(self._repo, "add", None)
        if add is None:
            raise RuntimeError(
                "register_from_text 需要一个支持写入的 repo（有 add 方法），"
                "如 InMemoryPersonaRepository"
            )
        add(persona)
        return persona

    # ---- 单人找匹配 ----
    def find_matches_for(self, persona_id: str) -> list[MatchResult]:
        """给指定的人找所有匹配上的候选，按分数降序。"""
        me = self._repo.get(persona_id)
        results = []
        for other in self._repo.all_personas():
            if other.id == me.id:
                continue
            r = match(me, other, self._clusters,
                      self._tension, self._style_complement)
            if r.matched:
                results.append(r)
        results.sort(key=lambda r: r.score, reverse=True)
        return results

    # ---- 推演一个匹配 ----
    def narrate_match(self, result: MatchResult) -> str:
        """对一个匹配结果做 AI 推演。AI 只在这里被调用。

        根据 score 和共簇等级把这次相遇分类到三档 call_point 之一,
        narrator (如果是 RoutedNarrator) 会按 call_point 选模型档位。
        非路由 narrator 会忽略 call_point —— 老代码不受影响。
        """
        a = self._repo.get(result.persona_a)
        b = self._repo.get(result.persona_b)
        seeds = extract_seeds(a, b, set(result.shared_clusters),
                              self._clusters, self._tension)
        if not seeds:
            return "（无可用故事种子）"
        # 把共簇 id 翻译成 levels,然后分类
        levels = [self._clusters[cid].level.value
                  for cid in result.shared_clusters
                  if cid in self._clusters]
        call_point = classify_meeting(result.score, levels)
        return self._narrator.narrate(
            seeds[0], a, b,
            call_point=call_point,
            shared_clusters=tuple(result.shared_clusters),
        )

    # ---- 推演一个匹配:异步路径 ----
    def enqueue_narrate(self, result: MatchResult, tick: int = 0) -> str:
        """把推演事件发到 EventBus,立即返回 event_id。

        真正的 narrate 由 NarrateWorker 异步消费。
        想要结果时:通过 sink.get(event_id) 查。

        用 sim_run_id + tick + 双方 id + score 算 event_id,
        多次 enqueue 同一对相遇时幂等 (bus 内部去重)。
        """
        if self._event_bus is None:
            raise RuntimeError(
                "enqueue_narrate 需要在构造 MatchingService 时注入 event_bus"
            )
        # 把 shared_clusters 翻成 levels
        levels = tuple(
            self._clusters[cid].level.value
            for cid in result.shared_clusters
            if cid in self._clusters
        )
        event = MeetingEvent(
            a_id=result.persona_a,
            b_id=result.persona_b,
            score=result.score,
            shared_clusters=tuple(result.shared_clusters),
            shared_levels=levels,
            tick=tick,
            sim_run_id=self._sim_run_id,
        )
        self._event_bus.publish(event)
        return event.event_id

    # ---- 场地推荐 (P1.6) ----
    def suggest_venue(self, result: MatchResult) -> str:
        """对一对匹配,生成场地建议文本。

        故知 P1.6 决定:不接 O2O 商家,只生成文本。
        所以这里没有"查附近哪家店",只有"按双方共同 LIKES 给类型建议"。
        """
        if self._venue_suggester is None:
            raise RuntimeError(
                "suggest_venue 需要在构造 MatchingService 时注入 venue_suggester"
            )
        a = self._repo.get(result.persona_a)
        b = self._repo.get(result.persona_b)
        return self._venue_suggester.suggest(a, b)

    # ---- 全矩阵 + 真值表评估 ----
    def all_pairs(self) -> list[MatchResult]:
        """跑所有 28 对（无序对），返回全部 MatchResult。"""
        personas = self._repo.all_personas()
        results = []
        for i in range(len(personas)):
            for j in range(i + 1, len(personas)):
                r = match(personas[i], personas[j], self._clusters,
                          self._tension, self._style_complement)
                results.append(r)
        return results

    def evaluate_against_truth(self) -> TruthReport:
        """对照真值表算命中率。真值表从 repo 之外加载——见下方注入。"""
        truth = self._load_truth()
        per_person = {}
        total_hits = 0
        total_expected = 0
        p7_correct = True

        for pid, expected in truth.items():
            matches = self.find_matches_for(pid)
            actual_top = [m.persona_b for m in matches[:3]]

            if not expected:
                # 期望无匹配（P7）
                ok = len(matches) == 0
                if pid == "P7":
                    p7_correct = ok
                per_person[pid] = {
                    "expected": [], "actual_top": actual_top,
                    "hit_count": 0, "expected_count": 0,
                }
                continue

            hits = [h for h in actual_top if h in expected]
            total_hits += len(hits)
            total_expected += min(3, len(expected))
            per_person[pid] = {
                "expected": expected,
                "actual_top": actual_top,
                "hit_count": len(hits),
                "expected_count": min(3, len(expected)),
            }

        hit_rate = total_hits / total_expected if total_expected else 0.0
        return TruthReport(
            hit_rate=hit_rate,
            hits=total_hits,
            total=total_expected,
            p7_correct=p7_correct,
            per_person=per_person,
        )

    def _load_truth(self) -> dict[str, list[str]]:
        """真值表加载。POC 里直接从 data/truth.json 读。

        注：严格来说真值表也该走一个端口。POC 阶段为简洁直接读文件，
        这是一个有意识的妥协，未来要重构成 TruthRepository 端口。
        """
        import json
        import os
        # repo 知道 data_dir —— 但端口没暴露它。POC 折中：从 repo 的属性拿。
        data_dir = getattr(self._repo, "_data_dir", None)
        if data_dir is None:
            raise RuntimeError("repo 未暴露 data_dir，无法加载真值表")
        path = os.path.join(data_dir, "truth.json")
        with open(path, encoding="utf-8") as f:
            return json.load(f)["expected_top"]
