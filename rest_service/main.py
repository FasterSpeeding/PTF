import uvicorn


if __name__ == "__main__":
    uvicorn.run("src.rest_server:build", factory=True)
