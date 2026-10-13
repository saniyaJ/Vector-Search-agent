# Food Discovery App using Vector DB

An AI agent that finds the food and dishes you are craving. Search is vector based: your text is matched against dish descriptions by meaning, not by keywords, and the data also carries CLIP vectors so text and image similarity live in the same space.

<!-- Replace the placeholder below with your own recording, e.g. docs/demo.gif -->
![Food Discovery demo](https://placehold.co/900x500/gif?text=Demo+GIF+coming+soon)

## Dataset

The data comes from the Hugging Face dataset
[Qdrant/wolt-food-clip-ViT-B-32-embeddings](https://huggingface.co/datasets/Qdrant/wolt-food-clip-ViT-B-32-embeddings).

Each record is a dish from a Wolt restaurant and contains:

- the product name, a description (in many languages) and the restaurant's categories
- a food image URL
- restaurant name, rating, address and geo location

Because descriptions are multilingual, a multilingual text embedding model is needed (see below).

## Embeddings

Two vectors are stored for every point.

### CLIP (`clip_vector`, 512 dimensions)

[`sentence-transformers/clip-ViT-B-32`](https://huggingface.co/sentence-transformers/clip-ViT-B-32) maps images and text into one shared 512-dimensional space.

How CLIP works:

1. **Two encoders.** A Vision Transformer (ViT-B/32) encodes images; a Transformer encodes text.
2. **Contrastive training.** CLIP is trained on hundreds of millions of image-caption pairs. For each batch it pulls the embedding of a matching image and caption together and pushes non-matching pairs apart.
3. **Shared space.** Because both encoders output vectors of the same size (512) in the same space, a sentence like "spicy ramen" lands close to photos of spicy ramen. Image-to-text, text-to-image and text-to-text similarity all work with a single cosine comparison.

### BGE-M3 (`bge_vec`, 1024 dimensions)

To search with text only, the app also uses [`BAAI/bge-m3`](https://huggingface.co/BAAI/bge-m3).

Why this model:

- **Multilingual**: supports 100+ languages, which matters for a dataset with descriptions in many languages and queries in any language.
- **Long inputs**: handles up to 8192 tokens, so long descriptions are not cut off.
- **Strong retrieval quality**: among the best open models on multilingual retrieval benchmarks.
- **Richer vectors**: 1024 dimensions capture more semantic detail than CLIP's 512 for text-to-text matching.

Both vectors use **cosine similarity** as the distance metric.

## Chunking

The text that is embedded for each product combines:

- product name
- product description
- product categories

```
Product name: <name>. Description: <description>. Categories - <categories>
```

This text is split into **fixed-size token chunks (256 tokens)** using the BGE-M3 tokenizer. The distribution of text lengths showed that 80% of the products lie within 300 tokens, so most dishes fit in one or two chunks and a fixed-size strategy gives consistent, comparable vectors without complex splitting logic. Each chunk becomes its own point, and search results are grouped back to one best dish per restaurant.

## Features

### 1. Text search

Type what you want in any language ("spicy noodles", "vegan salad", "something sweet"). The query is embedded with Clip Model and compared with the stored vectors by cosine similarity. Results are grouped by restaurant, so you get the best matching dish from each of up to 12 restaurants, each with its image, description, rating, address and a match score.

### 2. Rating filter

Optionally restrict results to dishes from restaurants with a **minimum rating**. The slider goes from 0 to 10 and starts at **7**, so turning the filter on keeps only well-rated places. The filter is sent to Qdrant as a payload range condition (`rating >= value`).

### 3. Location filter

Restrict results to dishes within a radius of a place:

- **Near me** uses your browser location.
- **Click the map** to search around any spot.
- The radius defaults to **10 km** and can be set to 25 or 50 km (the API caps it at 50 km).

The map shows pink dots for where the dataset has data and amber dots for your current results. If the chosen spot is far from any data you get a warning.

## How a vector point looks

Qdrant uses an **HNSW** (Hierarchical Navigable Small World) graph for approximate nearest-neighbour search. Filters (rating, location) are applied *during* the graph traversal, so the engine only considers points that satisfy the filter and still returns the closest matches, rather than filtering a short result list afterwards. This keeps results accurate even with strict filters.

Each point stores two named vectors (`bge_vec` and `clip_vector`) plus this payload:

```json
{
  "idx": 935,
  "cafe_name": "COMO (Chickens)Mendikulov",
  "product_name": "Chickens Тортилла",
  "categories": ["chicken", "burgers", "american", "mexican", "street_food"],
  "image": "https://wolt-menu-images-cdn.wolt.com/menu-images/60bf295c2c461eedb5371a32/ca49fb18-cf70-11eb-a583-baa684def60a_________.jpeg",
  "rating": 9.2,
  "address": "ул. Мендикулова 98",
  "location": { "lon": 76.95406875434803, "lat": 43.23328871993156 },
  "chunk": "Product name: Chickens Тортилла. Description: Куриная грудка в соусе терияки с добавлением салата и фри. Categories - chicken, burgers, american, mexican, street_food"
}
```

## Architecture

```
frontend/                   static frontend (index.html, css/, js/ ES modules, Leaflet map)
backend/
├── main.py                 FastAPI API
├── search.py               SearchFood: query encoding + Qdrant grouped search
├── upload.py               DataLoader: chunk, embed and upload to Qdrant
└── requirement.txt         Python dependencies
```

| Endpoint | Purpose |
| --- | --- |
| `GET /default-products` | One dish per restaurant, shown on page load |
| `POST /search` | `{query, rating?, lat?, lon?, radius_km?}` returns the best dish per restaurant |
| `GET /locations` | Where the dataset has data (for the map's coverage dots) |

## Getting started

1. Create a `.env` file in the project root:

   ```
   QDRANT_HOST=<your Qdrant URL>
   QDRANT_API_KEY=<your API key>
   COLLECTION_NAME=<collection name>
   ```

2. Install and run the API:

   ```powershell
   python -m venv vector_env
   .\vector_env\Scripts\Activate.ps1
   cd backend
   pip install -r requirement.txt
   python upload.py                       # one-off: create the collection and upload vectors
   uvicorn main:app --reload --port 8000
   ```

3. Serve the frontend on port 3000 (the origin allowed by CORS):

   ```powershell
   cd frontend
   python -m http.server 3000
   ```

   Then open <http://localhost:3000>.

To point the UI at a different backend, edit `API_BASE` in `frontend/js/config.js`.
