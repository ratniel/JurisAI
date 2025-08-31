from pydantic_settings import BaseSettings
from pydantic import MongoDsn


class Settings(BaseSettings):
    base_url: str = "https://www.myscheme.gov.in"
    mongodb_uri: str
    database_name: str
    schemes_collection: str

    class Config:
        env_file = ".env" # root path
        case_sensitive = False

settings = Settings()