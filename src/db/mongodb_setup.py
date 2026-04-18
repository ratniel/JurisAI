import asyncio
from typing import Any

from beanie import init_beanie
from loguru import logger
from pymongo import AsyncMongoClient

from src.config.settings import settings
from src.data_ingestion.data_models import RawSchemeDocument


async def init_database() -> AsyncMongoClient[dict[str, Any]]:
    """Initialize MongoDB connection and Beanie ODM"""
    try:
        client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(settings.mongodb_uri)

        # Get database
        database = client[settings.database_name]

        # Initialize Beanie with document models
        await init_beanie(
            database=database,
            document_models=[RawSchemeDocument]
        )

        logger.info("Successfully initialized MongoDB with Beanie ODM")
        return client

    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def close_database_connection(
    client: AsyncMongoClient[dict[str, Any]] | None,
) -> None:
    """Close database connection"""
    if client is not None:
        await client.close()
        logger.info("Database connection closed")


if __name__ == "__main__":
    # Test database connection
    async def test_connection():
        await init_database()
        logger.info("Database connection test successful")

    asyncio.run(test_connection())
