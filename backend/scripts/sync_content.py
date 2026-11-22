#!/usr/bin/env python3
"""
每 6 小时自动运行的公开题库/词库增量更新脚本
支持两种运行方式：
1. FastAPI 内置 APScheduler 自动调用 run_full_sync()
2. 独立命令行运行（配合 Linux systemd timer: OnUnitActiveSec=6h）：
   python3 backend/scripts/sync_content.py --subject all --batch-size 10

并发安全：
- 严格复用 SQLite WAL 模式 + busy_timeout=5000，写入与前端学生提交零锁库冲突。
- 英语：拉取开源分级词库 -> Free Dictionary API 补全音标与例句 -> 可选 OpenAI 兼容 API 补全课标中文释义与双语例句 -> UNIQUE(grade_stage, word) 去重入库。
- 数学：拉取公开题库 JSON 源（或内建增量变式题池 / 可选 LLM 变式生成）-> SHA-256 content_hash 严格去重入库。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

# 允许直接作为脚本运行
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import config, db, engine  # noqa: E402

logger = logging.getLogger("k12_sync")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# 内建公开课标候选增量词池（当外网受限或作为补充种子时亦可零报错增量入库）
FALLBACK_ENGLISH_CANDIDATES: dict[str, list[dict[str, str]]] = {
    "primary": [
        {"word": "mountain", "meaning": "n. 高山；山脉"},
        {"word": "vegetable", "meaning": "n. 蔬菜"},
        {"word": "birthday", "meaning": "n. 生日"},
        {"word": "calendar", "meaning": "n. 日历"},
    ],
    "grade_7": [
        {"word": "celebrate", "meaning": "v. 庆祝；庆贺"},
        {"word": "neighbor", "meaning": "n. 邻居"},
        {"word": "exercise", "meaning": "n. & v. 锻炼；练习"},
        {"word": "comfortable", "meaning": "adj. 舒适的；安逸的"},
    ],
    "grade_8": [
        {"word": "volunteer", "meaning": "n. 志愿者；v. 自愿做"},
        {"word": "imagine", "meaning": "v. 想象；设想"},
        {"word": "compare", "meaning": "v. 比较；对比"},
        {"word": "develop", "meaning": "v. 发展；培养"},
    ],
    "grade_9": [
        {"word": "appreciate", "meaning": "v. 欣赏；感激"},
        {"word": "confident", "meaning": "adj. 自信的；确信的"},
        {"word": "knowledge", "meaning": "n. 知识；学问"},
        {"word": "purpose", "meaning": "n. 目的；意图"},
    ],
}

# 内建公开人教版/北师大版典型增量数学题池（用于无外部 MATH_SOURCE_URL 时的安全增量演示）
FALLBACK_MATH_CANDIDATES: list[dict[str, Any]] = [
    {
        "grade": "grade_7",
        "topic_tag": "有理数混合运算",
        "question_type": "fill",
        "stem": r"计算：$(-1)^{2024} + (-2)^2 \times \left(-\dfrac{1}{2}\right) =$ ________。",
        "options": [],
        "answer": "-1",
        "analysis": r"第一步：$(-1)^{2024} = 1$，$(-2)^2 = 4$。\n第二步：$4 \times \left(-\dfrac{1}{2}\right) = -2$。\n第三步：$1 + (-2) = -1$。",
    },
    {
        "grade": "grade_8",
        "topic_tag": "一次函数图像与性质",
        "question_type": "choice",
        "stem": r"若点 $A(-2, y_1)$、$B(3, y_2)$ 都在一次函数 $y = -3x + 5$ 的图像上，则 $y_1$ 与 $y_2$ 的大小关系是（  ）",
        "options": [r"A. y_1 > y_2", r"B. y_1 < y_2", r"C. y_1 = y_2", r"D. 无法确定"],
        "answer": "A",
        "analysis": r"一次函数 $y = -3x + 5$ 的斜率 $k = -3 < 0$，故 $y$ 随 $x$ 的增大而减小。\n因为 $-2 < 3$，所以 $y_1 > y_2$，选 **A**。",
    },
    {
        "grade": "grade_9",
        "topic_tag": "一元二次方程根与系数",
        "question_type": "fill",
        "stem": r"已知一元二次方程 $x^2 - 6x + 5 = 0$ 的两根为 $x_1, x_2$，则 $\dfrac{1}{x_1} + \dfrac{1}{x_2} =$ ________。（填分数或小数，如 6/5 或 1.2）",
        "options": [],
        "answer": "6/5|1.2",
        "analysis": r"由韦达定理得 $x_1 + x_2 = 6$，$x_1 x_2 = 5$。\n通分得 $\dfrac{1}{x_1} + \dfrac{1}{x_2} = \dfrac{x_1 + x_2}{x_1 x_2} = \dfrac{6}{5} = 1.2$。",
    },
]


def compute_content_hash(grade: str, stem: str) -> str:
    """标准化数学题干并生成 SHA-256 唯一去重键"""
    normalized = re.sub(r"\s+", "", f"{grade}::{stem}").lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]


def _fetch_free_dictionary(word: str) -> tuple[str, list[dict[str, str]]]:
    """调用 Free Dictionary API 获取音标与英文例句"""
    try:
        import httpx

        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
        resp = httpx.get(url, timeout=6.0)
        if resp.status_code != 200:
            return "", []
        data = resp.json()
        if not isinstance(data, list) or not data:
            return "", []

        entry = data[0]
        phonetic = entry.get("phonetic") or ""
        if not phonetic:
            for ph in entry.get("phonetics", []):
                if ph.get("text"):
                    phonetic = ph["text"]
                    break

        examples: list[dict[str, str]] = []
        for meaning in entry.get("meanings", []):
            for defn in meaning.get("definitions", []):
                ex = defn.get("example")
                if ex:
                    examples.append({"en": ex, "zh": ""})
                if len(examples) >= 2:
                    break
            if len(examples) >= 2:
                break

        return phonetic, examples
    except Exception as exc:
        logger.debug("Free Dictionary API 查询 %s 跳过: %s", word, exc)
        return "", []


def _enrich_english_with_llm(word: str, fallback_meaning: str, examples: list[dict[str, str]]) -> tuple[str, list[dict[str, str]]]:
    """可选：接入兼容 OpenAI 格式的大模型 API 补全课标中文释义与双语例句"""
    if not (config.LLM_API_BASE and config.LLM_API_KEY):
        return fallback_meaning, examples
    try:
        import httpx

        prompt = (
            f"请为中国 K12 学生提供英语单词 '{word}' 的精简课标中文释义（含词性）和 1~2 条常用校园/生活双语例句。"
            "严格返回 JSON 对象：{\"meaning\": \"...\", \"examples\": [{\"en\": \"...\", \"zh\": \"...\"}]}"
        )
        resp = httpx.post(
            f"{config.LLM_API_BASE.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {config.LLM_API_KEY}"},
            json={
                "model": config.LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        meaning = parsed.get("meaning") or fallback_meaning
        llm_examples = parsed.get("examples") or examples
        return meaning, llm_examples[:2]
    except Exception as exc:
        logger.warning("LLM 补全单词 %s 失败，回退基础数据: %s", word, exc)
        return fallback_meaning, examples

KYLEBING_JUNIOR_URL = (
    "https://cdn.jsdelivr.net/gh/KyleBing/english-vocabulary@master/"
    "full_line_jsonl/sentence/%E6%AD%A3%E5%BA%8F/%E5%88%9D%E4%B8%AD.jsonl"
)


def _fetch_open_k12_words() -> dict[str, list[dict[str, Any]]]:
    """从开源 KyleBing/english-vocabulary 拉取初中词库并按词长/序号分配到各学段"""
    buckets: dict[str, list[dict[str, Any]]] = {
        "primary": [], "grade_7": [], "grade_8": [], "grade_9": []
    }
    try:
        import httpx

        resp = httpx.get(KYLEBING_JUNIOR_URL, timeout=60.0, follow_redirects=True)
        resp.raise_for_status()
        lines = resp.text.splitlines()
        stages = ("grade_7", "grade_8", "grade_9")
        for idx, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            word = str(obj.get("word", "")).strip().lower()
            if not word or " " in word or not word.isalpha():
                continue

            trans_parts = []
            for t in obj.get("translations", [])[:3]:
                pos = (t.get("type") or "").strip()
                zh = (t.get("translation") or "").strip()
                if zh:
                    trans_parts.append(f"{pos}. {zh}" if pos else zh)
            meaning = "；".join(trans_parts)
            if not meaning:
                continue

            uk = (obj.get("uk") or obj.get("us") or "").strip()
            phonetic = f"/{uk}/" if uk and not uk.startswith("/") else uk
            examples = [
                {"en": s.get("sentence", ""), "zh": s.get("translation", "")}
                for s in obj.get("sentences", [])[:2]
                if s.get("sentence")
            ]

            # 简单短词优先归入小学补充，其余轮流分配到初一/初二/初三
            target_stage = "primary" if len(word) <= 5 and idx % 4 == 0 else stages[idx % 3]
            buckets[target_stage].append({
                "word": word,
                "phonetic": phonetic,
                "meaning": meaning,
                "examples": examples,
            })
    except Exception as exc:
        logger.warning("拉取开源 K12 词库失败，回退内置候选词: %s", exc)
    return buckets


def sync_english_words(batch_size: int = 30, use_remote_api: bool = True) -> dict[str, int]:
    """英语四学段增量采集、补全与去重入库"""
    added = 0
    skipped = 0

    remote_buckets = _fetch_open_k12_words() if use_remote_api else {}
    # 合并开源词库与内置兜底词
    merged_sources: dict[str, list[dict[str, Any]]] = {}
    for stage in ("primary", "grade_7", "grade_8", "grade_9"):
        merged_sources[stage] = list(FALLBACK_ENGLISH_CANDIDATES.get(stage, [])) + list(remote_buckets.get(stage, []))

    with db.db_session() as conn:
        existing = {
            (r["grade_stage"], r["word"].lower())
            for r in conn.execute("SELECT grade_stage, word FROM english_words").fetchall()
        }

        to_insert: list[tuple[str, str, str, str, str, str]] = []
        for stage, candidates in merged_sources.items():
            for item in candidates:
                if len(to_insert) >= batch_size:
                    break
                word = item["word"].strip().lower()
                if (stage, word) in existing:
                    skipped += 1
                    continue

                phonetic = item.get("phonetic", "")
                examples: list[dict[str, str]] = list(item.get("examples", []))
                if use_remote_api and (not phonetic or not examples):
                    api_ph, api_ex = _fetch_free_dictionary(word)
                    phonetic = phonetic or api_ph
                    examples = examples or api_ex

                meaning, examples = _enrich_english_with_llm(word, item["meaning"], examples)
                if not examples:
                    examples = [{"en": f"Let's learn the word {word} today.", "zh": f"今天我们来学习单词 {word}。"}]

                to_insert.append((
                    stage, word, phonetic, meaning,
                    json.dumps(examples, ensure_ascii=False),
                    "open_k12_sync_6h",
                ))
                existing.add((stage, word))

        if to_insert:
            conn.executemany(
                """
                INSERT OR IGNORE INTO english_words (grade_stage, word, phonetic, meaning, examples, source)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                to_insert,
            )
            added = len(to_insert)

        conn.execute(
            """
            INSERT INTO sync_logs (job_type, added_count, skipped_count, status, detail, finished_at)
            VALUES ('english_sync', ?, ?, 'success', ?, datetime('now', 'localtime'))
            """,
            (added, skipped, f"新增 {added} 词，去重跳过 {skipped} 词"),
        )

    return {"added": added, "skipped": skipped}

"""

def sync_english_words(batch_size: int = 8, use_remote_api: bool = True) -> dict[str, int]:
    added = 0
    skipped = 0

    with db.db_session() as conn:
        existing = {
            (r["grade_stage"], r["word"].lower())
            for r in conn.execute("SELECT grade_stage, word FROM english_words").fetchall()
        }

        to_insert: list[tuple[str, str, str, str, str, str]] = []
        for stage, candidates in FALLBACK_ENGLISH_CANDIDATES.items():
            for item in candidates:
                if len(to_insert) >= batch_size:
                    break
                word = item["word"].strip().lower()
                if (stage, word) in existing:
                    skipped += 1
                    continue

                phonetic = ""
                examples: list[dict[str, str]] = []
                if use_remote_api:
                    phonetic, examples = _fetch_free_dictionary(word)
                meaning, examples = _enrich_english_with_llm(word, item["meaning"], examples)
                if not examples:
                    examples = [{"en": f"Let's learn the word {word} today.", "zh": f"今天我们来学习单词 {word}。"}]

                to_insert.append((
                    stage,
                    word,
                    phonetic,
                    meaning,
                    json.dumps(examples, ensure_ascii=False),
                    "auto_sync_6h",
                ))
                existing.add((stage, word))

        if to_insert:
            conn.executemany(
                INSERT OR IGNORE INTO english_words (grade_stage, word, phonetic, meaning, examples, source)
                VALUES (?, ?, ?, ?, ?, ?)
                to_insert,
            )
            added = len(to_insert)

        conn.execute(
            INSERT INTO sync_logs (job_type, added_count, skipped_count, status, detail, finished_at)
            VALUES ('english_sync', ?, ?, 'success', ?, datetime('now', 'localtime'))
            (added, skipped, f"新增 {added} 词，去重跳过 {skipped} 词"),
        )

    return {"added": added, "skipped": skipped}
"""

def _fetch_remote_math_questions() -> list[dict[str, Any]]:
    """若配置了外部公开题库 JSON 源，则拉取并校验字段"""
    if not config.MATH_SOURCE_URL:
        return []
    try:
        import httpx

        resp = httpx.get(config.MATH_SOURCE_URL, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []
    except Exception as exc:
        logger.warning("拉取外部数学题库源失败: %s", exc)
        return []


def sync_math_questions(use_remote_api: bool = True) -> dict[str, int]:
    """数学三年级增量采集与 SHA-256 content_hash 去重入库"""
    added = 0
    skipped = 0
    candidates = list(FALLBACK_MATH_CANDIDATES)
    if use_remote_api:
        candidates.extend(_fetch_remote_math_questions())

    with db.db_session() as conn:
        existing_hashes = {
            r["content_hash"]
            for r in conn.execute("SELECT content_hash FROM math_questions").fetchall()
        }

        for q in candidates:
            grade = q.get("grade", "")
            if grade not in ("grade_7", "grade_8", "grade_9"):
                continue
            stem = str(q.get("stem", "")).strip()
            if not stem:
                continue
            c_hash = compute_content_hash(grade, stem)
            if c_hash in existing_hashes:
                skipped += 1
                continue

            conn.execute(
                """
                INSERT OR IGNORE INTO math_questions (
                    grade, topic_tag, question_type, stem, options, answer, analysis, content_hash, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'auto_sync_6h')
                """,
                (
                    grade,
                    q.get("topic_tag", "综合巩固"),
                    q.get("question_type", "choice"),
                    stem,
                    json.dumps(q.get("options", []), ensure_ascii=False),
                    str(q.get("answer", "")).strip(),
                    str(q.get("analysis", "")).strip(),
                    c_hash,
                ),
            )
            existing_hashes.add(c_hash)
            added += 1

        conn.execute(
            """
            INSERT INTO sync_logs (job_type, added_count, skipped_count, status, detail, finished_at)
            VALUES ('math_sync', ?, ?, 'success', ?, datetime('now', 'localtime'))
            """,
            (added, skipped, f"新增 {added} 题，哈希去重跳过 {skipped} 题"),
        )

    return {"added": added, "skipped": skipped}


def run_full_sync(batch_size: int = 8, use_remote_api: bool = True) -> dict[str, Any]:
    """执行双科完整增量更新，并定期清理 10 分钟前未提交的无效学习记录"""
    db.init_database()
    en_res = sync_english_words(batch_size=batch_size, use_remote_api=use_remote_api)
    math_res = sync_math_questions(use_remote_api=use_remote_api)
    with db.db_session() as conn:
        cleaned = engine.cleanup_invalid_study_sessions(conn)
    return {"english": en_res, "math": math_res, "cleaned_invalid_sessions": cleaned}


def main() -> None:
    parser = argparse.ArgumentParser(description="K12 英语词库与数学题库每 6 小时增量更新脚本")
    parser.add_argument("--subject", choices=["all", "english", "math"], default="all")
    parser.add_argument("--batch-size", type=int, default=8, help="单次英语增量最大入库词数")
    parser.add_argument("--offline", action="store_true", help="离线模式（不请求外部 HTTP API）")
    args = parser.parse_args()

    db.init_database()
    use_remote = not args.offline

    if args.subject == "english":
        res = sync_english_words(batch_size=args.batch_size, use_remote_api=use_remote)
    elif args.subject == "math":
        res = sync_math_questions(use_remote_api=use_remote)
    else:
        res = run_full_sync(batch_size=args.batch_size, use_remote_api=use_remote)

    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
