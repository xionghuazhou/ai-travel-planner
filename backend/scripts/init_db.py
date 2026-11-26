"""初始化数据库并导入景点数据（独立脚本）"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import init_db  # noqa: E402
from app.main import seed_if_empty  # noqa: E402


async def main():
    await init_db()
    await seed_if_empty()
    print("✅ 数据库初始化完成")


if __name__ == "__main__":
    asyncio.run(main())
