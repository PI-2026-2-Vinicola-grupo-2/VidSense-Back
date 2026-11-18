from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    thingspeak_channel_id: str = "3500405"
    thingspeak_read_api_key: str = ""
    cors_origins: str = "http://localhost:5500,http://127.0.0.1:5500"
    db_host: str = ""
    db_port: str = "5432"
    db_name: str = "vinicola"
    db_user: str = ""
    db_password: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    model_config = SettingsConfigDict(env_file=".env")

    # Limiares PROVISÓRIOS, a validar com técnico de campo.
    alerta_umidade_alta: float = 80.0
    alerta_umidade_baixa: float = 40.0
    alerta_temp_alta: float = 32.0
    alerta_temp_baixa: float = 18.0
    stale_minutes: int = 60
    alerta_solo_seco: float | None = None

    # Faixa PROVISÓRIA de condição ideal para colheita (RF09).
    janela_temp_min: float = 18.0
    janela_temp_max: float = 30.0
    janela_umi_min: float = 50.0
    janela_umi_max: float = 75.0

    environment: str = "development"


settings = Settings()