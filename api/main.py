from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .endpoints import router

app = FastAPI(title="EduLLM - Academic Assistant")

app.add_middleware(
    CORSMiddleware,
    # allow_origins=["*"  # Allow all origins for development; adjust in production
    # #     "http://localhost:5173",  # Frontend Vite port
    # #     "http://localhost:3000",  # Keep this if you test with Create React App
    # # 
    # ],
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, OPTIONS, etc.)
    allow_headers=["*"],  # Allow all headers
)

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)