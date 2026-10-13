""" 
Data insertion pipeline for Food Discovery databse. 
Data set is extracted from here - https://huggingface.co/datasets/Qdrant/wolt-food-clip-ViT-B-32-embeddings 
Data contains Images of food and description about it in multiple language, Hence multilingual embedding is required for it.
Embeddings :
 BGE M3 is used, with 1024 as dimension and Cosine similarity 
 Clip embeddings, with 512 as dimension and Cosine similarity 

"""
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer
from datasets import load_dataset
import os
import io
import hashlib
import numpy as np
import requests
from PIL import Image
from dotenv import load_dotenv
import logging
from datetime import datetime

# Load .env file
load_dotenv()
 
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

# Named vectors stored in the collection
BGE_VECTOR = "bge_vec"    # BAAI/bge-m3, 1024 dimensions
CLIP_VECTOR = "clip_vec"  # clip-ViT-B-32 (text + image), 512 dimensions
BGE_SIZE = 1024
CLIP_SIZE = 512

class DataLoader:
    def __init__(self, bge_model="BAAI/bge-m3", clip_model="clip-ViT-B-32"):
        """
        Data Loader which generates and uploads vectors to Qdrant Collection

        Args:
            bge_model: Model name for the text embedding (also used for chunking)
            clip_model: Model name for the CLIP text + image embedding

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
                raise ValueError("QDRANT_COLLECTION_NAME environment variable not set")
            
            
            
            # Initialize the client
            self.client = QdrantClient(url=db_host, api_key=db_api_key)
            self.collection_name = db_collection_name
            self.bge_encoder = SentenceTransformer(bge_model)
            self.clip_encoder = SentenceTransformer(clip_model)
            # Chunks are cut with the BGE tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(bge_model)

            logger.info("Successfully connected to Qdrant and loaded BGE and CLIP encoders")
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            raise
        
    def create_collection(self):
        """
        Create collection if it doesn't exist.
        Named vector: is name of vector point. It can be based on embedding or dense, sparse, multivector
               
        Returns:
            bool: True if collection exists or created, False if creation failed
        """
            
        try:
            if not self.collection_name or not isinstance(self.collection_name, str):
                raise ValueError("collection_name must be a non-empty string")
 
            # Check if collection exists
            if self.client.collection_exists(self.collection_name):
                logger.info(f"Collection already exists")
                return True
                        
            # Create collection
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config={                    
                    BGE_VECTOR: models.VectorParams(
                        size=BGE_SIZE,
                        distance=models.Distance.COSINE
                    ),
                    CLIP_VECTOR: models.VectorParams(
                        size=CLIP_SIZE,
                        distance=models.Distance.COSINE
                    ),
                }
            )
        
            # Verify creation
            if self.client.collection_exists(self.collection_name):
                logger.info(f"Verification: Collection created")
                return True
            else:
                logger.error(f"Verification failed: Collection not found after creation")
                return False
                    
                
        except Exception as e:
            logger.error(f"Unexpected error in create_collection: {e}")
            return False
                    
    def load_dataset_db(self,dataset_name,streaming=True, subset_count=11000):
       
        """ 
        Load dataset from Hugging Face with error handling.
        
        Args:
            dataset_name: Name of dataset (e.g., 'Qdrant/wolt-food-clip-ViT-B-32-embeddings')
            streaming: Whether to stream dataset (True) or download fully (False)
            subset_count: Number of records to load, None for all
            
        Returns:
            Dataset object or None if failed
        """
        try:
            ds = load_dataset(dataset_name, split="train",streaming=streaming)
            if subset_count is not None:
                subset_ds = ds.take(subset_count)
                subset_fulldesc = subset_ds.map(self.add_full_description, batched=True, batch_size=50)
                return subset_fulldesc
            subset_fulldesc = ds.map(self.add_full_description, batched=True, batch_size=50)
            logger.info(f"Subset created with {subset_count} records")
            return ds 
        except Exception as e:
            logger.error(f"Unexpected error in load_dataset_db: {e}")
            return None
 
    def add_full_description(self,batch):
        """ 
        Detailed description added of product with product name, categories and its original description
        """
        try:
            full_descriptions = []
            for name, cafe_dict, desc in zip(batch["name"], batch["cafe"], batch["description"]):
                try:
                    # Check if cafe_dict is actually a dict
                    if isinstance(cafe_dict, dict):
                        categories = ', '.join(cafe_dict.get('categories', []))
                    else:
                        categories = str(cafe_dict)  # Convert to string if not dict

                    full_desc = f"Product name: {name}. Description: {desc}. Categories - {categories}"
                    full_descriptions.append(full_desc)
                except Exception as e:
                    print(f"Error processing: name={name}, cafe={cafe_dict}, desc={desc}")
                    print(f"Error: {e}")
                    full_descriptions.append("")  # Add empty string for problematic rows

            batch['full_description'] = full_descriptions
            return batch
        except Exception as e:
            logger.error(f"Critical error in add_full_description: {e}")
            raise
    
    def fixed_size_chunks(self,text, size = 256):
        "Splits text into fixed-size token chunks."
        tokens = self.tokenizer.encode(text, add_special_tokens=False)
        return [
            self.tokenizer.decode(tokens[i:i+size], skip_special_tokens=True)
            for i in range(0, len(tokens), size)
        ]
    
    def create_bge_vector(self, text):
        """
        Text embedding with BAAI/bge-m3.

        Args:
            text: Chunk text

        Returns:
            list of 1024 floats
        """
        return self.bge_encoder.encode(text).tolist()

    def _load_image(self, url):
        """Download an image and return it as an RGB PIL image, or None if it cannot be loaded."""
        if not url:
            return None
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return Image.open(io.BytesIO(response.content)).convert("RGB")
        except Exception as e:
            logger.warning(f"Could not load image {url}: {e}")
            return None

    def create_clip_vector(self, text, image=None):
        """
        Text + image embedding with CLIP (clip-ViT-B-32).

        CLIP maps text and images into the same 512-dimensional space. The text and the
        image are encoded separately, each vector is L2-normalised, and the two are
        averaged and normalised again, so the result sits between "what the dish is
        described as" and "what it looks like". With no image (missing or failed
        download) the text vector alone is returned.

        Args:
            text: Chunk text. CLIP reads at most 77 tokens, longer text is truncated.
            image: Optional PIL image of the dish

        Returns:
            list of 512 floats
        """
        text_vec = self.clip_encoder.encode(text, normalize_embeddings=True)
        if image is None:
            return text_vec.tolist()

        image_vec = self.clip_encoder.encode(image, normalize_embeddings=True)
        combined = text_vec + image_vec
        norm = np.linalg.norm(combined)
        if norm == 0:
            return text_vec.tolist()
        return (combined / norm).tolist()

    def _build_vector(self, named_vector, chunk, image):
        """Create the vector for `named_vector` with the matching model."""
        if named_vector == BGE_VECTOR:
            return self.create_bge_vector(chunk)
        if named_vector == CLIP_VECTOR:
            return self.create_clip_vector(chunk, image)
        raise ValueError(f"Unknown named vector '{named_vector}'")

    def _send_batch(self, named_vector, points, create_points):
        """Upload one batch: new points with payload, or only the vector on existing points."""
        if create_points:
            self.client.upload_points(collection_name=self.collection_name, points=points)
        else:
            self.client.update_vectors(
                collection_name=self.collection_name,
                points=[
                    models.PointVectors(id=p.id, vector=p.vector)
                    for p in points
                ],
            )

    def upload_vectors(self, dataset, named_vector, batch_size=256, create_points=True):
        """
        Create one named vector for every chunk and upload it.

        The point id is deterministic (doc id + chunk id), so the BGE and the CLIP
        runs address the same point.

        Args:
            dataset
            named_vector : BGE_VECTOR ("bge_vec") or CLIP_VECTOR ("clip_vec"); picks the model
            batch_size : default is 256
            create_points : True creates the points with their payload (use for the first
                            run). False only adds this vector to points that already exist,
                            keeping their other vectors and payload.
        """
        try:
            if not dataset:
                raise ValueError("dataset is empty or None")
            if named_vector not in (BGE_VECTOR, CLIP_VECTOR):
                raise ValueError(f"Named vector is incorrect: '{named_vector}'")

            points = []
            failed_points = []
            total_points = 0

            for i, doc in enumerate(dataset):
                chunks = self.fixed_size_chunks(doc["full_description"])
                # One image download per product, shared by all of its chunks
                image = self._load_image(doc['image']) if named_vector == CLIP_VECTOR else None
                for chunk_idx, chunk in enumerate(chunks):
                    try:
                        composite_key = f"{doc['id']}_{chunk_idx}"
                        unique_id = int(hashlib.md5(composite_key.encode()).hexdigest(), 16) % (2**63 - 1)

                        vector = self._build_vector(named_vector, chunk, image)
                        payload = None
                        if create_points:
                            payload = {
                                'idx': doc['id'],
                                'cafe_name': doc['cafe']['name'],
                                'product_name': doc['name'],
                                'categories': doc['cafe']['categories'],
                                'image': doc['image'],
                                'rating': doc['cafe']['rating'],
                                'address': doc['cafe']['address'],
                                'location': doc['cafe']['location'],
                                'chunk': chunk,
                            }
                        points.append(
                            models.PointStruct(id=unique_id, vector={named_vector: vector}, payload=payload)
                        )
                    except Exception as e:
                        logger.error(f"Unexpected error processing chunk {doc['id']}:{chunk_idx}: {e}")
                        failed_points.append(doc)

                if len(points) >= batch_size:
                    self._send_batch(named_vector, points, create_points)
                    total_points += len(points)
                    logger.info(f"Uploaded {named_vector} batch: {len(points)} points (total: {total_points})")
                    points = []

            if points:
                self._send_batch(named_vector, points, create_points)
                total_points += len(points)
                logger.info(f"Uploaded final {named_vector} batch: {len(points)} points")

            return {
                'success': total_points,
                'failed': len(failed_points),
                'failed_details': failed_points if failed_points else []
            }
        except Exception as e:
            logger.error(f"Critical error in upload_vectors: {e}")
            return {
                'success': 0,
                'failed': -1,
                'failed_details': [str(e)]
            }


def main() -> None:
    """
    Main orchestration function.

    Creates the collection, then uploads the BGE vectors (creating the points) and
    the CLIP vectors (added to the same points).
    """

    database_name = "Qdrant/wolt-food-clip-ViT-B-32-embeddings"
    dl = DataLoader()

    if not dl.create_collection():
        return

    # The dataset is a stream, so it is loaded again for each pass
    dataset = dl.load_dataset_db(database_name)
    result = dl.upload_vectors(dataset, BGE_VECTOR, create_points=True)
    logger.info(f" BGE result: {result}")

    dataset = dl.load_dataset_db(database_name)
    result = dl.upload_vectors(dataset, CLIP_VECTOR, create_points=False)
    logger.info(f" CLIP result: {result}")


if __name__ == "__main__":
    main()
