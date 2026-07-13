"""Mini-Prolog engine — facts, rules, unification, backtracking (stdlib only)."""

import re
from typing import Any, Dict, List, Optional, Tuple


class PrologEngine:
    def __init__(self, db=None):
        self.db = db
        self.facts: List[Tuple] = []
        self.rules: List[Tuple[Tuple, List[Tuple]]] = [
            (
                ("has", "_A", "_C"),
                [("is_a", "_A", "_B"), ("has", "_B", "_C")],
            ),
        ]
        self._ensure_table()
        self._load_facts_from_db()

    def _ensure_table(self):
        if not self.db:
            return
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS prolog_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                predicate TEXT NOT NULL,
                arg1 TEXT NOT NULL,
                arg2 TEXT,
                arg3 TEXT,
                confidence REAL DEFAULT 1.0
            )"""
        )

    def _load_facts_from_db(self):
        if not self.db:
            return
        rows = self.db.fetchall(
            "SELECT predicate, arg1, arg2, arg3 FROM prolog_facts"
        )
        self.facts = []
        for pred, a1, a2, a3 in rows:
            args = tuple(a for a in (a1, a2, a3) if a is not None)
            self.facts.append((pred, *args))

    def assert_fact(self, predicate: str, *args):
        fact = (predicate, *args)
        self.facts.append(fact)
        if self.db:
            a1 = args[0] if len(args) > 0 else ""
            a2 = args[1] if len(args) > 1 else None
            a3 = args[2] if len(args) > 2 else None
            self.db.execute(
                """INSERT INTO prolog_facts (predicate, arg1, arg2, arg3)
                   VALUES (?, ?, ?, ?)""",
                (predicate, a1, a2, a3),
            )

    def assert_rule(self, head: Tuple, body: List[Tuple]):
        self.rules.append((head, body))

    def _is_variable(self, term: Any) -> bool:
        if not isinstance(term, str):
            return False
        return term.startswith("_") or (len(term) > 0 and term[0].isupper())

    def _apply_subst(self, term: Any, subst: Dict[str, Any]) -> Any:
        while self._is_variable(term) and term in subst:
            term = subst[term]
        if isinstance(term, tuple):
            return tuple(self._apply_subst(t, subst) for t in term)
        return term

    def unify(
        self, term1: Any, term2: Any, subst: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        if subst is None:
            return None
        term1 = self._apply_subst(term1, subst)
        term2 = self._apply_subst(term2, subst)
        if term1 == term2:
            return subst
        if self._is_variable(term1):
            return {**subst, term1: term2}
        if self._is_variable(term2):
            return {**subst, term2: term1}
        if isinstance(term1, tuple) and isinstance(term2, tuple):
            if len(term1) != len(term2):
                return None
            for t1, t2 in zip(term1, term2):
                subst = self.unify(t1, t2, subst)
                if subst is None:
                    return None
            return subst
        return None

    def prove(
        self, goal: Tuple, subst: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        if subst is None:
            subst = {}
        solutions: List[Dict[str, Any]] = []

        for fact in self.facts:
            new_subst = self.unify(goal, fact, dict(subst))
            if new_subst is not None:
                solutions.append(new_subst)

        for head, body in self.rules:
            new_subst = self.unify(goal, head, dict(subst))
            if new_subst is not None:
                solutions.extend(self._prove_conjunction(body, new_subst))

        return solutions

    def _prove_conjunction(
        self, goals: List[Tuple], subst: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        if not goals:
            return [subst]
        solutions: List[Dict[str, Any]] = []
        for first_subst in self.prove(goals[0], subst):
            solutions.extend(self._prove_conjunction(goals[1:], first_subst))
        return solutions

    def query(self, predicate: str, *args) -> List[Dict[str, str]]:
        """Return variable bindings for a Prolog-style query."""
        self._load_facts_from_db()
        goal = (predicate, *args)
        query_vars = [a for a in args if self._is_variable(a)]
        raw_solutions = self.prove(goal)

        seen = set()
        results: List[Dict[str, str]] = []
        for sol in raw_solutions:
            binding = {}
            for var in query_vars:
                binding[var] = str(self._apply_subst(var, sol))
            key = tuple(sorted(binding.items()))
            if key not in seen:
                seen.add(key)
                results.append(binding)
        return results

    def query_string(self, query_str: str) -> str:
        """Parse ?- pred(args). and return a Russian-formatted answer."""
        text = query_str.strip()
        if text.startswith("?-"):
            text = text[2:].strip()
        text = text.rstrip(".")

        match = re.match(r"(\w+)\s*\((.*)\)", text)
        if not match:
            return "Не удалось разобрать запрос."

        pred = match.group(1)
        args_raw = match.group(2)
        args = [a.strip() for a in args_raw.split(",")] if args_raw.strip() else []
        bindings = self.query(pred, *args)

        if not bindings:
            return "Нет решения."

        parts = []
        for binding in bindings:
            if binding:
                parts.append(", ".join(f"{k} = {v}" for k, v in binding.items()))
            else:
                parts.append("Да")
        return "; ".join(parts)