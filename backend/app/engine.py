"""
全科目共享核心学习引擎（英语与数学 100% 统一调度）
- 6位推荐码准入与多端档案隔离
- 30分钟硬计时（expires_at = started_at + 1800），重学不重置时间，超时作废
- 双科专属抽题算法（英语三阶 6/3/1 动态补足；数学优先未做/错题）
- 必须全对才算过关，错题记录首次错项供个人中心标红
- 双科共享总积分（保底 0），每自然日每科首次全对通关额外 +5 分
- 英语三阶掌握度升降级状态机
- 个人中心只读复习档案
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import random
import re
import sqlite3
import time
from typing import Any
import uuid

from . import config

REFERRAL_CODE_PATTERN = re.compile(r"^[A-Za-z0-9]{6}$")
CN_PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")

VALID_ENGLISH_STAGES = {"primary", "grade_7", "grade_8", "grade_9"}
VALID_MATH_GRADES = {"grade_7", "grade_8", "grade_9"}


def local_today_str(now_ts: int | None = None) -> str:
    """获取当前自然日 YYYY-MM-DD（按配置时区，默认东八区）"""
    tz = timezone(timedelta(hours=config.LOCAL_TZ_OFFSET_HOURS))
    dt = datetime.fromtimestamp(now_ts if now_ts is not None else time.time(), tz=tz)
    return dt.strftime("%Y-%m-%d")


def now_epoch() -> int:
    return int(time.time())


def is_admin_code(raw_code: str | None) -> bool:
    return bool(config.ADMIN_REFERRAL_CODE) and (raw_code or "").strip().upper() == config.ADMIN_REFERRAL_CODE

# ============================================================================
# 1. 推荐码准入与用户档案
# ============================================================================

def verify_or_create_user(conn: sqlite3.Connection, raw_code: str) -> dict[str, Any]:
    """校验 6 位推荐码并返回用户档案"""
    code = (raw_code or "").strip().upper()
    if not config.ALLOW_AUTO_PROVISION and not is_admin_code(code):
        raise ValueError("推荐码无效或未授权，请联系管理员")

    row = conn.execute(
        "SELECT referral_code, phone, total_points, is_active FROM users WHERE referral_code = ?",
        (code,),
    ).fetchone()

    if row is None:
        if not config.ALLOW_AUTO_PROVISION:
            raise PermissionError("推荐码无效或未授权，请联系管理员")
        conn.execute(
            "INSERT INTO users (referral_code, total_points) VALUES (?, 0)",
            (code,),
        )
        row = conn.execute(
            "SELECT referral_code, phone, total_points, is_active FROM users WHERE referral_code = ?",
            (code,),
        ).fetchone()

    if not row["is_active"]:
        raise PermissionError("该推荐码已停用")

    return get_user_profile(conn, code)


def ensure_valid_referral_code(conn: sqlite3.Connection, raw_code: str | None) -> str:
    """业务接口强制推荐码鉴权（严禁未校验拉取题库或进入学习）"""
    code = (raw_code or "").strip().upper()
    if not REFERRAL_CODE_PATTERN.match(code):
        raise PermissionError("缺少或无效的 6 位推荐码授权头 (X-Referral-Code)")
    row = conn.execute(
        "SELECT referral_code, is_active FROM users WHERE referral_code = ?",
        (code,),
    ).fetchone()
    if row is None or not row["is_active"]:
        raise PermissionError("推荐码未激活或不存在，请先完成准入校验")
    return code


def get_user_profile(conn: sqlite3.Connection, referral_code: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT referral_code, phone, total_points FROM users WHERE referral_code = ?",
        (referral_code,),
    ).fetchone()
    if row is None:
        raise PermissionError("用户档案不存在")

    today = local_today_str()
    rewards = conn.execute(
        "SELECT subject FROM daily_pass_rewards WHERE referral_code = ? AND reward_date = ?",
        (referral_code, today),
    ).fetchall()
    passed_subjects = {r["subject"] for r in rewards}

    return {
        "referral_code": row["referral_code"],
        "phone": row["phone"],
        "total_points": row["total_points"],
        "today_english_passed": "english" in passed_subjects,
        "today_math_passed": "math" in passed_subjects,
        "is_admin": is_admin_code(row["referral_code"]),
        "server_now": now_epoch(),
    }


def bind_user_phone(conn: sqlite3.Connection, referral_code: str, phone: str) -> dict[str, Any]:
    """免验证码直绑 11 位中国大陆手机号"""
    cleaned = (phone or "").strip()
    if not CN_PHONE_PATTERN.match(cleaned):
        raise ValueError("请输入有效的 11 位中国大陆手机号（^1[3-9]\\d{9}$）")

    conn.execute(
        "UPDATE users SET phone = ?, updated_at = datetime('now', 'localtime') WHERE referral_code = ?",
        (cleaned, referral_code),
    )
    return get_user_profile(conn, referral_code)


def _apply_points(
    conn: sqlite3.Connection,
    referral_code: str,
    delta: int,
    subject: str,
    session_id: str | None,
    reason: str,
) -> tuple[int, int]:
    """统一积分结算：总分保底为 0，绝不出现负数，写入流水表"""
    row = conn.execute(
        "SELECT total_points FROM users WHERE referral_code = ?",
        (referral_code,),
    ).fetchone()
    current = int(row["total_points"])
    new_balance = max(0, current + delta)
    actual_delta = new_balance - current

    conn.execute(
        "UPDATE users SET total_points = ?, updated_at = datetime('now', 'localtime') WHERE referral_code = ?",
        (new_balance, referral_code),
    )
    conn.execute(
        """
        INSERT INTO point_ledger (referral_code, session_id, subject, delta, balance_after, reason)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (referral_code, session_id, subject, actual_delta, new_balance, reason),
    )
    return actual_delta, new_balance


# ============================================================================
# 2. 双科专属抽题算法
# ============================================================================

def _weighted_sample_without_replacement(
    items: list[dict[str, Any]],
    weights: list[float],
    k: int,
) -> list[dict[str, Any]]:
    """无放回加权抽样（用于二级巩固词 60% 权重倾向低 streak/错词）"""
    if k <= 0 or not items:
        return []
    k = min(k, len(items))
    pool = list(items)
    w_pool = list(weights)
    chosen: list[dict[str, Any]] = []
    for _ in range(k):
        total_w = sum(w_pool)
        if total_w <= 0:
            idx = random.randrange(len(pool))
        else:
            r = random.uniform(0, total_w)
            acc = 0.0
            idx = len(pool) - 1
            for i, w in enumerate(w_pool):
                acc += w
                if r <= acc:
                    idx = i
                    break
        chosen.append(pool.pop(idx))
        w_pool.pop(idx)
    return chosen


def draw_english_words(
    conn: sqlite3.Connection,
    referral_code: str,
    grade_stage: str,
    count: int = config.ENGLISH_ROUND_SIZE,
) -> list[dict[str, Any]]:
    """
    英语三阶动态抽词算法：
    标准配比：一级新词 6 个 + 二级巩固词(60%权重倾向易错/低streak) 3 个 + 三级熟练词 1 个
    某级别不足时自动从其他级别动态补足 count 个不重复单词
    """
    if grade_stage not in VALID_ENGLISH_STAGES:
        raise ValueError(f"不支持的英语学段: {grade_stage}")

    rows = conn.execute(
        """
        SELECT w.id, w.grade_stage, w.word, w.phonetic, w.meaning, w.examples,
               COALESCE(p.mastery_level, 1) AS mastery_level,
               COALESCE(p.streak, 0) AS streak,
               COALESCE(p.wrong_count, 0) AS wrong_count
        FROM english_words w
        LEFT JOIN user_english_progress p
               ON p.word_id = w.id AND p.referral_code = ?
        WHERE w.grade_stage = ?
        """,
        (referral_code, grade_stage),
    ).fetchall()

    if len(rows) < count:
        raise ValueError(f"学段 {grade_stage} 词库数量不足 {count} 个（当前仅 {len(rows)} 个）")

    level1, level2, level3 = [], [], []
    for r in rows:
        item = {
            "id": r["id"],
            "grade_stage": r["grade_stage"],
            "word": r["word"],
            "phonetic": r["phonetic"],
            "meaning": r["meaning"],
            "examples": json.loads(r["examples"] or "[]"),
            "mastery_level": r["mastery_level"],
            "streak": r["streak"],
            "wrong_count": r["wrong_count"],
        }
        if item["mastery_level"] == 1:
            level1.append(item)
        elif item["mastery_level"] == 2:
            level2.append(item)
        else:
            level3.append(item)

    random.shuffle(level1)
    random.shuffle(level3)

    # 目标配比 6 / 3 / 1
    picked_l1 = level1[:6]
    # 二级词库按权重抽 3 个：历史出错越多、streak 越低权重越高（基数 0.6 加权）
    l2_weights = [0.6 * (1.0 + item["wrong_count"] * 0.8 + max(0, 3 - item["streak"]) * 0.5) for item in level2]
    picked_l2 = _weighted_sample_without_replacement(level2, l2_weights, 3)
    picked_l3 = level3[:1]

    selected = picked_l1 + picked_l2 + picked_l3
    selected_ids = {x["id"] for x in selected}

    # 若不足 count 个，按 1级 -> 2级 -> 3级 顺序动态补足
    if len(selected) < count:
        remaining = [
            x for x in (level1 + level2 + level3)
            if x["id"] not in selected_ids
        ]
        random.shuffle(remaining)
        need = count - len(selected)
        selected.extend(remaining[:need])

    random.shuffle(selected)
    return selected[:count]


def draw_math_questions(
    conn: sqlite3.Connection,
    referral_code: str,
    grade: str,
    count: int = config.MATH_ROUND_SIZE,
) -> list[dict[str, Any]]:
    """
    数学分年级抽题规则：
    每次随机抽取 3 道典型题，优先抽取未做过或历史错题本中的题目，尽量覆盖不同考点标签
    """
    if grade not in VALID_MATH_GRADES:
        raise ValueError(f"不支持的数学年级: {grade}")

    rows = conn.execute(
        """
        SELECT q.id, q.grade, q.topic_tag, q.question_type, q.stem, q.options, q.answer, q.analysis,
               COALESCE(p.attempt_count, 0) AS attempt_count,
               COALESCE(p.is_in_wrong_book, 0) AS is_in_wrong_book
        FROM math_questions q
        LEFT JOIN user_math_progress p
               ON p.question_id = q.id AND p.referral_code = ?
        WHERE q.grade = ?
        """,
        (referral_code, grade),
    ).fetchall()

    if len(rows) < count:
        raise ValueError(f"年级 {grade} 数学题库数量不足 {count} 道（当前仅 {len(rows)} 道）")

    priority_pool = []  # 未做过 或 错题本中
    normal_pool = []    # 已做对的常规题
    for r in rows:
        item = {
            "id": r["id"],
            "grade": r["grade"],
            "topic_tag": r["topic_tag"],
            "question_type": r["question_type"],
            "stem": r["stem"],
            "options": json.loads(r["options"] or "[]"),
            "answer": r["answer"],
            "analysis": r["analysis"],
            "is_in_wrong_book": bool(r["is_in_wrong_book"]),
        }
        if r["attempt_count"] == 0 or r["is_in_wrong_book"] == 1:
            priority_pool.append(item)
        else:
            normal_pool.append(item)

    random.shuffle(priority_pool)
    random.shuffle(normal_pool)

    # 优先挑不同 topic_tag，提升每日三题考点覆盖度
    selected: list[dict[str, Any]] = []
    used_tags: set[str] = set()
    used_ids: set[int] = set()

    for pool in (priority_pool, normal_pool):
        for q in pool:
            if len(selected) >= count:
                break
            if q["id"] not in used_ids and q["topic_tag"] not in used_tags:
                selected.append(q)
                used_tags.add(q["topic_tag"])
                used_ids.add(q["id"])

    if len(selected) < count:
        for pool in (priority_pool, normal_pool):
            for q in pool:
                if len(selected) >= count:
                    break
                if q["id"] not in used_ids:
                    selected.append(q)
                    used_ids.add(q["id"])

    return selected[:count]


# ============================================================================
# 3. 共享学习批次引擎（开局计时、校验提交、超时作废、全对通关）
# ============================================================================

def _load_session_items(
    conn: sqlite3.Connection,
    subject: str,
    item_ids: list[int],
    include_answers: bool = False,
) -> list[dict[str, Any]]:
    """按原顺序加载本轮批次的题目/单词列表"""
    if not item_ids:
        return []
    placeholders = ",".join("?" for _ in item_ids)
    if subject == "english":
        rows = conn.execute(
            f"SELECT id, grade_stage, word, phonetic, meaning, examples FROM english_words WHERE id IN ({placeholders})",
            item_ids,
        ).fetchall()
        by_id = {
            r["id"]: {
                "id": r["id"],
                "grade_stage": r["grade_stage"],
                "word": r["word"],
                "phonetic": r["phonetic"],
                "meaning": r["meaning"],
                "examples": json.loads(r["examples"] or "[]"),
            }
            for r in rows
        }
    else:
        rows = conn.execute(
            f"SELECT id, grade, topic_tag, question_type, stem, options, answer, analysis FROM math_questions WHERE id IN ({placeholders})",
            item_ids,
        ).fetchall()
        by_id = {}
        for r in rows:
            obj: dict[str, Any] = {
                "id": r["id"],
                "grade": r["grade"],
                "topic_tag": r["topic_tag"],
                "question_type": r["question_type"],
                "stem": r["stem"],
                "options": json.loads(r["options"] or "[]"),
            }
            if include_answers:
                obj["answer"] = r["answer"]
                obj["analysis"] = r["analysis"]
            by_id[r["id"]] = obj

    return [by_id[i] for i in item_ids if i in by_id]


def start_study_session(
    conn: sqlite3.Connection,
    referral_code: str,
    subject: str,
    stage_or_grade: str,
    now_ts: int | None = None,
) -> dict[str, Any]:
    """创建新学习批次，后端写入绝对截止时间 expires_at = started_at + 1800"""
    current_ts = now_ts if now_ts is not None else now_epoch()
    expires_ts = current_ts + config.SESSION_TOTAL_SECONDS

    if subject == "english":
        drawn = draw_english_words(conn, referral_code, stage_or_grade, config.ENGLISH_ROUND_SIZE)
    elif subject == "math":
        drawn = draw_math_questions(conn, referral_code, stage_or_grade, config.MATH_ROUND_SIZE)
    else:
        raise ValueError(f"不支持的科目: {subject}")

    item_ids = [item["id"] for item in drawn]
    session_id = str(uuid.uuid4())
    created_date = local_today_str(current_ts)

    conn.execute(
        """
        INSERT INTO study_sessions (
            id, referral_code, subject, stage_or_grade, item_ids,
            status, started_at, expires_at, created_date
        ) VALUES (?, ?, ?, ?, ?, 'in_progress', ?, ?, ?)
        """,
        (
            session_id,
            referral_code,
            subject,
            stage_or_grade,
            json.dumps(item_ids),
            current_ts,
            expires_ts,
            created_date,
        ),
    )

    # 数学题目不提前下发标答与解析（防止作弊，提交后按错题/通关返回）
    safe_items = _load_session_items(conn, subject, item_ids, include_answers=False)

    return {
        "session_id": session_id,
        "subject": subject,
        "stage_or_grade": stage_or_grade,
        "status": "in_progress",
        "started_at": current_ts,
        "expires_at": expires_ts,
        "server_now": current_ts,
        "remaining_seconds": config.SESSION_TOTAL_SECONDS,
        "stealth_hide_threshold": config.STEALTH_HIDE_THRESHOLD_SECONDS,
        "urgent_pulse_threshold": config.URGENT_PULSE_THRESHOLD_SECONDS,
        "items": safe_items,
    }


def _normalize_math_answer(ans: str) -> str:
    """标准化数学答案：去首尾空格、统一大小写与常见符号空格"""
    return re.sub(r"\s+", "", (ans or "").strip()).upper()


def _check_math_answer(expected: str, user_input: str) -> bool:
    """支持多等价答案（用 | 分隔）的严格比对"""
    norm_user = _normalize_math_answer(user_input)
    if not norm_user:
        return False
    candidates = [_normalize_math_answer(c) for c in expected.split("|")]
    return norm_user in candidates


def _update_english_mastery_on_attempt(
    conn: sqlite3.Connection,
    referral_code: str,
    item_ids: list[int],
    wrong_id_set: set[int],
    is_final_pass: bool,
) -> None:
    """
    英语三阶掌握度状态机：
    - 复核拼写错误：二级或三级词 streak 清零并降级/留在二级（一级词保持一级）
    - 全对过关时（且仅在未超时通关时触发晋升）：
      - 一级词 -> 晋升二级，streak = 1
      - 二级词 -> streak += 1，若 streak >= 3 晋升三级
      - 三级词 -> streak += 1，保持三级
    """
    for wid in item_ids:
        row = conn.execute(
            "SELECT mastery_level, streak, wrong_count FROM user_english_progress WHERE referral_code = ? AND word_id = ?",
            (referral_code, wid),
        ).fetchone()
        level = row["mastery_level"] if row else 1
        streak = row["streak"] if row else 0
        wrong_count = row["wrong_count"] if row else 0

        if wid in wrong_id_set:
            wrong_count += 1
            streak = 0
            if level in (2, 3):
                level = 2  # 二级或三级词答错，降级/留在二级
        elif is_final_pass:
            if level == 1:
                level = 2
                streak = 1
            elif level == 2:
                streak += 1
                if streak >= 3:
                    level = 3
            else:
                streak += 1

        conn.execute(
            """
            INSERT INTO user_english_progress (referral_code, word_id, mastery_level, streak, wrong_count, last_reviewed_at, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))
            ON CONFLICT(referral_code, word_id) DO UPDATE SET
                mastery_level = excluded.mastery_level,
                streak = excluded.streak,
                wrong_count = excluded.wrong_count,
                last_reviewed_at = excluded.last_reviewed_at,
                updated_at = excluded.updated_at
            """,
            (referral_code, wid, level, streak, wrong_count),
        )


def _update_math_progress_on_attempt(
    conn: sqlite3.Connection,
    referral_code: str,
    details: list[dict[str, Any]],
) -> None:
    """更新数学做题记录与错题本"""
    for d in details:
        qid = d["question_id"]
        is_correct = d["is_correct"]
        row = conn.execute(
            "SELECT attempt_count, correct_count, wrong_count, is_in_wrong_book FROM user_math_progress WHERE referral_code = ? AND question_id = ?",
            (referral_code, qid),
        ).fetchone()
        attempt_c = (row["attempt_count"] if row else 0) + 1
        correct_c = (row["correct_count"] if row else 0) + (1 if is_correct else 0)
        wrong_c = (row["wrong_count"] if row else 0) + (0 if is_correct else 1)
        # 答错过就进入错题本供只读复盘
        in_wrong = 1 if (not is_correct or (row and row["is_in_wrong_book"] == 1)) else 0
        last_wrong = None if is_correct else d["user_input"]

        conn.execute(
            """
            INSERT INTO user_math_progress (
                referral_code, question_id, attempt_count, correct_count, wrong_count,
                is_in_wrong_book, last_wrong_answer, last_attempted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
            ON CONFLICT(referral_code, question_id) DO UPDATE SET
                attempt_count = excluded.attempt_count,
                correct_count = excluded.correct_count,
                wrong_count = excluded.wrong_count,
                is_in_wrong_book = excluded.is_in_wrong_book,
                last_wrong_answer = COALESCE(excluded.last_wrong_answer, user_math_progress.last_wrong_answer),
                last_attempted_at = excluded.last_attempted_at
            """,
            (referral_code, qid, attempt_c, correct_c, wrong_c, in_wrong, last_wrong),
        )


def submit_study_session(
    conn: sqlite3.Connection,
    referral_code: str,
    session_id: str,
    answers: list[dict[str, Any]],
    now_ts: int | None = None,
) -> dict[str, Any]:
    """
    共享提交与校验引擎：
    1. 检查会话归属与状态
    2. 后端硬计时校验：若 now_ts > expires_at，判定超时作废（expired），不晋升、不发通关积分
    3. 核对双科答案并即时算分（英语 +1/-1，数学 +2/-1，总分保底 0）
    4. 若有错：保留 in_progress 状态且 expires_at 绝不重置，返回错题详情/解析供“重新学习本组”
    5. 若全对：标记 passed，触发熟练度晋升与每日首次通关 +5 分奖励
    """
    current_ts = now_ts if now_ts is not None else now_epoch()
    session = conn.execute(
        "SELECT * FROM study_sessions WHERE id = ? AND referral_code = ?",
        (session_id, referral_code),
    ).fetchone()
    if session is None:
        raise ValueError("学习批次不存在或无权访问")

    if session["status"] == "passed":
        raise ValueError("本轮学习已通关，请勿重复提交")
    if session["status"] == "expired":
        raise ValueError("本轮学习已超时作废，请重新开启新批次")

    # 后端硬计时超时判定
    if current_ts > int(session["expires_at"]):
        duration = current_ts - int(session["started_at"])
        conn.execute(
            """
            UPDATE study_sessions
            SET status = 'expired', completed_at = ?, duration_sec = ?
            WHERE id = ?
            """,
            (current_ts, duration, session_id),
        )
        profile = get_user_profile(conn, referral_code)
        return {
            "session_id": session_id,
            "subject": session["subject"],
            "status": "expired",
            "is_expired": True,
            "all_correct": False,
            "message": "超时未完成，本次成绩作废",
            "score_delta": 0,
            "daily_bonus": 0,
            "total_points": profile["total_points"],
            "remaining_seconds": 0,
            "expires_at": int(session["expires_at"]),
            "server_now": current_ts,
            "results": [],
        }

    subject = session["subject"]
    item_ids: list[int] = json.loads(session["item_ids"])
    attempt_count = int(session["attempt_count"]) + 1
    first_wrong_ids: list[int] = json.loads(session["first_wrong_ids"] or "[]")

    results: list[dict[str, Any]] = []
    wrong_ids: list[int] = []
    correct_count = 0
    wrong_count = 0

    if subject == "english":
        ans_map = {int(a["word_id"]): str(a.get("user_input", "")) for a in answers if "word_id" in a}
        words = _load_session_items(conn, "english", item_ids, include_answers=True)
        for w in words:
            user_in = ans_map.get(w["id"], "").strip()
            is_correct = user_in.lower() == w["word"].strip().lower()
            if is_correct:
                correct_count += 1
            else:
                wrong_count += 1
                wrong_ids.append(w["id"])
            results.append({
                "word_id": w["id"],
                "word": w["word"],
                "phonetic": w["phonetic"],
                "meaning": w["meaning"],
                "examples": w["examples"],
                "user_input": user_in,
                "is_correct": is_correct,
            })
        raw_delta = correct_count * config.ENGLISH_POINTS_CORRECT + wrong_count * config.ENGLISH_POINTS_WRONG
    else:
        ans_map = {int(a["question_id"]): str(a.get("user_input", "")) for a in answers if "question_id" in a}
        questions = _load_session_items(conn, "math", item_ids, include_answers=True)
        for q in questions:
            user_in = ans_map.get(q["id"], "").strip()
            is_correct = _check_math_answer(q["answer"], user_in)
            if is_correct:
                correct_count += 1
            else:
                wrong_count += 1
                wrong_ids.append(q["id"])
            results.append({
                "question_id": q["id"],
                "topic_tag": q["topic_tag"],
                "question_type": q["question_type"],
                "stem": q["stem"],
                "options": q["options"],
                "correct_answer": q["answer"],
                "analysis": q["analysis"],
                "user_input": user_in,
                "is_correct": is_correct,
            })
        raw_delta = correct_count * config.MATH_POINTS_CORRECT + wrong_count * config.MATH_POINTS_WRONG

    # 首次提交记录错题 ID，用于个人中心历史标红
    if attempt_count == 1:
        first_wrong_ids = list(wrong_ids)

    all_correct = (wrong_count == 0 and correct_count == len(item_ids))

    # 单次作答即时算分（保底为 0）
    actual_delta, new_balance = _apply_points(
        conn,
        referral_code,
        raw_delta,
        subject,
        session_id,
        f"{'英语背词' if subject == 'english' else '数学精练'}第{attempt_count}次提交（对{correct_count}错{wrong_count}）",
    )

    # 更新掌握度 / 错题本
    if subject == "english":
        _update_english_mastery_on_attempt(
            conn, referral_code, item_ids, set(wrong_ids), is_final_pass=all_correct
        )
    else:
        _update_math_progress_on_attempt(conn, referral_code, results)

    daily_bonus = 0
    new_status = "in_progress"
    completed_at = None
    duration_sec = None

    if all_correct:
        new_status = "passed"
        completed_at = current_ts
        duration_sec = max(1, current_ts - int(session["started_at"]))
        today = local_today_str(current_ts)

        # 检查今日该科目是否已领过 +5 分每日通关奖励
        existing_bonus = conn.execute(
            "SELECT id FROM daily_pass_rewards WHERE referral_code = ? AND subject = ? AND reward_date = ?",
            (referral_code, subject, today),
        ).fetchone()
        if existing_bonus is None:
            conn.execute(
                """
                INSERT INTO daily_pass_rewards (referral_code, subject, reward_date, session_id, points)
                VALUES (?, ?, ?, ?, ?)
                """,
                (referral_code, subject, today, session_id, config.DAILY_FIRST_PASS_BONUS),
            )
            daily_bonus, new_balance = _apply_points(
                conn,
                referral_code,
                config.DAILY_FIRST_PASS_BONUS,
                subject,
                session_id,
                f"{today} {'英语' if subject == 'english' else '数学'}每日首次全对通关奖励",
            )

    total_session_delta = int(session["total_score_delta"]) + actual_delta + daily_bonus
    conn.execute(
        """
        UPDATE study_sessions
        SET attempt_count = ?,
            first_wrong_ids = ?,
            latest_wrong_ids = ?,
            status = ?,
            completed_at = COALESCE(?, completed_at),
            duration_sec = COALESCE(?, duration_sec),
            total_score_delta = ?,
            daily_bonus_awarded = CASE WHEN ? > 0 THEN 1 ELSE daily_bonus_awarded END
        WHERE id = ?
        """,
        (
            attempt_count,
            json.dumps(first_wrong_ids),
            json.dumps(wrong_ids),
            new_status,
            completed_at,
            duration_sec,
            total_session_delta,
            daily_bonus,
            session_id,
        ),
    )

    remaining_sec = max(0, int(session["expires_at"]) - current_ts)
    return {
        "session_id": session_id,
        "subject": subject,
        "status": new_status,
        "is_expired": False,
        "all_correct": all_correct,
        "attempt_count": attempt_count,
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "raw_score_delta": raw_delta,
        "score_delta": actual_delta,
        "daily_bonus": daily_bonus,
        "total_points": new_balance,
        "duration_sec": duration_sec,
        "expires_at": int(session["expires_at"]),
        "server_now": current_ts,
        "remaining_seconds": remaining_sec,
        "results": results,
    }


def expire_session_if_needed(
    conn: sqlite3.Connection,
    referral_code: str,
    session_id: str,
    now_ts: int | None = None,
) -> dict[str, Any]:
    """前端倒计时归零或轮询时主动触发超时作废落库"""
    current_ts = now_ts if now_ts is not None else now_epoch()
    session = conn.execute(
        "SELECT * FROM study_sessions WHERE id = ? AND referral_code = ?",
        (session_id, referral_code),
    ).fetchone()
    if session is None:
        raise ValueError("学习批次不存在")

    status = session["status"]
    if status == "in_progress" and current_ts >= int(session["expires_at"]):
        duration = current_ts - int(session["started_at"])
        conn.execute(
            "UPDATE study_sessions SET status = 'expired', completed_at = ?, duration_sec = ? WHERE id = ?",
            (current_ts, duration, session_id),
        )
        status = "expired"

    return {
        "session_id": session_id,
        "status": status,
        "expires_at": int(session["expires_at"]),
        "server_now": current_ts,
        "remaining_seconds": max(0, int(session["expires_at"]) - current_ts),
    }


# ============================================================================
# 4. 个人中心：双科只读复习档案（严禁复核测试与计分）
# ============================================================================

def get_english_readonly_archive(
    conn: sqlite3.Connection,
    referral_code: str,
    grade_stage: str | None = None,
) -> dict[str, Any]:
    """获取英语历史批次（含耗时、首次错词标红）与一/二/三级词库只读清单"""
    params: list[Any] = [referral_code]
    stage_filter = ""
    if grade_stage and grade_stage in VALID_ENGLISH_STAGES:
        stage_filter = " AND stage_or_grade = ?"
        params.append(grade_stage)

    session_rows = conn.execute(
        f"""
        SELECT id, stage_or_grade, item_ids, first_wrong_ids, status,
               started_at, completed_at, duration_sec, attempt_count,
               total_score_delta, daily_bonus_awarded, created_date
        FROM study_sessions
        WHERE referral_code = ? AND subject = 'english'{stage_filter}
        ORDER BY started_at DESC
        LIMIT 30
        """,
        params,
    ).fetchall()

    history = []
    for s in session_rows:
        item_ids = json.loads(s["item_ids"] or "[]")
        first_wrong_set = set(json.loads(s["first_wrong_ids"] or "[]"))
        words = _load_session_items(conn, "english", item_ids, include_answers=True)
        for w in words:
            w["first_wrong"] = w["id"] in first_wrong_set
        history.append({
            "session_id": s["id"],
            "grade_stage": s["stage_or_grade"],
            "status": s["status"],
            "started_at": s["started_at"],
            "completed_at": s["completed_at"],
            "duration_sec": s["duration_sec"],
            "attempt_count": s["attempt_count"],
            "total_score_delta": s["total_score_delta"],
            "daily_bonus_awarded": bool(s["daily_bonus_awarded"]),
            "created_date": s["created_date"],
            "words": words,
        })

    # 按学段查询一/二/三级词库清单（只读卡片数据）
    word_params: list[Any] = [referral_code]
    w_stage_filter = ""
    if grade_stage and grade_stage in VALID_ENGLISH_STAGES:
        w_stage_filter = " WHERE w.grade_stage = ?"
        word_params.append(grade_stage)

    word_rows = conn.execute(
        f"""
        SELECT w.id, w.grade_stage, w.word, w.phonetic, w.meaning, w.examples,
               COALESCE(p.mastery_level, 1) AS mastery_level,
               COALESCE(p.streak, 0) AS streak,
               COALESCE(p.wrong_count, 0) AS wrong_count
        FROM english_words w
        LEFT JOIN user_english_progress p
               ON p.word_id = w.id AND p.referral_code = ?
        {w_stage_filter}
        ORDER BY mastery_level DESC, w.id ASC
        """,
        word_params,
    ).fetchall()

    tiers: dict[str, list[dict[str, Any]]] = {"level_1": [], "level_2": [], "level_3": []}
    for r in word_rows:
        obj = {
            "id": r["id"],
            "grade_stage": r["grade_stage"],
            "word": r["word"],
            "phonetic": r["phonetic"],
            "meaning": r["meaning"],
            "examples": json.loads(r["examples"] or "[]"),
            "mastery_level": r["mastery_level"],
            "streak": r["streak"],
            "wrong_count": r["wrong_count"],
            "readonly": True,
        }
        tiers[f"level_{r['mastery_level']}"].append(obj)

    return {
        "readonly": True,
        "history": history,
        "tiers": tiers,
    }


def get_math_readonly_archive(
    conn: sqlite3.Connection,
    referral_code: str,
    grade: str | None = None,
) -> dict[str, Any]:
    """获取数学历史 3 题批次与错题本（含完整 LaTeX 分步解析，严格只读）"""
    params: list[Any] = [referral_code]
    grade_filter = ""
    if grade and grade in VALID_MATH_GRADES:
        grade_filter = " AND stage_or_grade = ?"
        params.append(grade)

    session_rows = conn.execute(
        f"""
        SELECT id, stage_or_grade, item_ids, first_wrong_ids, status,
               started_at, completed_at, duration_sec, attempt_count,
               total_score_delta, daily_bonus_awarded, created_date
        FROM study_sessions
        WHERE referral_code = ? AND subject = 'math'{grade_filter}
        ORDER BY started_at DESC
        LIMIT 30
        """,
        params,
    ).fetchall()

    history = []
    for s in session_rows:
        item_ids = json.loads(s["item_ids"] or "[]")
        first_wrong_set = set(json.loads(s["first_wrong_ids"] or "[]"))
        questions = _load_session_items(conn, "math", item_ids, include_answers=True)
        for q in questions:
            q["first_wrong"] = q["id"] in first_wrong_set
            q["readonly"] = True
        history.append({
            "session_id": s["id"],
            "grade": s["stage_or_grade"],
            "status": s["status"],
            "started_at": s["started_at"],
            "completed_at": s["completed_at"],
            "duration_sec": s["duration_sec"],
            "attempt_count": s["attempt_count"],
            "total_score_delta": s["total_score_delta"],
            "daily_bonus_awarded": bool(s["daily_bonus_awarded"]),
            "created_date": s["created_date"],
            "questions": questions,
        })

    # 错题本列表
    wb_params: list[Any] = [referral_code]
    wb_grade_filter = ""
    if grade and grade in VALID_MATH_GRADES:
        wb_grade_filter = " AND q.grade = ?"
        wb_params.append(grade)

    wrong_rows = conn.execute(
        f"""
        SELECT q.id, q.grade, q.topic_tag, q.question_type, q.stem, q.options, q.answer, q.analysis,
               p.wrong_count, p.last_wrong_answer, p.last_attempted_at
        FROM user_math_progress p
        JOIN math_questions q ON q.id = p.question_id
        WHERE p.referral_code = ? AND p.is_in_wrong_book = 1{wb_grade_filter}
        ORDER BY p.last_attempted_at DESC
        """,
        wb_params,
    ).fetchall()

    wrong_book = [
        {
            "id": r["id"],
            "grade": r["grade"],
            "topic_tag": r["topic_tag"],
            "question_type": r["question_type"],
            "stem": r["stem"],
            "options": json.loads(r["options"] or "[]"),
            "answer": r["answer"],
            "analysis": r["analysis"],
            "wrong_count": r["wrong_count"],
            "last_wrong_answer": r["last_wrong_answer"],
            "last_attempted_at": r["last_attempted_at"],
            "readonly": True,
        }
        for r in wrong_rows
    ]

    return {
        "readonly": True,
        "history": history,
        "wrong_book": wrong_book,
    }


def get_admin_daily_records(
    conn: sqlite3.Connection,
    date_str: str | None = None,
    target_code: str | None = None,
    subject: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """隐藏推荐码专用：查看所有使用者的每日学习批次、抽题明细、复核结果与耗时"""
    conditions = ["s.referral_code != ?"]
    params: list[Any] = [config.ADMIN_REFERRAL_CODE]

    if date_str:
        conditions.append("s.created_date = ?")
        params.append(date_str.strip())
    if target_code:
        conditions.append("s.referral_code = ?")
        params.append(target_code.strip().upper())
    if subject in ("english", "math"):
        conditions.append("s.subject = ?")
        params.append(subject)

    where_sql = " AND ".join(conditions)
    params.append(limit)

    rows = conn.execute(
        f"""
        SELECT s.id, s.referral_code, u.phone, u.total_points,
               s.subject, s.stage_or_grade, s.item_ids,
               s.first_wrong_ids, s.latest_wrong_ids,
               s.attempt_count, s.status,
               s.started_at, s.expires_at, s.completed_at, s.duration_sec,
               s.total_score_delta, s.daily_bonus_awarded, s.created_date
        FROM study_sessions s
        JOIN users u ON u.referral_code = s.referral_code
        WHERE {where_sql}
        ORDER BY s.created_date DESC, s.started_at DESC
        LIMIT ?
        """,
        params,
    ).fetchall()

    # 返回所有有记录的活跃用户列表，方便前端筛选
    user_rows = conn.execute(
        """
        SELECT referral_code, phone, total_points
        FROM users
        WHERE referral_code != ?
        ORDER BY updated_at DESC
        """,
        (config.ADMIN_REFERRAL_CODE,),
    ).fetchall()

    records = []
    for r in rows:
        item_ids = json.loads(r["item_ids"] or "[]")
        first_wrong_set = set(json.loads(r["first_wrong_ids"] or "[]"))
        latest_wrong_set = set(json.loads(r["latest_wrong_ids"] or "[]"))
        items = _load_session_items(conn, r["subject"], item_ids, include_answers=True)
        for it in items:
            it["first_wrong"] = it["id"] in first_wrong_set
            it["latest_wrong"] = it["id"] in latest_wrong_set

        records.append({
            "session_id": r["id"],
            "referral_code": r["referral_code"],
            "phone": r["phone"],
            "user_total_points": r["total_points"],
            "created_date": r["created_date"],
            "subject": r["subject"],
            "stage_or_grade": r["stage_or_grade"],
            "status": r["status"],                 # passed / expired / in_progress
            "attempt_count": r["attempt_count"],
            "started_at": r["started_at"],
            "completed_at": r["completed_at"],
            "duration_sec": r["duration_sec"],     # 耗时（秒）
            "first_wrong_count": len(first_wrong_set),
            "latest_wrong_count": len(latest_wrong_set),
            "total_score_delta": r["total_score_delta"],
            "daily_bonus_awarded": bool(r["daily_bonus_awarded"]),
            "items": items,
        })

    return {
        "users": [dict(u) for u in user_rows],
        "records": records,
    }