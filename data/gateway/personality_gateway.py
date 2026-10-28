from load_env import PERSONALITY_PATH


class PersonalityGateway:
    @staticmethod
    def read() -> str | None:
        try:
            # utf-8-sig aceita ficheiros guardados com BOM (comum em editores do Windows).
            return PERSONALITY_PATH.read_text(encoding="utf-8-sig")
        except FileNotFoundError:
            return None

    @staticmethod
    def write(content: str) -> None:
        PERSONALITY_PATH.parent.mkdir(parents=True, exist_ok=True)
        # Grava num ficheiro temporário e troca, para nunca deixar a personalidade a meio.
        temporary_path = PERSONALITY_PATH.with_name(PERSONALITY_PATH.name + ".tmp")
        temporary_path.write_text(content, encoding="utf-8")
        temporary_path.replace(PERSONALITY_PATH)
