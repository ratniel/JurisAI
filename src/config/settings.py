from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    base_url: str = "https://www.myscheme.gov.in"

settings = Settings()