# echo_win_pack.spec
# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

block_cipher = None

# ------------------------------------------------------------
# 1. Скрытые импорты (библиотеки, которые PyInstaller может не найти сам)
# ------------------------------------------------------------
hidden_imports = [
    'sentence_transformers',
    'sentence_transformers.models',
    'transformers',
    'transformers.models',
    'tokenizers',
    'tokenizers.decoders',
    'tokenizers.normalizers',
    'tokenizers.pre_tokenizers',
    'tokenizers.trainers',
    'llama_cpp',
    'faiss',
    'faiss.swigfaiss',
    'networkx',
    'networkx.algorithms',
    'networkx.generators',
    'numpy',
    'psutil',
    'pynvml',
    'json',
    'uuid',
    'hashlib',
    'dataclasses',
    'typing',
    'collections',
    'queue',
    'threading',
    'datetime',
    're',
    'random',
    'time',
    'gc',
    'pathlib',
]

# ------------------------------------------------------------
# 2. Данные (папки, файлы, которые нужно скопировать внутрь пакета)
# ------------------------------------------------------------
datas = []

# Копируем папки проекта
for folder in ['echo_core', 'utils', 'memory', 'language', 'runtime']:
    if os.path.exists(folder):
        datas.append((folder, folder))

# Копируем файлы, лежащие в корне
for f in ['echo_manifest.json', 'core_axioms.md', 'assistant_config_v14.json']:
    if os.path.exists(f):
        datas.append((f, '.'))

# Копируем папку data (language kernel, knowledge_input, логи, модели)
if os.path.exists('data'):
    datas.append(('data', 'data'))

# ------------------------------------------------------------
# 3. Бинарные файлы (динамические библиотеки llama-cpp и др.)
# ------------------------------------------------------------
binaries = []

# Если llama-cpp-python установлен, тащим его dll
try:
    import llama_cpp
    llama_dir = os.path.dirname(llama_cpp.__file__)
    for f in os.listdir(llama_dir):
        if f.endswith('.dll') or f.endswith('.pyd'):
            binaries.append((os.path.join(llama_dir, f), 'llama_cpp'))
except ImportError:
    pass

# ------------------------------------------------------------
# 4. Анализ и сборка
# ------------------------------------------------------------
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='EchoCore',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)