from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.core.database import Base, engine
from app.api.v1.endpoints import servers, validation 

settings = get_settings()

app = FastAPI(
    title = settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION,
    contact={
        "name": "Vocs Pouani",
        "url": "https://github.com/itsvocs",
        "email": "vocs.pouani@uniKlinikum-giessen.de",
    },
    license_info={
        "name": "MIT License",
    }
)

# CORS // Frontend Communication 
app.middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    if settings.ENVIRONMENT == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            print("Database tables created")


@app.get("/")
async def root():
    return {"message": "Welcome to the FHIR Verity API", "version": settings.PROJECT_VERSION}

# Include Routers
app.include_router(servers.router, prefix="/api/v1/", tags=["servers"])
app.include_router(validation.router, prefix="/api/v1/", tags=["validation"])