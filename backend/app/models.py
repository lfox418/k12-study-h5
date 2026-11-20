"""Pydantic 数据模型定义"""
from typing import Any, Literal
from pydantic import BaseModel, Field


class ReferralVerifyRequest(BaseModel):
    referral_code: str = Field(..., min_length=6, max_length=6, description="6位数字或字母推荐码")


class PhoneBindRequest(BaseModel):
    phone: str = Field(..., description="11位中国大陆手机号")


class StartSessionRequest(BaseModel):
    subject: Literal["english", "math"]
    stage_or_grade: Literal["primary", "grade_7", "grade_8", "grade_9"]


class EnglishAnswerItem(BaseModel):
    word_id: int
    user_input: str = ""


class MathAnswerItem(BaseModel):
    question_id: int
    user_input: str = ""


class SubmitSessionRequest(BaseModel):
    answers: list[dict[str, Any]]


class UserProfileResponse(BaseModel):
    referral_code: str
    phone: str | None = None
    total_points: int
    today_english_passed: bool = False
    today_math_passed: bool = False
