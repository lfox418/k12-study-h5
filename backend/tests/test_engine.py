"""核心引擎端到端自动化验证测试"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import config, db, engine  # noqa: E402
from scripts import sync_content  # noqa: E402


def run_all_tests() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = Path(tmpdir) / "test_k12_study.db"
        config.DB_PATH = test_db
        db.init_database(db_path=test_db)

        with db.db_session(test_db) as conn:
            # 1. 验证 WAL 模式与并发参数
            mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
            assert mode.lower() == "wal", f"期望 WAL 模式，实际为 {mode}"
            timeout_ms = conn.execute("PRAGMA busy_timeout;").fetchone()[0]
            assert int(timeout_ms) == 5000, f"期望 busy_timeout=5000，实际为 {timeout_ms}"

            # 2. 验证英语四学段与数学三年级预制题库完整入库
            en_stages = dict(conn.execute("SELECT grade_stage, COUNT(*) FROM english_words GROUP BY grade_stage").fetchall())
            assert set(en_stages.keys()) == {"primary", "grade_7", "grade_8", "grade_9"}
            for stage, cnt in en_stages.items():
                assert cnt >= 10, f"英语学段 {stage} 词数不足 10: {cnt}"

            math_grades = dict(conn.execute("SELECT grade, COUNT(*) FROM math_questions GROUP BY grade").fetchall())
            assert set(math_grades.keys()) == {"grade_7", "grade_8", "grade_9"}
            for g, cnt in math_grades.items():
                assert cnt >= 6, f"数学年级 {g} 题数不足: {cnt}"

            # 3. 验证 6 位推荐码校验与未授权拦截
            try:
                engine.ensure_valid_referral_code(conn, None)
                raise AssertionError("未传推荐码应当被拦截")
            except PermissionError:
                pass

            profile = engine.verify_or_create_user(conn, "abc123")
            assert profile["referral_code"] == "ABC123"
            assert profile["total_points"] == 0

            # 4. 验证免验证码手机号正则校验与绑定
            try:
                engine.bind_user_phone(conn, "ABC123", "12345")
                raise AssertionError("非法手机号应当被拒绝")
            except ValueError:
                pass
            updated = engine.bind_user_phone(conn, "ABC123", "13912345678")
            assert updated["phone"] == "13912345678"

            # 5. 验证英语开局、错词扣分保底 0、重学不重置 expires_at、全对通关 + 每日 +5 奖励
            t0 = 1_760_000_000
            en_sess = engine.start_study_session(conn, "ABC123", "english", "grade_7", now_ts=t0)
            assert len(en_sess["items"]) == 10
            assert en_sess["expires_at"] == t0 + 1800

            # 首次故意全部填错 -> 扣 10 分但总分保底为 0
            wrong_ans = [{"word_id": w["id"], "user_input": "wrong"} for w in en_sess["items"]]
            r1 = engine.submit_study_session(conn, "ABC123", en_sess["session_id"], wrong_ans, now_ts=t0 + 120)
            assert r1["status"] == "in_progress"
            assert r1["all_correct"] is False
            assert r1["total_points"] == 0, "总分必须保底为 0"
            assert r1["expires_at"] == t0 + 1800, "重学期间 expires_at 不得重置"

            # 第二次全部拼对（忽略大小写与首尾空格）-> +10 分 + 每日首次通关 +5 分 = 15 分
            correct_ans = [{"word_id": w["id"], "user_input": f"  {w['word'].upper()} "} for w in en_sess["items"]]
            r2 = engine.submit_study_session(conn, "ABC123", en_sess["session_id"], correct_ans, now_ts=t0 + 300)
            assert r2["status"] == "passed"
            assert r2["all_correct"] is True
            assert r2["score_delta"] == 10
            assert r2["daily_bonus"] == 5
            assert r2["total_points"] == 15

            # 同日再通关一次英语 -> 不重复发 +5 分，仅加单轮 10 分 -> 25 分
            en_sess2 = engine.start_study_session(conn, "ABC123", "english", "grade_7", now_ts=t0 + 400)
            correct_ans2 = [{"word_id": w["id"], "user_input": w["word"]} for w in en_sess2["items"]]
            r3 = engine.submit_study_session(conn, "ABC123", en_sess2["session_id"], correct_ans2, now_ts=t0 + 500)
            assert r3["daily_bonus"] == 0, "同自然日同科目重复通关不得重复发 5 分"
            assert r3["total_points"] == 25

            # 6. 验证数学每日三题与独立每日 +5 分奖励
            math_sess = engine.start_study_session(conn, "ABC123", "math", "grade_8", now_ts=t0 + 600)
            assert len(math_sess["items"]) == 3
            # 查出标答模拟全对（对 3 题 = +6 分，数学当日首次通关 +5 分 -> 25 + 11 = 36 分）
            q_ids = [q["id"] for q in math_sess["items"]]
            q_rows = conn.execute(
                f"SELECT id, answer FROM math_questions WHERE id IN ({','.join('?' for _ in q_ids)})",
                q_ids,
            ).fetchall()
            ans_map = {row["id"]: row["answer"].split("|")[0] for row in q_rows}
            m_res = engine.submit_study_session(
                conn,
                "ABC123",
                math_sess["session_id"],
                [{"question_id": qid, "user_input": ans_map[qid]} for qid in q_ids],
                now_ts=t0 + 900,
            )
            assert m_res["status"] == "passed"
            assert m_res["score_delta"] == 6
            assert m_res["daily_bonus"] == 5
            assert m_res["total_points"] == 36

            # 7. 验证 30 分钟超时作废规则（不发积分）
            exp_sess = engine.start_study_session(conn, "ABC123", "math", "grade_9", now_ts=t0 + 1000)
            exp_res = engine.submit_study_session(
                conn,
                "ABC123",
                exp_sess["session_id"],
                [{"question_id": q["id"], "user_input": "A"} for q in exp_sess["items"]],
                now_ts=t0 + 1000 + 1801,  # 超过 30 分钟
            )
            assert exp_res["status"] == "expired"
            assert exp_res["is_expired"] is True
            assert exp_res["total_points"] == 36, "超时作废不得发放积分"

            # 8. 验证只读档案返回首次错词标红与三阶词库
            en_arch = engine.get_english_readonly_archive(conn, "ABC123", "grade_7")
            assert en_arch["readonly"] is True
            assert len(en_arch["history"]) == 2
            assert len(en_arch["tiers"]["level_2"]) >= 10, "首轮全对过关的一级词应晋升二级"

            math_arch = engine.get_math_readonly_archive(conn, "ABC123")
            assert math_arch["readonly"] is True
            assert len(math_arch["history"]) == 2

        # 9. 验证离线增量更新脚本与二次运行幂等去重
        sync1 = sync_content.run_full_sync(batch_size=6, use_remote_api=False)
        assert sync1["english"]["added"] == 6
        assert sync1["math"]["added"] == 3
        sync2 = sync_content.run_full_sync(batch_size=6, use_remote_api=False)
        assert sync2["math"]["added"] == 0 and sync2["math"]["skipped"] >= 3

        print("ALL ENGINE & SQLITE WAL TESTS PASSED:", json.dumps({"sync1": sync1, "sync2": sync2}, ensure_ascii=False))


if __name__ == "__main__":
    run_all_tests()
