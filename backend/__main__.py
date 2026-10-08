import uvicorn

from backend.app import HOST, PORT, create_app

uvicorn.run(create_app(), host=HOST, port=PORT)
