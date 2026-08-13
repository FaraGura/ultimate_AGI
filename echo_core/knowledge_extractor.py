import re, traceback
from typing import Optional, Dict, Any, List

class KnowledgeExtractor:
    PATTERNS = [
        ("definition", "IS_A", [
            r"\*{0,2}([A-ZА-ЯЁ][^:]+?)\*{0,2}:\s*(.+?)(?:\.|$)",
            r"\b(.+?)\s*[—–-]\s*это\s+(.+)", r"\b(.+?)\s+это\s+(.+)",
            r"\b(.+?)\s+означает\s+(.+)", r"\b(.+?)\s+является\s+(.+)",
        ]),
        ("cause", "CAUSES", [r"\b(.+?)\s+вызывает\s+(.+)", r"\b(.+?)\s+приводит к\s+(.+)", r"\bесли\s+(.+?)\s*,\s*то\s+(.+)"]),
        ("property", "HAS_PROPERTY", [r"\b(.+?)\s+имеет\s+(.+)", r"\b(.+?)\s+обладает\s+(.+)"]),
        ("location", "LOCATED_IN", [r"\b(.+?)\s+находится в\s+(.+)", r"\b(.+?)\s+находится на\s+(.+)", r"\b(.+?)\s+лежит на\s+(.+)", r"\b(.+?)\s+лежит в\s+(.+)"]),
        ("action", "CAN_DO", [r"\b(.+?)\s+может\s+(.+)", r"\b(.+?)\s+умеет\s+(.+)", r"\b(.+?)\s+способен\s+(.+)"]),
    ]
    ADJ_PROPERTY_PATTERN = re.compile(r"\b(\w+)\s+(\w+(?:ый|ий|ой|ая|яя|ое|ее|ые|ие))\b", re.IGNORECASE)
    ADJ_ENDINGS = {"ый", "ий", "ой", "ая", "яя", "ое", "ее", "ые", "ие"}
    FALSE_ADJECTIVES = {"понятие", "здание", "собрание", "решение", "мнение", "среднее", "существо", "животное", "насекомое", "растение"}
    SUBJECT_STOP_WORDS = {
        "часто", "иногда", "или", "и", "но", "не", "очень", "весьма", "быстро", "всегда", "редко", "тоже", "также",
        "привет", "привет!", "здравствуйте", "здравствуйте!", "здравствуй", "здравствуй!", "добрый день", "доброе утро",
        "добрый вечер", "хай", "салют", "приветствую", "с удовольствием", "пожалуйста",
        "я", "мы", "ты", "вы", "он", "она", "оно", "они", "меня", "тебя", "его", "её", "нас", "вас", "их",
        "мне", "тебе", "ему", "ей", "нам", "вам", "им", "мной", "тобой", "ними", "нами", "вами",
        "на", "по", "за", "с", "в", "к", "у", "о", "от", "до", "из",
    }

    def __init__(self, causal_graph, db):
        self.causal_graph = causal_graph; self.db = db
        self.logger = getattr(causal_graph, 'logger', None)
        self._bridge_callback = None

    def _is_adjective(self, word: str) -> bool:
        w = word.lower().strip(".,!?():;\"'-")
        if w in self.FALSE_ADJECTIVES: return False
        for ending in self.ADJ_ENDINGS:
            if w.endswith(ending): return True
        return False

    def _preprocess_text(self, text: str) -> str:
        text = re.sub(r"\*{1,3}([^*]+?)\*{1,3}", r"\1", text)
        text = text.replace("\\", "")
        return text

    def _clean_response(self, text: str) -> str:
        lines = text.split('\n')
        cleaned = []
        for line in lines:
            stripped = line.strip()
            if re.match(r'^(Analyze|Here\'s a thinking|Note:|Thinking)', stripped, re.IGNORECASE): continue
            if re.match(r'^(\*{3,}|#{3,})$', stripped): continue
            cleaned.append(line)
        return '\n'.join(cleaned)

    def extract(self, text: str) -> Optional[Dict[str, Any]]:
        facts = self.extract_all(text)
        return facts[0] if facts else None

    def _classify_list_item(self, content: str) -> tuple[str, str]:
        text = content.strip().rstrip(".,!?;:")
        if not text:
            return "", ""

        lowered = text.lower()
        if re.match(r'^(свойства|свойство|свойства:|свойство:|функции|действия|что умеет|что может|особенности|характеристики)', lowered):
            return "", ""

        if re.match(r'^(\*{3,}|#{1,6}|\*{1,2}[^*]+\*{1,2}|\*{1,2}[^*]+)$', text):
            return "", ""

        if re.search(r'\b(может|умеет|способен|можно|служит|используется|предназначен|предназначена|предназначено)\b', lowered):
            return "CAN_DO", text

        if re.search(r'\b(имеет|обладает|состоит|является|представляет|характеризуется|сладкое|красное|белое|мягкое|твердый|гладкий|круглый|плоский|глубокий|большой|маленький|длинный|короткий|мягкий|хрупкий|тяжёлый|лёгкий|плотный|гибкий|яркий|тихий|шумный|вкусный|полезный|опасный|полезен)\b', lowered):
            return "HAS_PROPERTY", text

        return "HAS_PROPERTY", text

    def extract_all(self, text: str) -> List[Dict[str, Any]]:
        if not text or not text.strip(): return []
        text = self._preprocess_text(text.strip())
        text = self._clean_response(text)
        facts = []
        main_subject = None

        for knowledge_type, relation, patterns in self.PATTERNS:
            for pattern in patterns:
                match = re.match(pattern, text, re.IGNORECASE)
                if match:
                    subject = match.group(1).strip().rstrip(".,!?;:")
                    obj = match.group(2).strip().rstrip(".,!?;:")
                    if len(subject) > 1 and len(obj) > 1:
                        if subject.lower() not in self.SUBJECT_STOP_WORDS:
                            main_subject = subject
                            facts.append({"subject": subject, "relation": relation, "object": obj, "type": knowledge_type, "confidence": 0.6})
                    break

        if main_subject:
            for line in text.split('\n'):
                stripped = line.strip()
                if not stripped:
                    continue

                if re.match(r'^(\*{3,}|#{1,6}|\*{1,2}[^*]+\*{1,2}|\*{1,2}[^*]+)$', stripped):
                    continue

                if re.match(r'^(\*|-[^*]|\d+\.)\s+(.+)', stripped):
                    content = re.sub(r'^(\*|-[^*]|\d+\.)\s+', '', stripped)
                    if not content:
                        continue
                    content = re.sub(r'^\*+', '', content).strip()
                    if not content:
                        continue
                    if content.lower() in self.SUBJECT_STOP_WORDS:
                        continue
                    if re.match(r'^(свойства|свойство|функции|действия|характеристики|особенности|что умеет|что может)[:\s]*$', content.lower()):
                        continue
                    relation, object_text = self._classify_list_item(content)
                    if not relation or not object_text:
                        continue
                    facts.append({"subject": main_subject, "relation": relation, "object": object_text.strip().rstrip(".,!?;:"), "type": "list_item", "confidence": 0.5})

        return facts

    def _add_to_graph(self, result: Dict[str, Any]) -> None:
        try:
            subject, obj, relation = result.get("subject", ""), result.get("object", ""), result.get("relation", "")
            if not subject or not obj: return
            self.causal_graph.add_edge(subject, obj, relation, confidence=result.get("confidence", 0.6))
            if self._bridge_callback:
                try: status = self._bridge_callback(subject, obj, relation, result.get("confidence", 0.6))
                except Exception as e: print(f"[KE] Мост: {e}")
        except Exception as e: print(f"[KE] Ошибка: {e}")