#!/usr/bin/env python3
"""
SCP Wiki Dataset Builder — Real Data Only
=========================================
Загружает реальные данные из SCP Data API (tedivm).
Структура API: https://scp-data.tedevm.com/

Форматы: .md, .txt, .py, .js, .ts, .json, .yaml

Источник: SCP Foundation Wiki (CC BY-SA 3.0)
"""

import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
import yaml

# ═══════════════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════════════════

TARGET_SIZE_BYTES = 2_000_000
OUTPUT_DIR = Path("demo_documents")

# Базовый URL API
API_BASE = "https://scp-data.tedivm.com/data/scp"

ENDPOINTS = {
    "items_meta": f"{API_BASE}/items/index.json",
    "items_content": f"{API_BASE}/items/content_index.json",
    "tales_meta": f"{API_BASE}/tales/index.json",
    "tales_content": f"{API_BASE}/tales/content_index.json",
    "goi_meta": f"{API_BASE}/goi/index.json",
    "goi_content": f"{API_BASE}/goi/content_goi.json",
    "hubs": f"{API_BASE}/hubs/index.json",
}


# ═══════════════════════════════════════════════════════════════
# УТИЛИТЫ
# ═══════════════════════════════════════════════════════════════


def ensure_dirs() -> None:
    """Создаёт структуру папок."""
    for subdir in ["scp", "tales", "goi", "hubs", "code", "metadata", "logs"]:
        (OUTPUT_DIR / subdir).mkdir(parents=True, exist_ok=True)


def get_dir_size() -> int:
    """Текущий размер всех файлов в OUTPUT_DIR."""
    total = 0
    for path in OUTPUT_DIR.rglob("*"):
        if path.is_file():
            total += path.stat().st_size
    return total


def save_file(subdir: str, filename: str, content: str) -> Path:
    """Сохраняет файл, возвращает путь."""
    filepath = OUTPUT_DIR / subdir / filename
    filepath.write_text(content, encoding="utf-8")
    return filepath


def fetch_json(url: str, retries: int = 3, delay: float = 2.0) -> Optional[dict]:
    """Загружает JSON с retry-логикой."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"  ⚠️ Попытка {attempt + 1}/{retries}: {e}")
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))
    print(f"  ❌ Не удалось загрузить: {url}")
    return None


def sanitize_filename(name: str, max_len: int = 80) -> str:
    """Очищает строку для имени файла."""
    invalid = '<>:"/\\|?*'
    result = "".join("_" if c in invalid else c for c in name)
    result = re.sub(r"\s+", "_", result.strip(" ._"))
    return result[:max_len] if result else "untitled"


def extract_code_blocks(text: str) -> List[Tuple[str, str]]:
    """Извлекает блоки кода ```lang ... ``` из текста."""
    blocks = []
    pattern = r"```(\w+)?\n(.*?)```"
    for match in re.finditer(pattern, text, re.DOTALL):
        lang = (match.group(1) or "text").strip().lower()
        code = match.group(2).strip()
        if len(code) >= 30:
            blocks.append((lang, code))
    return blocks


# ═══════════════════════════════════════════════════════════════
# СБОРЩИКИ .md ФАЙЛОВ
# ═══════════════════════════════════════════════════════════════


def build_scp_markdown(item: dict) -> str:
    """Собирает .md файл SCP-объекта."""
    item_num = item.get("scp_number", item.get("scp", "???"))
    obj_class = item.get("object_class", "Unknown")

    # Определяем класс из тегов если не указан
    if obj_class == "Unknown":
        tags = [t.lower() for t in item.get("tags", [])]
        for cls in ["safe", "euclid", "keter", "thaumiel", "apollyon"]:
            if cls in tags:
                obj_class = cls.capitalize()
                break

    tags = item.get("tags", [])
    rating = item.get("rating", "N/A")
    author = item.get("created_by", "Unknown")
    series = item.get("series", "Unknown")
    hubs = item.get("hubs", [])
    url = item.get("url", "")
    raw_content = item.get("raw_content", "No content available.")

    # Очищаем wiki-разметку
    content = raw_content.replace("[[", "").replace("]]", "")

    return f"""# SCP-{item_num}

**Item #:** SCP-{item_num}

**Object Class:** {obj_class}

**Series:** {series}

**Author:** {author}

**Rating:** {rating}

**Tags:** {", ".join(tags[:30]) if tags else "None"}

**Hubs:** {", ".join(hubs[:10]) if hubs else "None"}

**URL:** {url}

---

## Description

{content}

---

## Metadata

| Key | Value |
|-----|-------|
| Item Number | SCP-{item_num} |
| Object Class | {obj_class} |
| Series | {series} |
| Author | {author} |
| Rating | {rating} |

"""


def build_tale_markdown(tale: dict) -> str:
    """Собирает .md файл рассказа."""
    title = tale.get("title", "Untitled Tale")
    author = tale.get("created_by", "Unknown")
    tags = tale.get("tags", [])
    rating = tale.get("rating", "N/A")
    hubs = tale.get("hubs", [])
    url = tale.get("url", "")
    raw_content = tale.get("raw_content", "No content available.")

    word_count = len(raw_content.split())

    return f"""# {title}

**Type:** Foundation Tale

**Author:** {author}

**Rating:** {rating}

**Word Count:** {word_count}

**Tags:** {", ".join(tags[:30]) if tags else "None"}

**Hubs:** {", ".join(hubs[:10]) if hubs else "None"}

---

{raw_content}

---

## Metadata

| Key | Value |
|-----|-------|
| Title | {title} |
| Author | {author} |
| Rating | {rating} |
| Word Count | {word_count} |

---
*Source: SCP Foundation Wiki (CC BY-SA 3.0)*
"""


def build_goi_markdown(goi: dict) -> str:
    """Собирает .md файл GOI-формата."""
    title = goi.get("title", "Unknown GOI Format")
    author = goi.get("created_by", "Unknown")
    tags = goi.get("tags", [])
    rating = goi.get("rating", "N/A")
    url = goi.get("url", "")
    raw_content = goi.get("raw_content", "No content available.")

    return f"""# {title}

**Type:** GOI Format (Group of Interest)

**Author:** {author}

**Rating:** {rating}

**Tags:** {", ".join(tags[:30]) if tags else "None"}

**URL:** {url}

---

{raw_content}

"""


def build_hub_markdown(hub: dict) -> str:
    """Собирает .md файл хаба."""
    title = hub.get("title", "Unknown Hub")
    tags = hub.get("tags", [])
    refs = hub.get("references", [])
    raw_content = hub.get("raw_content", "No content available.")
    url = hub.get("url", "")

    return f"""# {title}

**Type:** Hub / Canon Hub

**Tags:** {", ".join(tags[:30]) if tags else "None"}

**Referenced Articles:** {len(refs)}

**URL:** {url}

---

{raw_content}

---

## Referenced Articles

{chr(10).join(f"- {ref}" for ref in refs[:50])}

"""


# ═══════════════════════════════════════════════════════════════
# ИЗВЛЕЧЕНИЕ КОДА И МЕТАДАННЫХ
# ═══════════════════════════════════════════════════════════════


def save_code_blocks(
    item_id: str, source_type: str, raw_content: str
) -> Dict[str, int]:
    """Извлекает кодовые блоки и сохраняет как отдельные файлы."""
    blocks = extract_code_blocks(raw_content)
    counts = {"py": 0, "js": 0, "ts": 0, "json": 0, "yaml": 0, "txt": 0}

    ext_map = {
        "python": ".py",
        "py": ".py",
        "javascript": ".js",
        "js": ".js",
        "typescript": ".ts",
        "ts": ".ts",
        "json": ".json",
        "yaml": ".yaml",
        "yml": ".yaml",
        "bash": ".txt",
        "shell": ".txt",
        "text": ".txt",
    }

    for i, (lang, code) in enumerate(blocks):
        ext = ext_map.get(lang, ".txt")

        if ext == ".py":
            subdir, fname = "code", f"{source_type}_{item_id}_code_{i:02d}.py"
            counts["py"] += 1
        elif ext == ".js":
            subdir, fname = "code", f"{source_type}_{item_id}_script_{i:02d}.js"
            counts["js"] += 1
        elif ext == ".ts":
            subdir, fname = "code", f"{source_type}_{item_id}_types_{i:02d}.ts"
            counts["ts"] += 1
        elif ext == ".json":
            subdir, fname = "metadata", f"{source_type}_{item_id}_data_{i:02d}.json"
            counts["json"] += 1
        elif ext == ".yaml":
            subdir, fname = "metadata", f"{source_type}_{item_id}_config_{i:02d}.yaml"
            counts["yaml"] += 1
        else:
            subdir, fname = "logs", f"{source_type}_{item_id}_log_{i:02d}.txt"
            counts["txt"] += 1

        header = f"# Extracted from {source_type.upper()}-{item_id}\\n"
        header += f"# Language: {lang}\\n"
        header += f"# Source: SCP Foundation Wiki\\n\\n"

        save_file(subdir, fname, header + code)

    return counts


def save_metadata(item: dict, item_id: str, source_type: str) -> None:
    """Сохраняет метаданные как .json и .yaml."""
    # JSON
    meta_json = {
        "item_id": item_id,
        "type": source_type,
        "title": item.get("title") or item.get("scp", f"SCP-{item_id}"),
        "author": item.get("created_by", "Unknown"),
        "rating": item.get("rating", "N/A"),
        "tags": item.get("tags", []),
        "hubs": item.get("hubs", []),
        "url": item.get("url", ""),
        "page_id": item.get("page_id", ""),
        "created_at": item.get("created_at", ""),
        "source": "SCP Foundation Wiki",
        "license": "CC BY-SA 3.0",
        "api": "https://scp-data.tedevm.com/",
        "retrieved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_file(
        "metadata",
        f"{source_type}_{item_id}_meta.json",
        json.dumps(meta_json, indent=2, ensure_ascii=False),
    )

    # YAML
    meta_yaml = {
        "item": {
            "id": item_id,
            "type": source_type,
            "title": item.get("title") or item.get("scp", f"SCP-{item_id}"),
            "author": item.get("created_by", "Unknown"),
            "rating": item.get("rating", "N/A"),
            "tags": item.get("tags", []),
            "hubs": item.get("hubs", []),
        },
        "source": {
            "url": item.get("url", ""),
            "page_id": item.get("page_id", ""),
            "license": "CC BY-SA 3.0",
            "api": "https://scp-data.tedevm.com/",
            "retrieved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
    }
    save_file(
        "metadata",
        f"{source_type}_{item_id}_meta.yaml",
        yaml.dump(meta_yaml, allow_unicode=True, sort_keys=False),
    )


# ═══════════════════════════════════════════════════════════════
# ЗАГРУЗКА КОНТЕНТА ПО content_file
# ═══════════════════════════════════════════════════════════════


def resolve_content_url(content_file: str, source_type: str) -> str:
    """
    Формирует полный URL для файла контента.
    content_file относительно index.json файла.

    Если content_file — абсолютный путь (например, от GitHub Actions runner),
    извлекаем только имя файла и используем его как относительный путь.
    """
    if source_type == "scp":
        base = f"{API_BASE}/items/"
    elif source_type == "tale":
        base = f"{API_BASE}/tales/"
    else:
        base = f"{API_BASE}/goi/"

    # content_file может быть:
    #   - относительным путём:  "./series1.json" или "series1.json"
    #   - абсолютным локальным: "/home/runner/work/.../content_2008.json"
    # Для абсолютных путей берём только basename
    if os.path.isabs(content_file):
        clean_path = os.path.basename(content_file)
    else:
        clean_path = content_file.lstrip("./")
    return base + clean_path


def load_content_by_file(content_file: str, source_type: str) -> Optional[dict]:
    """Загружает файл контента по пути из content_file."""
    url = resolve_content_url(content_file, source_type)
    return fetch_json(url)


def merge_content(meta: dict, content_data: dict) -> dict:
    """Объединяет метаданные с данными контента."""
    merged = dict(meta)
    if "raw_content" in content_data:
        merged["raw_content"] = content_data["raw_content"]
    if "raw_source" in content_data:
        merged["raw_source"] = content_data["raw_source"]
    return merged


# ═══════════════════════════════════════════════════════════════
# ОБРАБОТЧИКИ КАТЕГОРИЙ
# ═══════════════════════════════════════════════════════════════


def process_items_with_content_index(
    items_meta: dict,
    content_index: dict,
    source_type: str,
    remaining_quotas: Dict[str, int],
    category_order: List[str],
    current_idx: int,
) -> Dict[str, int]:
    """
    Обрабатывает SCP Items или Tales с загрузкой контента через content_index.

    Останавливается, когда превышена квота категории в remaining_quotas.
    """
    stats = {"md": 0}

    budget = remaining_quotas.get(source_type, 0)
    spent = 0

    # Загружаем все файлы контента заранее (кэшируем)
    print(f"   📦 Загрузка файлов контента...")
    content_cache = {}  # link -> item_with_content

    for series_name, content_file in content_index.items():
        content_data = load_content_by_file(content_file, source_type)
        if not content_data:
            print(f"   ⚠️ Не удалось загрузить: {content_file}")
            continue

        if isinstance(content_data, dict):
            for link, item in content_data.items():
                content_cache[link] = item

        print(
            f"   ✅ {series_name}: {len(content_data) if isinstance(content_data, dict) else '?'} элементов"
        )

    print(f"   📋 Всего в кэше контента: {len(content_cache)} элементов")
    print(f"   📋 Всего в метаданных: {len(items_meta)} элементов")

    for link, meta in items_meta.items():
        if spent >= budget or budget <= 0:
            print(f"   ⏹️ Достигнута квота категории ({budget:,} байт)")
            break

        item_id = sanitize_filename(link)

        if link in content_cache:
            item = merge_content(meta, content_cache[link])
        else:
            item = dict(meta)

        raw_content = item.get("raw_content", "")
        if not raw_content:
            continue

        if source_type == "scp":
            md_content = build_scp_markdown(item)
            save_file("scp", f"scp_{item_id}.md", md_content)
        else:
            md_content = build_tale_markdown(item)
            save_file("tales", f"{item_id}.md", md_content)

        stats["md"] += 1

        # meta_json = {
        #    "type": source_type,
        #    "title": item.get("title") or item.get("scp", item_id),
        #    "author": item.get("created_by", "Unknown"),
        #    "rating": item.get("rating", "N/A"),
        #    "tags": item.get("tags", []),
        #    "url": item.get("url", ""),
        # }
        # meta_str = json.dumps(meta_json, indent=2, ensure_ascii=False)
        # save_file("metadata", f"{source_type}_{item_id}_meta.json", meta_str)

        item_bytes = len(md_content.encode("utf-8"))  # + len(meta_str.encode("utf-8"))
        spent += item_bytes

        if stats["md"] % 20 == 0:
            print(
                f"   📄 Обработано: {stats['md']} | Потрачено: {spent:,}/{budget:,} байт"
            )

    remaining_quotas[source_type] = max(0, budget - spent)

    total_spent = sum(remaining_quotas.values()) + spent
    if budget > spent and total_spent < TARGET_SIZE_BYTES:
        leftover = budget - spent
        future_categories = category_order[current_idx + 1 :]
        active_future = [c for c in future_categories if remaining_quotas.get(c, 0) > 0]
        if active_future and leftover > 0:
            extra_per = leftover // len(active_future)
            remainder = leftover % len(active_future)
            for i, fc in enumerate(active_future):
                remaining_quotas[fc] = (
                    remaining_quotas.get(fc, 0)
                    + extra_per
                    + (1 if i < remainder else 0)
                )
            print(
                f"   🔄 Категория '{source_type}' завершилась раньше квоты: +{leftover:,}B перераспределено → {', '.join(active_future)}"
            )

    return stats


def process_goi(
    goi_content: dict,
    remaining_quotas: Dict[str, int],
    category_order: List[str],
    current_idx: int,
) -> Dict[str, int]:
    """Обрабатывает GOI-форматы."""
    stats = {"md": 0}

    if not isinstance(goi_content, dict):
        print("   ⚠️ GOI данные не в формате dict")
        return stats

    budget = remaining_quotas.get("goi", 0)
    spent = 0

    print(f"   📋 GOI форматов: {len(goi_content)}")

    for link, item in goi_content.items():
        if spent >= budget or budget <= 0:
            print(f"   ⏹️ Достигнута квота категории ({budget:,} байт)")
            break

        item_id = sanitize_filename(link)
        raw_content = item.get("raw_content", "")
        if not raw_content:
            continue

        md_content = build_goi_markdown(item)
        save_file("goi", f"{item_id}.md", md_content)
        stats["md"] += 1

        meta_json = {
            "type": "goi",
            "title": item.get("title", item_id),
            "author": item.get("created_by", "Unknown"),
            "rating": item.get("rating", "N/A"),
            "tags": item.get("tags", []),
            "url": item.get("url", ""),
        }
        meta_str = json.dumps(meta_json, indent=2, ensure_ascii=False)
        save_file("metadata", f"goi_{item_id}_meta.json", meta_str)

        item_bytes = len(md_content.encode("utf-8")) + len(meta_str.encode("utf-8"))
        spent += item_bytes

        if stats["md"] % 10 == 0:
            print(f"   📄 GOI: {stats['md']} | Потрачено: {spent:,}/{budget:,} байт")

    remaining_quotas["goi"] = max(0, budget - spent)

    total_spent = sum(remaining_quotas.values()) + spent
    if budget > spent and total_spent < TARGET_SIZE_BYTES:
        leftover = budget - spent
        future_categories = category_order[current_idx + 1 :]
        active_future = [c for c in future_categories if remaining_quotas.get(c, 0) > 0]
        if active_future and leftover > 0:
            extra_per = leftover // len(active_future)
            remainder = leftover % len(active_future)
            for i, fc in enumerate(active_future):
                remaining_quotas[fc] = (
                    remaining_quotas.get(fc, 0)
                    + extra_per
                    + (1 if i < remainder else 0)
                )
            print(
                f"   🔄 Категория 'goi' завершилась раньше квоты: +{leftover:,}B перераспределено → {', '.join(active_future)}"
            )

    return stats


def process_hubs(
    hubs_data: dict,
    remaining_quotas: Dict[str, int],
    category_order: List[str],
    current_idx: int,
) -> Dict[str, int]:
    """Обрабатывает хабы."""
    stats = {"md": 0}

    if not isinstance(hubs_data, dict):
        return stats

    budget = remaining_quotas.get("hubs", 0)
    spent = 0

    print(f"   📋 Хабов: {len(hubs_data)}")

    for link, hub in hubs_data.items():
        if spent >= budget or budget <= 0:
            print(f"   ⏹️ Достигнута квота категории ({budget:,} байт)")
            break

        hub_id = sanitize_filename(link)
        md_content = build_hub_markdown(hub)
        save_file("hubs", f"{hub_id}.md", md_content)
        stats["md"] += 1

        meta_json = {
            "type": "hub",
            "title": hub.get("title", hub_id),
            "tags": hub.get("tags", []),
            "references_count": len(hub.get("references", [])),
            "url": hub.get("url", ""),
        }
        meta_str = json.dumps(meta_json, indent=2, ensure_ascii=False)
        save_file("metadata", f"hub_{hub_id}_meta.json", meta_str)

        item_bytes = len(md_content.encode("utf-8")) + len(meta_str.encode("utf-8"))
        spent += item_bytes

    remaining_quotas["hubs"] = max(0, budget - spent)

    total_spent = sum(remaining_quotas.values()) + spent
    if budget > spent and total_spent < TARGET_SIZE_BYTES:
        leftover = budget - spent
        future_categories = category_order[current_idx + 1 :]
        active_future = [c for c in future_categories if remaining_quotas.get(c, 0) > 0]
        if active_future and leftover > 0:
            extra_per = leftover // len(active_future)
            remainder = leftover % len(active_future)
            for i, fc in enumerate(active_future):
                remaining_quotas[fc] = (
                    remaining_quotas.get(fc, 0)
                    + extra_per
                    + (1 if i < remainder else 0)
                )
            print(
                f"   🔄 Категория 'hubs' завершилась раньше квоты: +{leftover:,}B перераспределено → {', '.join(active_future)}"
            )

    return stats


# ═══════════════════════════════════════════════════════════════
# ОСНОВНАЯ ЛОГИКА
# ═══════════════════════════════════════════════════════════════


def _allocate_quotas(target: int, categories: List[str]) -> Dict[str, int]:
    """
    Делит общий целевой объём на категории поровну.
    Возвращает словарь {category: initial_quota_bytes}.
    Все квоты суммируются == target (с округлением).
    """
    increase_for_scp = 2
    base = target // (len(categories) + increase_for_scp)
    remainder = target % len(categories)
    quotas: Dict[str, int] = {}
    for i, cat in enumerate(categories):
        quotas[cat] = base + (1 if i < remainder else 0)
        if cat == "scp":
            quotas[cat] += increase_for_scp * base
    return quotas


def build_dataset() -> Dict:
    """Собирает датасет из реальных данных SCP Wiki."""
    ensure_dirs()

    total_stats = {
        "scp_md": 0,
        "tales_md": 0,
        "goi_md": 0,
        "hubs_md": 0,
        "code_py": 0,
        "code_js": 0,
        "code_ts": 0,
        "meta_files": 0,
        "logs_txt": 0,
    }

    # Категории в порядке обработки
    categories = ["scp", "tales", "goi", "hubs"]

    # Начальные квоты — делим поровну
    quotas = _allocate_quotas(TARGET_SIZE_BYTES, categories)

    # Копия, которую будем мутировать при перераспределении
    remaining = dict(quotas)

    print(
        f"🎯 Целевой объём: {TARGET_SIZE_BYTES:,} bytes ({TARGET_SIZE_BYTES / 1024 / 1024:.1f} MB)"
    )
    print(f"📂 Категории: {', '.join(categories)}")
    print(
        f"   Начальные квоты: {', '.join(f'{c}: {v:,}B ({v/TARGET_SIZE_BYTES*100:.0f}%)' for c, v in quotas.items())}"
    )
    print("=" * 70)

    # === ПРЕДВАРИТЕЛЬНАЯ ЗАГРУЗКА ВСЕХ МЕТАДАННЫХ ===
    # Метаданные — маленькие JSON, загружаем всё сразу чтобы знать размеры категорий
    print("\n📦 Предварительная загрузка метаданных...")

    scp_meta = fetch_json(ENDPOINTS["items_meta"])
    scp_idx = fetch_json(ENDPOINTS["items_content"])
    tales_meta = fetch_json(ENDPOINTS["tales_meta"])
    tales_idx = fetch_json(ENDPOINTS["tales_content"])
    goi_content = fetch_json(ENDPOINTS["goi_content"])
    hubs_data = fetch_json(ENDPOINTS["hubs"])

    print(f"   SCP Items:  {len(scp_meta) if scp_meta else 0} элементов")
    print(f"   Tales:      {len(tales_meta) if tales_meta else 0} элементов")
    print(
        f"   GOI:        {len(goi_content) if isinstance(goi_content, dict) else 0} элементов"
    )
    print(
        f"   Hubs:       {len(hubs_data) if isinstance(hubs_data, dict) else 0} элементов"
    )

    # Удаляем пустые категории из порядка обработки
    active_categories = []
    for cat in categories:
        count = 0
        if cat == "scp" and scp_meta:
            count = len(scp_meta)
        elif cat == "tales" and tales_meta:
            count = len(tales_meta)
        elif cat == "goi" and isinstance(goi_content, dict):
            count = len(goi_content)
        elif cat == "hubs" and isinstance(hubs_data, dict):
            count = len(hubs_data)

        if count == 0:
            # Переносим квоту пустой категории в пул
            if cat in remaining:
                freed = remaining.pop(cat)
                print(
                    f"   ⚠️ Категория '{cat}' пуста — квота {freed:,}B возвращается в пул"
                )

    # Пересчитываем квоты только для активных категорий
    active_cats = list(remaining.keys())
    if len(active_cats) < len(categories):
        new_quotas = _allocate_quotas(sum(remaining.values()), active_cats)
        remaining = new_quotas
        print(
            f"   🔄 Активные квоты: {', '.join(f'{c}: {v:,}B' for c, v in remaining.items())}"
        )

    print(f"   Итого активных: {len(active_cats)} из {len(categories)}")
    print(f"   Текущий размер каталога: {get_dir_size():,} байт")
    print("=" * 70)

    # === ПОКАТЕГОРИЙНАЯ ОБРАБОТКА С ПЕРЕДАЧЕЙ ОСТАТКОВ ===
    processed_order = list(remaining.keys())

    for round_idx, category in enumerate(processed_order):
        if sum(remaining.values()) <= 0:
            print(f"\n⏹️ Все квоты исчерпаны")
            break

        quota = remaining.get(category, 0)
        if quota <= 0:
            print(f"\n⏹️ Квота для '{category}' исчерпана, переходим к следующей")
            continue

        print(f"\n{'='*70}")
        print(
            f"📂 【{round_idx + 1}/{len(processed_order)}】 Категория: {category.upper()}"
        )
        print(
            f"   Квота: {quota:,} байт ({quota/TARGET_SIZE_BYTES*100:.0f}% от общего)"
        )
        print(f"   Остаток всех квот: {sum(remaining.values()):,} байт")
        print(f"{'='*70}")

        if category == "scp":
            if not scp_meta or not scp_idx:
                print("❌ Не удалось загрузить SCP Items")
                continue
            stats = process_items_with_content_index(
                scp_meta,
                scp_idx,
                "scp",
                remaining,
                processed_order,
                round_idx,
            )
            total_stats["scp_md"] = stats.get("md", 0)

        elif category == "tales":
            if not tales_meta or not tales_idx:
                print("❌ Не удалось загрузить Tales")
                continue
            stats = process_items_with_content_index(
                tales_meta,
                tales_idx,
                "tale",
                remaining,
                processed_order,
                round_idx,
            )
            total_stats["tales_md"] = stats.get("md", 0)

        elif category == "goi":
            if not goi_content:
                print("❌ Не удалось загрузить GOI")
                continue
            stats = process_goi(
                goi_content,
                remaining,
                processed_order,
                round_idx,
            )
            total_stats["goi_md"] = stats.get("md", 0)

        elif category == "hubs":
            if not hubs_data:
                print("❌ Не удалось загрузить Hubs")
                continue
            stats = process_hubs(hubs_data, remaining, processed_order, round_idx)
            total_stats["hubs_md"] = stats.get("md", 0)

    # === ИТОГИ ===
    final_size = get_dir_size()
    total_md = (
        total_stats["scp_md"]
        + total_stats["tales_md"]
        + total_stats["goi_md"]
        + total_stats["hubs_md"]
    )
    total_code = (
        total_stats["code_py"] + total_stats["code_js"] + total_stats["code_ts"]
    )

    print("\n" + "=" * 70)
    print("✅ ДАТАСЕТ СОБРАН!")
    print(f"📦 Итоговый размер: {final_size:,} bytes ({final_size / 1024:.1f} KB)")

    print(f"\n📊 Распределение:")
    print(f"   • SCP Items (.md):        {total_stats['scp_md']}")
    print(f"   • Tales (.md):            {total_stats['tales_md']}")
    print(f"   • GOI Formats (.md):      {total_stats['goi_md']}")
    print(f"   • Hubs (.md):             {total_stats['hubs_md']}")
    print(f"   • Всего Markdown:         {total_md}")
    print(f"   • Python (.py):           {total_stats['code_py']}")
    print(f"   • JavaScript (.js):       {total_stats['code_js']}")
    print(f"   • TypeScript (.ts):       {total_stats['code_ts']}")
    print(f"   • Всего кода:             {total_code}")
    print(f"   • Метаданные (.json/.yaml): {total_stats['meta_files']}")
    print(f"   • Логи (.txt):            {total_stats['logs_txt']}")

    return {
        "total_size_bytes": final_size,
        "stats": total_stats,
        "output_dir": str(OUTPUT_DIR),
    }


# ═══════════════════════════════════════════════════════════════
# ТОЧКА ВХОДА
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("SCP Wiki Dataset Builder — Real Data Only")
    print("API: https://scp-data.tedevm.com/")
    print("=" * 70)

    result = build_dataset()

    # Сохраняем итоговые метаданные
    meta = {
        "dataset": {
            "target_size": TARGET_SIZE_BYTES,
            "actual_size": result["total_size_bytes"],
            "actual_kb": round(result["total_size_bytes"] / 1024, 1),
        },
        "files": result["stats"],
        "source": {
            "name": "SCP Foundation Wiki",
            "license": "CC BY-SA 3.0",
            "api": "https://scp-data.tedevm.com/",
        },
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    save_file(
        "metadata", "dataset_info.json", json.dumps(meta, indent=2, ensure_ascii=False)
    )

    print(f"\n💾 Метаданные: {OUTPUT_DIR / 'metadata' / 'dataset_info.json'}")
    print(f"📁 Все файлы: {OUTPUT_DIR}/")
