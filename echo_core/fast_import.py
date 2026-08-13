# echo_core/fast_import.py
import json
import csv
from typing import Optional

from echo_core.causal_graph import normalize


# Маппинг топ-10 свойств Wikidata в отношения Echo
WD_TO_ECHO = {
    "P31":  "IS_A",           # instance of
    "P279": "IS_A",           # subclass of
    "P17":  "LOCATED_IN",     # country
    "P36":  "HAS_PROPERTY",   # capital
    "P571": "HAS_PROPERTY",   # inception
    "P18":  "HAS_PROPERTY",   # image
    "P2048":"HAS_PROPERTY",   # height
    "P403": "LOCATED_IN",     # body of water
    "P131": "LOCATED_IN",     # located in admin territory
    "P3973":"HAS_PROPERTY",   # population
}
FALLBACK_RELATION = "RELATED_TO"


class FastImporter:
    def __init__(self, core):
        self.core = core
        self.db = core.db

    def _fast_identity_check(self, subject: str, obj: str) -> bool:
        """Проверка на пустые значения."""
        return bool(subject and obj and subject.strip() != obj.strip())

    def _prepare_provenance(self, source_type: str) -> dict:
        """Формирует provenance, гарантируя прохождение _evidence_check."""
        return {
            "engine": "external_db",
            "source": source_type,
            "method": "fast_import",
        }

    def _save_fact(self, subject: str, relation: str, obj: str,
                   confidence: float, source_type: str) -> bool:
        """
        Быстрый путь сохранения факта: записывает и в граф B (убеждения),
        и в граф A (causal_graph), чтобы memory.query мог найти факты.
        """
        if not self._fast_identity_check(subject, obj):
            return False

        subj_norm = normalize(subject)
        obj_norm = normalize(obj)

        provenance = self._prepare_provenance(source_type)

        belief_dict = {
            "source": subj_norm,
            "target": obj_norm,
            "relation": relation,
            "confidence": confidence,
            "certainty_type": "inductive",
            "status": "created",
            "provenance": provenance,
        }

        # Сохраняем в граф B (убеждения) с быстрым путём
        result = self.core.belief_manager.receive(belief_dict, fast_path=True)

        # Дублируем в граф A (причинный граф), чтобы memory.query видел факты
        try:
            self.core.causal.add_edge(
                subj_norm, obj_norm, relation,
                confidence=confidence,
                provenance_source=source_type
            )
        except Exception:
            pass  # не ломаем импорт, если граф A временно недоступен

        return result in ("active", "candidate")

    def ingest_wikidata_fact(self, entity_id: str, prop_id: str,
                             value: str, confidence: float = 0.9) -> bool:
        """Загружает один факт из Wikidata через Fast Path."""
        relation = WD_TO_ECHO.get(prop_id, FALLBACK_RELATION)
        return self._save_fact(entity_id, relation, value, confidence, "wikidata_truthy")

    def ingest_wikidata_file(self, filepath: str,
                             limit: int = 0) -> dict:
        """
        Пакетная загрузка Wikidata Truthy JSONL.
        Ожидаемый формат строки (с уже разрешёнными метками, не QID!):
        {"id": "дуглас адамс", "property": "P31", "value": "человек"}
        Возвращает статистику: {total, imported, skipped, errors}.
        """
        stats = {"total": 0, "imported": 0, "skipped": 0, "errors": 0}

        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                if limit and stats["total"] >= limit:
                    break
                stats["total"] += 1
                try:
                    data = json.loads(line.strip())
                    entity = data.get("id", "")
                    prop = data.get("property", "")
                    value = data.get("value", "")
                    if not entity or not prop or not value:
                        stats["skipped"] += 1
                        continue
                    if self.ingest_wikidata_fact(entity, prop, value):
                        stats["imported"] += 1
                    else:
                        stats["skipped"] += 1
                except Exception:
                    stats["errors"] += 1

        return stats

    def ingest_conceptnet_fact(self, relation: str, start: str, end: str,
                               confidence: float = 0.85) -> bool:
        """Загружает один факт из ConceptNet через Fast Path."""
        cn_to_echo = {
            "IsA": "IS_A",
            "PartOf": "HAS_PROPERTY",
            "HasA": "HAS_PROPERTY",
            "UsedFor": "CAN_DO",
            "CapableOf": "CAN_DO",
            "LocatedNear": "LOCATED_IN",
            "AtLocation": "LOCATED_IN",
            "Causes": "CAUSES",
        }
        echo_relation = cn_to_echo.get(relation, FALLBACK_RELATION)

        clean_start = start.split("/")[-1].replace("_", " ")
        clean_end = end.split("/")[-1].replace("_", " ")

        return self._save_fact(clean_start, echo_relation, clean_end,
                               confidence, "conceptnet")

    def ingest_conceptnet_file(self, filepath: str,
                               limit: int = 0) -> dict:
        """
        Пакетная загрузка ConceptNet CSV.
        Возвращает статистику.
        """
        stats = {"total": 0, "imported": 0, "skipped": 0, "errors": 0}

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if limit and stats["total"] >= limit:
                    break
                stats["total"] += 1
                try:
                    if len(row) < 3:
                        stats["skipped"] += 1
                        continue
                    uri_start = row[0]
                    uri_rel = row[1]
                    uri_end = row[2]

                    rel_type = uri_rel.split("/")[-1] if "/" in uri_rel else uri_rel

                    if self.ingest_conceptnet_fact(rel_type, uri_start, uri_end):
                        stats["imported"] += 1
                    else:
                        stats["skipped"] += 1
                except Exception:
                    stats["errors"] += 1

        return stats


# ─── Быстрый тест ──────────────────────────────────────────────────
if __name__ == "__main__":
    # Проверка маппинга Wikidata
    assert WD_TO_ECHO["P31"] == "IS_A"
    assert WD_TO_ECHO.get("P999", FALLBACK_RELATION) == "RELATED_TO"
    print("✅ Тест маппинга Wikidata пройден")

    # Проверка формирования provenance
    from unittest.mock import Mock
    mock_core = Mock()
    mock_core.belief_manager = Mock()
    mock_core.belief_manager.receive = Mock(return_value="candidate")
    mock_core.causal = Mock()
    mock_core.causal.add_edge = Mock()
    mock_core.db = Mock()
    importer = FastImporter(mock_core)
    prov = importer._prepare_provenance("wikidata_truthy")
    assert prov["engine"] == "external_db"
    assert prov["source"] == "wikidata_truthy"
    assert prov["method"] == "fast_import"
    print("✅ Тест provenance пройден")

    # Проверка, что _save_fact вызывает и belief_manager, и causal_graph
    importer._save_fact("кошка", "IS_A", "животное", 0.9, "wikidata_truthy")
    assert mock_core.belief_manager.receive.called, "belief_manager.receive не вызван"
    assert mock_core.causal.add_edge.called, "causal.add_edge не вызван"
    print("✅ _save_fact пишет в оба графа")

    print("\n🔥 fast_import.py v1.1 готов")