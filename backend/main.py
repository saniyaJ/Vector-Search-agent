"""
FastAPI backend for Food Discovery.
Endpoints:
    GET  /default-products
         One product per restaurant, loaded when the page opens.
    POST /search
         Body: {"query": "spicy noodles", "rating": 7}
         Optional location filter, off unless all three values are sent:
         {"query": "spicy noodles", "lat": 63.43, "lon": 10.40, "radius_km": 3}
"""
from contextlib import asynccontextmanager
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Load .env before search.py reads the environment variables
load_dotenv()

from search import MAX_RADIUS_KM, Product, SearchFood  # noqa: E402

# Embedding model used when the data was uploaded (must match upload.py)
EMBEDDING_MODEL = "BAAI/bge-m3"

# Frontend origins allowed to call this API from a browser
ALLOWED_ORIGINS = ["http://localhost:3000"]


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="What food the user wants")
    rating: Optional[float] = Field(None, ge=0, le=10, description="Minimum rating (0-10)")
    # Location filter: all three together, or none (the default, no location filter)
    lat: Optional[float] = Field(None, ge=-90, le=90, description="User latitude")
    lon: Optional[float] = Field(None, ge=-180, le=180, description="User longitude")
    radius_km: Optional[float] = Field(None, gt=0, le=MAX_RADIUS_KM, description="Search radius in km")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the model once at startup, not per request
    app.state.search_food = SearchFood(EMBEDDING_MODEL)
    yield


app = FastAPI(title="Food Discovery API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/default-products", response_model=List[Product])
def default_products(request: Request):
    # No limit is passed on purpose: default_products() uses its own default.
    return request.app.state.search_food.default_products()

@app.get("/locations")
def locations(request: Request):
    """Where the dataset has data: rounded locations with a point count each."""
    return {"points": request.app.state.search_food.coverage_points()}


@app.post("/search", response_model=List[Product])
def search(request: Request, body: SearchRequest):
    try:
        return request.app.state.search_food.search_query(
            query=body.query,
            rating=body.rating,
            lat=body.lat,
            lon=body.lon,
            radius_km=body.radius_km,
        )
    except ValueError as e:
        # Raised by search_query for an invalid rating or location
        # (for example, only some of lat/lon/radius_km were sent)
        raise HTTPException(status_code=422, detail=str(e))