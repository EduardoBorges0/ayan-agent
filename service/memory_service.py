import asyncio
import re

from data.gateway.memory_gateway import MemoryGateway

MAX_MEMORY_LENGTH = 300
MAX_MEMORIES = 50
_SECRET_PATTERN = re.compile(r"sk-[A-Za-z0-9_\-]{16,}")


class MemoryService:
    @staticmethod
    async def list_memories() -> dict:
        memories = await asyncio.to_thread(MemoryGateway.list_all)
        return {"success": True, "data": memories}

    @staticmethod
    async def remember(content: str) -> dict:
        content = " ".join(content.split())
        if not content:
            return {"success": False, "error": "empty_memory"}
        if len(content) > MAX_MEMORY_LENGTH:
            return {"success": False, "error": "memory_too_long"}
        if _SECRET_PATTERN.search(content):
            return {"success": False, "error": "memory_looks_like_secret"}

        existing = await asyncio.to_thread(MemoryGateway.list_all)
        if any(memory.content.casefold() == content.casefold() for memory in existing):
            return {"success": False, "error": "memory_already_exists"}
        if len(existing) >= MAX_MEMORIES:
            return {"success": False, "error": "memory_limit_reached"}

        memory = await asyncio.to_thread(MemoryGateway.add, content)
        return {"success": True, "data": memory}

    @staticmethod
    async def forget(memory_id: int) -> dict:
        memory = await asyncio.to_thread(MemoryGateway.get_by_id, memory_id)
        if memory is None:
            return {"success": False, "error": "memory_not_found"}
        await asyncio.to_thread(MemoryGateway.delete, memory_id)
        return {"success": True, "data": memory}
