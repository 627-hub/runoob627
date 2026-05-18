# -*- coding: utf-8 -*-
"""
简单认证模块
"""
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
import config

api_key_header = APIKeyHeader(name="X-API-Token", auto_error=False)


async def verify_token(api_key: str = Security(api_key_header)):
    """验证 API Token（如果配置了 API_TOKEN）"""
    if not config.API_TOKEN:
        # 未配置 token，跳过认证
        return None

    if api_key != config.API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Token",
        )
    return api_key


# 用于需要认证的路由
def get_auth_dependencies():
    """返回认证依赖（如果启用了认证）"""
    if config.API_TOKEN:
        return [Security(verify_token)]
    return []
