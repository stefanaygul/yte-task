from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check():
    # BUG: Dependency kontrolü yok — DB, Redis, RabbitMQ down olsa bile "healthy" döner
    return {"status": "healthy"}
