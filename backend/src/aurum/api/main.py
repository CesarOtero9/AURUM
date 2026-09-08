from fastapi import FastAPI

app = FastAPI(
    title="AURUM API",
    version="0.1.0",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "aurum-api",
        "version": "0.1.0",
    }
