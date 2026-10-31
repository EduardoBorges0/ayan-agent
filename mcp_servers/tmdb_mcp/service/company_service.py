from mcp_servers.tmdb_mcp.data.gateway.tmdb.company_gateway import CompanyGateway
from mcp_servers.tmdb_mcp.service.tmdb_call import clean_query, tmdb_call


class CompanyService:
    @staticmethod
    async def search(query: str, page: int = 1) -> dict:
        query, error = clean_query(query)
        if error:
            return {"success": False, "error": error}
        return await tmdb_call(CompanyGateway.search(query, page))
