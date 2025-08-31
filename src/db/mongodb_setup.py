import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from loguru import logger

from config.settings import settings
from data_ingestion.data_models import SchemeDetails


async def init_database() -> AsyncIOMotorClient:
    """Initialize MongoDB connection and Beanie ODM"""
    try:
        client = AsyncIOMotorClient(settings.mongodb_uri)

        # Get database
        database = client[settings.database_name]

        # Initialize Beanie with document models
        await init_beanie(
            database=database,
            document_models=[SchemeDetails]
        )

        logger.info("Successfully initialized MongoDB with Beanie ODM")
        return client

    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def close_database_connection(client: AsyncIOMotorClient) -> None:
    """Close database connection"""
    if client:
        client.close()
        logger.info("Database connection closed successfully")


if __name__ == "__main__":
    # Test database connection
    async def test_connection():
        await init_database()
        logger.info("Database connection test successful")

    asyncio.run(test_connection())
