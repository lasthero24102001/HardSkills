from pydantic_settings import BaseSettings,SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL:str
    REDIS_URL:str
    SECRET_KEY:str
    ALGORITHM:str
    ACCESS_TOKEN_EXPIRE_MINUTES:int=30
    REFRESH_TOKEN_EXPIRE_DAYS:int=30
    REDIS_TIME:int=60

    model_config = SettingsConfigDict(env_file='.env',env_file_encoding='utf-8',extra='ignore')

settings = Settings()