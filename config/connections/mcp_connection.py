import asyncio
import logging
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import Implementation

from data.model.mcp_model import McpServerConfig
from load_env import MCP_TIMEOUT_SECONDS, USER_CONFIG_DIR

logger = logging.getLogger(__name__)


def describe_error(exc: BaseException) -> str:
    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        exc = exc.exceptions[0]
    return f"{type(exc).__name__}: {exc}"


# As sessões vivem numa task própria porque o SDK exige abrir e fechar os cancel scopes na mesma task.
class McpConnect:
    _sessions: dict[str, ClientSession] = {}
    _owner: asyncio.Task | None = None
    _stop: asyncio.Event | None = None

    @classmethod
    async def start(cls, servers: list[McpServerConfig]) -> dict[str, str]:
        failures: dict[str, str] = {}
        ready = asyncio.Event()
        cls._stop = asyncio.Event()
        cls._owner = asyncio.create_task(cls._hold_sessions(servers, failures, ready))
        await ready.wait()
        return failures

    @classmethod
    async def stop(cls) -> None:
        if cls._owner is None:
            return
        cls._stop.set()
        try:
            await cls._owner
        except Exception as exc:
            logger.warning("Erro ao fechar os servidores MCP: %s", describe_error(exc))
        cls._owner = None

    @classmethod
    def get_session(cls, server: str) -> ClientSession | None:
        return cls._sessions.get(server)

    @classmethod
    async def _hold_sessions(cls, servers: list[McpServerConfig], failures: dict[str, str], ready: asyncio.Event):
        try:
            async with AsyncExitStack() as stack:
                for server in servers:
                    try:
                        cls._sessions[server.name] = await cls._open(stack, server)
                    except Exception as exc:
                        failures[server.name] = describe_error(exc)
                ready.set()
                await cls._stop.wait()
        finally:
            cls._sessions.clear()
            ready.set()

    @staticmethod
    async def _open(stack: AsyncExitStack, server: McpServerConfig) -> ClientSession:
        USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        server_stack = AsyncExitStack()
        try:
            log_file = server_stack.enter_context(
                open(USER_CONFIG_DIR / f"mcp-{server.name}.log", "a", encoding="utf-8")
            )
            parameters = StdioServerParameters(
                command=server.command, args=server.args, env=server.env or None, cwd=server.cwd
            )
            read, write = await server_stack.enter_async_context(stdio_client(parameters, errlog=log_file))
            session = await server_stack.enter_async_context(ClientSession(
                read, write,
                read_timeout_seconds=MCP_TIMEOUT_SECONDS,
                client_info=Implementation(name="ayan", version="0.1.0"),
            ))
            await session.initialize()
        except BaseException:
            await server_stack.aclose()
            raise
        stack.push_async_exit(server_stack)
        return session
