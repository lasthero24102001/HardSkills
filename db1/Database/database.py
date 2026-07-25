from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from sqlalchemy.exc import OperationalError
from config import settings

engine = create_async_engine(settings.DATABASE_URL,echo=settings.SQL_ECHO,  # False по дефолту
    pool_size=10, max_overflow=20,
    pool_timeout=30, pool_recycle=1800, pool_pre_ping=True,)
async_factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
db_retry_strategy = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type(OperationalError),
    reraise=True
)

async def get_db():
    async with async_factory() as db:
        try:
            yield db
        except Exception as e:
            await db.rollback()
            raise e
        finally:
            await db.close()