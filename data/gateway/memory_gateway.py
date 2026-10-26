from config.connections.sqlite_connection import SQLiteConnect
from data.model.memory_model import Memory


class MemoryGateway:
    @staticmethod
    def list_all() -> list[Memory]:
        with SQLiteConnect.connect() as connection:
            rows = connection.execute("SELECT id, content, created_at FROM memories ORDER BY id").fetchall()
        return [Memory(id=row[0], content=row[1], created_at=row[2]) for row in rows]

    @staticmethod
    def add(content: str) -> Memory:
        with SQLiteConnect.connect() as connection:
            row = connection.execute(
                "INSERT INTO memories (content) VALUES (?) RETURNING id, content, created_at", (content,)
            ).fetchone()
        return Memory(id=row[0], content=row[1], created_at=row[2])

    @staticmethod
    def get_by_id(memory_id: int) -> Memory | None:
        with SQLiteConnect.connect() as connection:
            row = connection.execute(
                "SELECT id, content, created_at FROM memories WHERE id = ?", (memory_id,)
            ).fetchone()
        return Memory(id=row[0], content=row[1], created_at=row[2]) if row else None

    @staticmethod
    def delete(memory_id: int) -> bool:
        with SQLiteConnect.connect() as connection:
            cursor = connection.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        return cursor.rowcount > 0
