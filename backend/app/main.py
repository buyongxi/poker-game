import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import settings
from app.database import init_db, async_session
from app.api import auth, users, rooms, admin
from app.websocket.manager import router as websocket_router
from app.services.user_service import UserService

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()

    # Create initial admin if credentials are provided
    if settings.ADMIN_USERNAME and settings.ADMIN_PASSWORD:
        async with async_session() as db:
            user_service = UserService(db)
            created = await user_service.create_initial_admin(
                username=settings.ADMIN_USERNAME,
                password=settings.ADMIN_PASSWORD,
                display_name=settings.ADMIN_DISPLAY_NAME or "管理员"
            )
            if created:
                print(f"Initial admin created: {settings.ADMIN_USERNAME}")
    else:
        print("No admin credentials provided, skipping admin creation")

    yield
    # Shutdown


app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(rooms.router, prefix="/api/rooms", tags=["rooms"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])

# WebSocket router
app.include_router(websocket_router)


@app.get("/")
async def root():
    return {"message": "Poker Game API", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
