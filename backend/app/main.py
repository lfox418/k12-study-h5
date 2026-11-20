"""
FastAPI 主应用入口
- 强制 X-Referral-Code 请求头鉴权（未授权严禁访问任何题库与学习接口）
- 提供双科统一引擎 RESTful API 与个人中心只读档案 API
- 内置 APScheduler 每 6 小时自动增量同步题库/词库任务
"""
from __future__ import annotations
import httpx
from fastapi.responses import Response

from contextlib import asynccontextmanager
import logging
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import config, db, engine
from .models import (
    PhoneBindRequest,
    ReferralVerifyRequest,
    StartSessionRequest,
    SubmitSessionRequest,
)

logger = logging.getLogger("k12_study")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

scheduler = None


def _run_scheduled_sync() -> None:
    """APScheduler 定时回调：调用增量更新脚本"""
    try:
        from scripts.sync_content import run_full_sync
        logger.info("触发每 %d 小时定时增量同步任务...", config.SYNC_INTERVAL_HOURS)
        summary = run_full_sync()
        logger.info("定时增量同步完成: %s", summary)
    except Exception as exc:
        logger.exception("定时增量同步异常: %s", exc)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global scheduler
    # 启动时确保 SQLite WAL 数据库与预制题库就绪
    db.init_database()
    logger.info("SQLite WAL 数据库已就绪: %s", config.DB_PATH)

    if config.ENABLE_INTERNAL_SCHEDULER:
        try:
            from apscheduler.schedulers.background import BackgroundScheduler

            scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
            scheduler.add_job(
                _run_scheduled_sync,
                trigger="interval",
                hours=config.SYNC_INTERVAL_HOURS,
                id="k12_content_sync_6h",
                replace_existing=True,
                max_instances=1,
            )
            scheduler.start()
            logger.info("APScheduler 已启动，每 %d 小时自动增量更新题库与词库", config.SYNC_INTERVAL_HOURS)
        except ImportError:
            logger.warning("未安装 apscheduler，跳过内置定时器（可使用 systemd timer 运行独立脚本）")

    yield

    if scheduler is not None:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler 已安全停止")


app = FastAPI(
    title="K12 英语分级背词 + 初中数学每日三题 双科学习系统 API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_referral_code(x_referral_code: Optional[str] = Header(default=None, alias="X-Referral-Code")) -> str:
    """全局强制推荐码请求头依赖"""
    with db.db_session() as conn:
        try:
            return engine.ensure_valid_referral_code(conn, x_referral_code)
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

def require_admin_code(referral_code: str = Depends(require_referral_code)) -> str:
    if not engine.is_admin_code(referral_code):
        raise HTTPException(status_code=403, detail="无权访问全局记录")
    return referral_code


@app.get("/api/admin/daily-records")
def admin_daily_records(
    date: Optional[str] = Query(default=None, description="自然日 YYYY-MM-DD"),
    user_code: Optional[str] = Query(default=None, description="筛选指定推荐码"),
    subject: Optional[str] = Query(default=None, description="english 或 math"),
    _admin: str = Depends(require_admin_code),
):
    with db.db_session() as conn:
        return engine.get_admin_daily_records(
            conn, date_str=date, target_code=user_code, subject=subject
        )
        

# ============================================================================
# 基础健康检查 & 推荐码准入关卡（无需 X-Referral-Code）
# ============================================================================

@app.get("/api/health")
def health_check():
    with db.db_session() as conn:
        mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        en_cnt = conn.execute("SELECT COUNT(*) FROM english_words").fetchone()[0]
        math_cnt = conn.execute("SELECT COUNT(*) FROM math_questions").fetchone()[0]
    return {
        "status": "ok",
        "sqlite_journal_mode": mode,
        "english_words_count": en_cnt,
        "math_questions_count": math_cnt,
        "server_now": engine.now_epoch(),
    }


@app.post("/api/auth/verify-code")
def verify_referral_code(payload: ReferralVerifyRequest):
    """6位推荐码准入校验"""
    with db.db_session() as conn:
        try:
            profile = engine.verify_or_create_user(conn, payload.referral_code)
            return {"ok": True, "profile": profile}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc


# ============================================================================
# 用户档案与手机号直绑（强制 X-Referral-Code）
# ============================================================================

@app.get("/api/user/profile")
def get_profile(referral_code: str = Depends(require_referral_code)):
    with db.db_session() as conn:
        return engine.get_user_profile(conn, referral_code)


@app.put("/api/user/phone")
def update_phone(payload: PhoneBindRequest, referral_code: str = Depends(require_referral_code)):
    """免验证码直绑 11 位中国大陆手机号"""
    with db.db_session() as conn:
        try:
            profile = engine.bind_user_phone(conn, referral_code, payload.phone)
            return {"ok": True, "profile": profile}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


# ============================================================================
# 全科目共享学习引擎 API（英语 & 数学统一入口）
# ============================================================================

@app.post("/api/sessions/start")
def start_session(payload: StartSessionRequest, referral_code: str = Depends(require_referral_code)):
    with db.db_session() as conn:
        try:
            return engine.start_study_session(
                conn,
                referral_code=referral_code,
                subject=payload.subject,
                stage_or_grade=payload.stage_or_grade,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/sessions/{session_id}/submit")
def submit_session(
    session_id: str,
    payload: SubmitSessionRequest,
    referral_code: str = Depends(require_referral_code),
):
    with db.db_session() as conn:
        try:
            return engine.submit_study_session(
                conn,
                referral_code=referral_code,
                session_id=session_id,
                answers=payload.answers,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/sessions/{session_id}/check-expiry")
def check_session_expiry(session_id: str, referral_code: str = Depends(require_referral_code)):
    with db.db_session() as conn:
        try:
            return engine.expire_session_if_needed(conn, referral_code, session_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


# ============================================================================
# 个人中心双科只读复习档案 API（严格只读，不计分）
# ============================================================================

@app.get("/api/archive/english")
def archive_english(
    grade_stage: Optional[str] = Query(default=None),
    referral_code: str = Depends(require_referral_code),
):
    with db.db_session() as conn:
        return engine.get_english_readonly_archive(conn, referral_code, grade_stage)


@app.get("/api/archive/math")
def archive_math(
    grade: Optional[str] = Query(default=None),
    referral_code: str = Depends(require_referral_code),
):
    with db.db_session() as conn:
        return engine.get_math_readonly_archive(conn, referral_code, grade)


@app.get("/api/sync/logs")
def get_sync_logs(referral_code: str = Depends(require_referral_code)):
    """查看最近 10 次定时增量同步记录"""
    with db.db_session() as conn:
        rows = conn.execute(
            "SELECT id, job_type, added_count, skipped_count, status, detail, started_at, finished_at FROM sync_logs ORDER BY id DESC LIMIT 10"
        ).fetchall()
    return {"logs": [dict(r) for r in rows]}


@app.get("/api/tts")
def tts_audio(word: str = Query(..., min_length=1, max_length=500)):
    """同源代理英文单词/例句 MP3：单词优先有道并自动兜底百度，长句直接走百度 TTS"""
    clean = (
        word.strip()
        .replace("’", "'")
        .replace("‘", "'")
        .replace("“", """)
        .replace("”", """)
        .replace("—", " ")
        .replace("–", " ")
    )
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    candidates = []
    if " " not in clean:
        candidates.append(("https://dict.youdao.com/dictvoice", {"audio": clean, "type": 2}))
    candidates.append(("https://fanyi.baidu.com/gettts", {"lan": "en", "text": clean, "spd": 3, "source": "web"}))

    last_exc = None
    for url, params in candidates:
        try:
            r = httpx.get(url, params=params, headers=headers, timeout=10.0, follow_redirects=True)
            r.raise_for_status()
            if len(r.content) > 100:
                return Response(
                    content=r.content,
                    media_type="audio/mpeg",
                    headers={"Cache-Control": "public, max-age=86400"},
                )
        except Exception as exc:
            last_exc = exc
    raise HTTPException(status_code=502, detail=f"TTS fetch failed: {last_exc}")
