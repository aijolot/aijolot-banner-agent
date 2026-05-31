"""brand-context-load skill — see SKILL.md."""

from app.agents.tools import brand_fs
from app.schemas.brand import BrandContext


async def run(brand_id: str) -> BrandContext:
    return brand_fs.read(brand_id)
