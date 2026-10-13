""" 
Search food based on query and returns top product for each restaurant 
Can also filter by rating (0-10)
It will deliver Food detail, description , image and match score

"""
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer
import os 
from typing import Optional, List, Union
import logging
from dotenv import load_dotenv
from datetime import datetime

# Load .env file
load_dotenv()

# Also fix your Product and Location classes to use Pydantic:
from pydantic import BaseModel

class Location(BaseModel):
    lat: float
    lon: float


class Product(BaseModel):
    id: int
    product_name: str
    description: str
    image_url: str
    cafe_name: str
    rating: Optional[float]
    address: str
    location: Location
    score: float
    
 # Create log filename with timestamp
log_filename = f'logs/dataloader_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'


    
# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
    # Log to console
    logging.StreamHandler(),
    # Log to file
    logging.FileHandler(log_filename)  # ← Creates this file
    ]
)
logger = logging.getLogger(__name__)

# Largest radius (in km) a location search may use
MAX_RADIUS_KM = 50

class SearchFood:
    def __init__(self,embedding):
        """
        Search food which finds based on query and filters
        
        Args:
            embedding: Model name for embeddings 
            
        Raises:
            ValueError: If environment variables not set
            Exception: If models fail to load
        """
        try:
            db_host = os.getenv('QDRANT_HOST')
            db_api_key = os.getenv('QDRANT_API_KEY')
            db_collection_name = os.getenv('COLLECTION_NAME')
            
            if not db_host:
                raise ValueError("QDRANT_HOST environment variable not set")
            if not db_api_key:
                raise ValueError("QDRANT_API_KEY environment variable not set")
            if not db_collection_name:
                raise ValueError("COLLECTION_NAME environment variable not set")
            
            
            
            # Initialize the client
            self.client = QdrantClient(url=db_host, api_key=db_api_key)
            self.collection_name = db_collection_name
            self._coverage = None  # cache for coverage_points()
            self.encoder = SentenceTransformer(embedding)
            self.tokenizer = AutoTokenizer.from_pretrained(embedding)
            logger.info("Successfully connected to Qdrant and loadded encoder")
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            raise
    def _validate_rating(self,rating):
        """
        Validate a rating value.

        Args:
            rating: int, float, or numeric string

        Returns:
            The rating as a float if it is a number between 0 and 10 (inclusive),
            otherwise None.
        """
        if isinstance(rating, bool):
            return None

        if isinstance(rating, (int, float)):
            rating_float = float(rating)
        elif isinstance(rating, str):
            try:
                rating_float = float(rating)
            except ValueError:
                return None
        else:
            return None

        # float("nan") fails this comparison too, so NaN returns None
        if 0 <= rating_float <= 10:
            return rating_float
        return None
        
    def _validate_location(self, lat, lon, radius_km):
        """
        Validate an optional location filter.

        Returns:
            None if no location values were given, otherwise a
            (lat, lon, radius_km) tuple of floats.

        Raises:
            ValueError: If only some of the three values are given, or a value is
                        not a number in range.
        """
        values = (lat, lon, radius_km)
        if all(v is None for v in values):
            return None
        if any(v is None for v in values):
            raise ValueError("lat, lon and radius_km must be provided together")

        numbers = []
        for name, v in zip(("lat", "lon", "radius_km"), values):
            # bool is a subclass of int, so reject it explicitly
            if isinstance(v, bool):
                raise ValueError(f"Invalid {name} '{v}': must be a number")
            try:
                numbers.append(float(v))
            except (TypeError, ValueError):
                raise ValueError(f"Invalid {name} '{v}': must be a number")
        lat_f, lon_f, radius_f = numbers

        # NaN and infinity fail these range checks too
        if not -90 <= lat_f <= 90:
            raise ValueError(f"Invalid lat '{lat}': must be between -90 and 90")
        if not -180 <= lon_f <= 180:
            raise ValueError(f"Invalid lon '{lon}': must be between -180 and 180")
        if not 0 < radius_f <= MAX_RADIUS_KM:
            raise ValueError(f"Invalid radius_km '{radius_km}': must be greater than 0 and at most {MAX_RADIUS_KM}")
        return lat_f, lon_f, radius_f

    def search_query(self, query: str, rating=None, lat=None, lon=None, radius_km=None):
        """
        Search food by text query with optional filters.

        Args:
            query: Text describing the food the user wants
            rating: Optional minimum rating (0-10). 0 is a valid value.
            lat, lon: Optional location of the user (degrees)
            radius_km: Optional search radius around lat/lon, in km (max MAX_RADIUS_KM).
                       lat, lon and radius_km must be given together.

        Returns:
            List of Product objects, one per restaurant (its best match for the
            query), at most 12 (empty list if the search fails)

        Raises:
            ValueError: If rating or the location values are invalid
        """
        # Validate before the try block so bad input is reported to the caller
        # instead of being swallowed by the except below and returned as [].
        valid_rating = None
        if rating is not None:
            valid_rating = self._validate_rating(rating)
            if valid_rating is None:
                raise ValueError(f"Invalid rating '{rating}': must be a number between 0 and 10")
        location = self._validate_location(lat, lon, radius_km)

        try:
            # Every condition in `must` has to match (AND)
            conditions = []
            if valid_rating is not None:
                conditions.append(
                    models.FieldCondition(
                        key="rating",
                        range=models.Range(gte=valid_rating)
                    )
                )
            if location is not None:
                loc_lat, loc_lon, loc_radius_km = location
                conditions.append(
                    models.FieldCondition(
                        key="location",
                        geo_radius=models.GeoRadius(
                            center=models.GeoPoint(lat=loc_lat, lon=loc_lon),
                            radius=loc_radius_km * 1000  # Qdrant expects meters
                        )
                    )
                )
            query_filter = models.Filter(must=conditions) if conditions else None

            results = self.client.query_points_groups(
                collection_name=self.collection_name,
                query=self.encoder.encode(query).tolist(),
                using='bge_vec',
                query_filter=query_filter,
                group_by="cafe_name",   # one group per restaurant (payload field must be indexed)
                group_size=1,           # best-matching product inside each restaurant
                limit=12,               # number of restaurants (groups), not products
                with_payload=True
            )

            # Convert Qdrant points to Product objects
            products = []
            for i, pointgrp in enumerate(results.groups, 1):
                try:
                    productGrp = self._grouppoint_to_product(pointgrp)
                    if len(productGrp) > 0:
                        products.extend(productGrp)
                except Exception as e:
                    logger.error(f"Failed to convert point {pointgrp.id}: {e}")
                    continue

            logger.info(f"Found {len(products)} products")
            return products
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def default_products(self,limit=12):
        """ On Page load products with highest rating and one product per resturant will be loaded.
         Returns:
                     List of Product objects (empty list if the search fails)
        """
        try:
            default_query = 'food'
            results = self.client.query_points_groups(
                            collection_name=self.collection_name,
                            query=self.encoder.encode(default_query).tolist(),
                            using="bge_vec",
                            group_by="cafe_name",   # one group per restaurant (payload field must be indexed)
                            group_size=1,           # best-matching product inside each restaurant
                            limit=limit,                # number of restaurants (groups), not points
                            with_payload=True,
                        )
             # Convert Qdrant points to Product objects
            products = []
            for i, pointgrp in enumerate(results.groups, 1):
                try:
                    productGrp = self._grouppoint_to_product(pointgrp)
                    if len(productGrp)>0:
                        products.extend(productGrp)
                except Exception as e:
                    logger.error(f"Failed to convert point {pointgrp.id}: {e}")
                    continue
            
            logger.info(f"Found {len(products)} products")
            logger.info(products)
            return products
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    def coverage_points(self, max_points=20000, precision=1):
        """
        Where the data is: point locations rounded to `precision` decimals
        (1 = about 11 km) with the number of points in each cell.
        Scans the collection once and caches the result.

        Returns:
            List of {"lat", "lon", "count"} dicts (empty list if the scan fails)
        """
        if self._coverage is not None:
            return self._coverage
        try:
            cells = {}
            offset = None
            scanned = 0
            while scanned < max_points:
                points, offset = self.client.scroll(
                    collection_name=self.collection_name,
                    limit=1000,
                    offset=offset,
                    with_payload=["location"],
                    with_vectors=False,
                )
                for p in points:
                    loc = (p.payload or {}).get("location")
                    if not loc:
                        continue
                    key = (round(loc["lat"], precision), round(loc["lon"], precision))
                    cells[key] = cells.get(key, 0) + 1
                scanned += len(points)
                if offset is None:
                    break
            self._coverage = [
                {"lat": lat, "lon": lon, "count": count}
                for (lat, lon), count in cells.items()
            ]
            return self._coverage
        except Exception as e:
            logger.error(f"Coverage scan failed: {e}")
            return []

    def _grouppoint_to_product(self, pointgrp) -> Product:
            """
            Convert Qdrant point Group to Product object.
            Args:
                point: Qdrant point Group with payload  
            Returns:
                Product object
            """
            try:
                productGrp = []
                for i,point in enumerate(pointgrp.hits,1):
                    # Extract location
                    location = Location(
                        lat=point.payload["location"]["lat"],
                        lon=point.payload["location"]["lon"]
                    )
                    
                    # Create Product
                    product = Product(
                        id=point.id,
                        product_name=point.payload["product_name"],
                        description=point.payload["chunk"],
                        image_url=point.payload["image"],
                        cafe_name=point.payload["cafe_name"],
                        rating=point.payload["rating"],
                        address=point.payload["address"],
                        location=location,
                        score=point.score
                    )
                    productGrp.append(product)
                return productGrp
                
            except Exception as e:
                logger.error(f"Error converting point Group to product: {e}")
                raise
            
    def _point_to_product(self, point) -> Product:
        """
        Convert Qdrant point to Product object.
        
        Args:
            point: Qdrant point with payload
            
        Returns:
            Product object
        """
        try:
            # Extract location
            location = Location(
                lat=point.payload["location"]["lat"],
                lon=point.payload["location"]["lon"]
            )
            
            # Create Product
            product = Product(
                id=point.id,
                product_name=point.payload["product_name"],
                description=point.payload["chunk"],
                image_url=point.payload["image"],
                cafe_name=point.payload["cafe_name"],
                rating=point.payload["rating"],
                address=point.payload["address"],
                location=location,
                score=point.score
            )
            
            return product
            
        except KeyError as e:
            logger.error(f"Missing field in payload: {e}")
            raise ValueError(f"Incomplete payload data: {e}")
        except Exception as e:
            logger.error(f"Error converting point to product: {e}")
            raise