"""Pydantic 数据模型定义"""
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, model_validator


class ReferralVerifyRequest(BaseModel):
    referral_code: str = Field(..., min_length=6, max_length=6, description="6位数字或字母推荐码")


class NicknameBindRequest(BaseModel):
    nickname: str = Field(..., min_length=2, max_length=20, description="全局唯一昵称（2~20位中英文、数字或_-）")


class StartSessionRequest(BaseModel):
    subject: Literal["english", "math"]
    stage_or_grade: Literal["primary", "grade_7", "grade_8", "grade_9"]

    @model_validator(mode="after")
    def validate_subject_stage(self) -> "StartSessionRequest":
        if self.subject == "math" and self.stage_or_grade == "primary":
            raise ValueError("数学科目仅支持 grade_7、grade_8、grade_9")
        return self


class EnglishAnswerItem(BaseModel):
    word_id: int
    user_input: str = ""


class MathAnswerItem(BaseModel):
    question_id: int
    user_input: str = ""


class SubmitSessionRequest(BaseModel):
    answers: list[dict[str, Any]]


class QuotaHeartbeatRequest(BaseModel):
    subject: Literal["english", "math"]
    delta_seconds: int = Field(..., ge=0, le=120)
    session_id: Optional[str] = None
    referral_code: Optional[str] = None


class UserProfileResponse(BaseModel):
    referral_code: str
    nickname: Optional[str] = None
    total_points: float
    today_english_passed: bool = False
    today_math_passed: bool = False
