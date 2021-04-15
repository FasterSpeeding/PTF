import uvicorn  # type: ignore[import]
from src import utilities

if __name__ == "__main__":
    metadata = utilities.Metadata()
    uvicorn.run(
        "src.rest_server:build",
        factory=True,
        log_level=metadata.log_level,
        ssl_keyfile=metadata.ssl_key,
        ssl_certfile=metadata.ssl_cert,
    )
