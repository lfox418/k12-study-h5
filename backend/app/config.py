"""全局配置模块"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = Path(os.getenv("K12_DB_PATH", str(BASE_DIR / "database" / "k12_study.db")))
INIT_SQL_PATH = Path(os.getenv("K12_INIT_SQL_PATH", str(BASE_DIR / "database" / "init_k12_study.sql")))

# 全局共享计时引擎参数（单位：秒）
SESSION_TOTAL_SECONDS = 30 * 60          # 总限时 30 分钟
STEALTH_HIDE_THRESHOLD_SECONDS = 10 * 60 # 剩余 > 10 分钟隐藏倒计时（即前 20 分钟隐身）
URGENT_PULSE_THRESHOLD_SECONDS = 2 * 60  # 最后 2 分钟红色呼吸脉冲提醒

# 题量与积分奖惩规则
ENGLISH_ROUND_SIZE = 10
ENGLISH_POINTS_CORRECT = 1
ENGLISH_POINTS_WRONG = -1

MATH_ROUND_SIZE = 3
MATH_POINTS_CORRECT = 2
MATH_POINTS_WRONG = -1

DAILY_FIRST_PASS_BONUS = 5               # 每自然日每科目首次全对通关额外 +5 分

# 内部自用模式：是否允许任意符合 6 位字母/数字格式的推荐码首次校验时自动建档
# 设为 "false" 时仅允许 users 表中预制白名单推荐码进入
ALLOW_AUTO_PROVISION = os.getenv("K12_ALLOW_AUTO_PROVISION", "true").lower() == "true"

# 时区偏移（默认东八区，用于自然日 YYYY-MM-DD 判定）
LOCAL_TZ_OFFSET_HOURS = int(os.getenv("K12_TZ_OFFSET_HOURS", "8"))

# 每 6 小时增量更新配置
SYNC_INTERVAL_HOURS = int(os.getenv("K12_SYNC_INTERVAL_HOURS", "6"))
ENABLE_INTERNAL_SCHEDULER = os.getenv("K12_ENABLE_SCHEDULER", "true").lower() == "true"

# 可选 OpenAI 兼容大模型 API 配置（用于补全课标中文释义、双语例句或数学变式题）
LLM_API_BASE = os.getenv("LLM_API_BASE", "").strip()
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()

# 英语公开开源词库默认 URL（可通过环境变量覆盖为内网镜像或自定义 JSON）
ENGLISH_SOURCE_URL = os.getenv(
    "K12_ENGLISH_SOURCE_URL",
    "https://raw.githubusercontent.com/kajweb/dict/master/bookLists.json",
)
MATH_SOURCE_URL = os.getenv("K12_MATH_SOURCE_URL", "").strip()

ADMIN_REFERRAL_CODE = os.getenv("K12_ADMIN_REFERRAL_CODE", "ADM999").strip().upper()