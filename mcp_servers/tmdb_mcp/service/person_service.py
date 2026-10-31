from mcp_servers.tmdb_mcp.data.gateway.tmdb.person_gateway import CreditRole, PersonGateway
from mcp_servers.tmdb_mcp.load_env import TMDB_LANGUAGE
from mcp_servers.tmdb_mcp.service.tmdb_call import clean_query, tmdb_call


class PersonService:
    @staticmethod
    async def search(query: str, page: int = 1) -> dict:
        query, error = clean_query(query)
        if error:
            return {"success": False, "error": error}
        return await tmdb_call(PersonGateway.search(query, page, TMDB_LANGUAGE))

    @staticmethod
    async def get_credits(person_id: int, role: CreditRole = "cast", job: str | None = None) -> dict:
        job = " ".join(job.split()) if job else None
        return await tmdb_call(PersonGateway.get_credits(person_id, role, job, TMDB_LANGUAGE))
