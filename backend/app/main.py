from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.models import Account, RestItem, RestTypeDefinition, Tenant
from app.routers import accounts, auth, rest_items, rest_types, tenants

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Kreideheld API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(tenants.router, prefix="/tenants", tags=["tenants"])
app.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
app.include_router(rest_types.router, prefix="/rest-types", tags=["rest-types"])
app.include_router(rest_items.router, prefix="/rest-items", tags=["rest-items"])


@app.get("/health")
def health_check():
    return {"status": "ok"}
