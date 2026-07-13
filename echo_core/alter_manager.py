# echo_core/alter_manager.py
"""
Alter Manager v1.0 — система разветвления Echo (Fork Architecture).
Позволяет создавать изолированные экземпляры Альтеров на основе единого Core.
Каждый Альтер имеет свой контекст, цели и опыт. Управляется через AlterManager.
"""

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional


class AlterRole(Enum):
    GUARDIAN = "guardian"
    CODER = "coder"
    KNOWLEDGE = "knowledge"
    EXECUTION = "execution"
    BACKUP = "backup"
    CUSTOM = "custom"


@dataclass
class AlterInstance:
    alter_id: str
    role: AlterRole
    parent_id: str = "echo_primary"
    experience_layer: str = ""
    context_flags: int = 1  # GLOBAL
    created_tick: int = 0
    active: bool = True
    manifest: Dict[str, Any] = field(default_factory=dict)


class AlterManager:
    """Центральный реестр Альтеров."""

    def __init__(self):
        self.alters: Dict[str, AlterInstance] = {}
        self._load_manifests()

    def _load_manifests(self):
        """Загружает существующие манифесты из директории alters/."""
        alters_dir = "alters"
        if not os.path.exists(alters_dir):
            return
        for folder in os.listdir(alters_dir):
            manifest_path = os.path.join(alters_dir, folder, "manifest.json")
            if os.path.exists(manifest_path):
                try:
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    alter = AlterInstance(
                        alter_id=data.get("alter_id", folder),
                        role=AlterRole(data.get("role", "custom")),
                        parent_id=data.get("parent_id", "echo_primary"),
                        experience_layer=data.get("experience_layer", ""),
                        context_flags=data.get("context_flags", 1),
                        created_tick=data.get("created_tick", 0),
                        manifest=data
                    )
                    self.alters[alter.alter_id] = alter
                except Exception:
                    pass

    def create_alter(self, alter_id: str, role: AlterRole,
                     experience_layer: str = "",
                     context_flags: int = 1) -> AlterInstance:
        """Создаёт нового Альтера и его манифест."""
        if alter_id in self.alters:
            raise ValueError(f"Альтер '{alter_id}' уже существует")

        alter = AlterInstance(
            alter_id=alter_id,
            role=role,
            experience_layer=experience_layer,
            context_flags=context_flags
        )
        self.alters[alter_id] = alter
        self._save_manifest(alter)
        return alter

    def _save_manifest(self, alter: AlterInstance):
        """Сохраняет манифест Альтера в alters/{alter_id}/manifest.json."""
        alter_dir = f"alters/{alter.alter_id}"
        os.makedirs(alter_dir, exist_ok=True)
        manifest_data = {
            "alter_id": alter.alter_id,
            "role": alter.role.value,
            "parent_id": alter.parent_id,
            "experience_layer": alter.experience_layer,
            "context_flags": alter.context_flags,
            "created_tick": alter.created_tick
        }
        with open(f"{alter_dir}/manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, ensure_ascii=False, indent=2)

    def get_alter(self, alter_id: str) -> Optional[AlterInstance]:
        return self.alters.get(alter_id)

    def list_alters(self) -> list:
        return [
            {
                "id": a.alter_id,
                "role": a.role.value,
                "active": a.active,
                "experience_layer": a.experience_layer
            }
            for a in self.alters.values()
        ]

    def suspend_alter(self, alter_id: str):
        alter = self.alters.get(alter_id)
        if alter:
            alter.active = False

    def resume_alter(self, alter_id: str):
        alter = self.alters.get(alter_id)
        if alter:
            alter.active = True


# ======================
# ВСТРОЕННЫЕ ТЕСТЫ
# ======================
if __name__ == "__main__":
    manager = AlterManager()

    guardian = manager.create_alter("echo_guardian", AlterRole.GUARDIAN, "security")
    assert guardian.alter_id == "echo_guardian"
    assert guardian.role == AlterRole.GUARDIAN

    coder = manager.create_alter("echo_coder", AlterRole.CODER, "coding")
    assert len(manager.list_alters()) == 2

    manager.suspend_alter("echo_coder")
    assert not manager.get_alter("echo_coder").active

    manager.resume_alter("echo_coder")
    assert manager.get_alter("echo_coder").active

    print("✅ Все тесты AlterManager пройдены")
    print("Созданные Альтеры:", manager.list_alters())