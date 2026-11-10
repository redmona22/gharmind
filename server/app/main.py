from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, conversations, health, leads, listing_media, listings, users
from app.api.webhooks import whatsapp
from app.config import settings

if settings.app_env == "production" and settings.secret_key == "change-me":
    raise RuntimeError("SECRET_KEY must be changed in production")

app = FastAPI(title="Gharmind")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(whatsapp.router)
app.include_router(auth.router, prefix="/auth")
app.include_router(users.router, prefix="/users")
app.include_router(leads.router, prefix="/leads")
app.include_router(conversations.router, prefix="/conversations")
app.include_router(listings.router, prefix="/listings")
app.include_router(listing_media.router, prefix="/listings")
