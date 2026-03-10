from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    base_url: str = "https://www.myscheme.gov.in"
    mongodb_uri: str = "mongodb://localhost:27017"
    database_name: str = "jurisai"
    schemes_collection: str = "schemes"

    class Config:
        env_file = ".env" # root path
        case_sensitive = False

settings = Settings()
