"""用户相关 Pydantic 模型"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """注册请求"""
    username: str = Field(..., min_length=2, max_length=50)
    email: str = Field(..., max_length=120)
    password: str = Field(..., min_length=6, max_length=64)


class UserLogin(BaseModel):
    """登录请求"""
    username: str
    password: str


class UserOut(BaseModel):
    """用户信息"""
    id: str
    username: str
    email: str
    avatar: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    """登录响应"""
    access_token: str
    token_type: str = "bearer"
    user: UserOut
