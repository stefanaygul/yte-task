from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# BUG: pool_size çok küçük (5), Black Friday trafiğinde tükenecek
# BUG: Startup retry yok — DB henüz ayağa kalkmadıysa crash
DATABASE_URL = "postgresql://chaos:chaos123@db:5432/chaosdb"

engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=0,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
