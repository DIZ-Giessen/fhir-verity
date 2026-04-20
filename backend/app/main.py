from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.api.v1.endpoints import servers, validation, websocket 

settings = get_settings()

app = FastAPI(
    title = settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION,
    license_info={
        "name": "MIT License",
    }
)

# CORS // Frontend Communication 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

"""
@app.on_event("startup")
async def startup_event():
    if settings.ENVIRONMENT == "development":
        try: 
            from app.models import Base, FhirServer, ValidationRun, InvalidResource
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                print("Database tables created")
        except Exception as e:
            print(f"Error creating database tables: {e}")
"""


@app.get("/")
async def root():
    return {"message": "Welcome to the FHIR Verity API", "version": settings.PROJECT_VERSION}

# Include Routers
app.include_router(servers.router, prefix="/api/v1", tags=["servers"])
app.include_router(validation.router, prefix="/api/v1", tags=["validation"])
app.include_router(websocket.router, prefix="/api/v1", tags=["websocket"])