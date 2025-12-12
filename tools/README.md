# Tools

Analysis and visualization tools for the Dollars & Sense project.

## NDCG Visualizer

`ndcg_visualizer.py` - Generate interactive HTML visualizations comparing actual vs ideal recommendation rankings with real product data.

### Usage

```bash
# Generate with default settings (5 sessions)
python3 tools/ndcg_visualizer.py

# Custom output path and number of sessions
python3 tools/ndcg_visualizer.py --output my_analysis.html --num-sessions 10
```

### Features

- **Product images & titles**: Real product data from Shopify catalog
- **Vendor information**: Shows merchant/brand for each product  
- **Context/trigger**: Shows what triggered the recommendations (search query, browsing context)
- **Side-by-side comparison**: Actual ranking vs Ideal (IDCG) ranking
- **Visual highlighting**: 
  - 🟢 Green = Purchased items (relevance = 4)
  - 🔵 Blue = Clicked items (relevance = 2)
  - ⬜ Gray = No interaction (relevance = 0)
- **CG source tracking**: Shows which candidate generation algorithm produced each item
- **Metrics display**: DCG, IDCG, NDCG, and ranking loss percentage
- **Per-item breakdown**: Shows DCG contribution for each position

### NDCG Interpretation

| NDCG Score | Interpretation |
|------------|----------------|
| = 1.0 | Perfect - relevant items at ideal positions |
| ≥ 0.8 | Excellent - reranker working well |
| 0.6 - 0.8 | Good - some room for improvement |
| < 0.6 | Opportunity - significant ranking improvements possible |

### Sample Output

The tool generates 5 example sessions showing different NDCG scenarios:
- **Session 1**: NDCG=0.367 - Purchase at position 10 (should be at 1)
- **Session 2**: NDCG=0.500 - Purchase at position 3 (pretty good)
- **Session 3**: NDCG=0.367 - Click at 5, Purchase at 10
- **Session 4**: NDCG=1.000 - Perfect ranking (purchase at position 1)
- **Session 5**: NDCG=0.511 - Click at 2, Purchase at 6

### Data Sources

The visualizer joins multiple BigQuery tables to enrich the display:

| Data | Table | Key Columns |
|------|-------|-------------|
| Impressions | `sdp-prd-shop-ml.product_recommendation.intermediate__shop_personalization__recs_impressions_enriched` | session_id, entity_id, section_y_pos, is_clicked, has_1d_any_touch_attr_order |
| Product Titles | `sdp-prd-merchandising.products_and_pricing_intermediate.products_extended` | product_id, title, vendor, category |
| Product Images | `sdp-prd-shop-ml.intermediate.intermediate__product_images_v2` | product_id, image_cdn_url, position |

### Extending with Real Data

To query live BigQuery data, you can use this pattern:

```python
from google.cloud import bigquery

def fetch_sessions_from_bigquery(num_sessions: int = 5) -> List[Dict]:
    client = bigquery.Client()
    query = """
    WITH purchase_sessions AS (
      SELECT DISTINCT session_id
      FROM `sdp-prd-shop-ml.product_recommendation.intermediate__shop_personalization__recs_impressions_enriched`
      WHERE DATE(event_timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY)
        AND has_1d_any_touch_attr_order = true
      LIMIT 10
    )
    SELECT 
      si.session_id, si.product_id, si.position,
      p.title AS product_title, p.vendor,
      img.image_cdn_url AS product_image_url,
      si.is_clicked, si.has_purchase
    FROM ... -- see queries/exploration/ndcg_analysis.sql for full query
    """
    results = client.query(query).to_dataframe()
    # Transform to session format
    return transform_to_sessions(results)
```

---

## NDCG Visualizer Server (Live Data)

`ndcg_server.py` - **Recommended** - Flask web server that queries BigQuery in real-time.

### Installation

```bash
pip install -r tools/requirements.txt
```

### Usage

```bash
# Start the server
python3 tools/ndcg_server.py --port 8080

# Then open in browser
open http://localhost:8080
```

### Features

| Feature | Description |
|---------|-------------|
| **Live Search** | Queries BigQuery on every search |
| **Performance Metrics Dashboard** | Real-time aggregate metrics with loading state |
| **Category Filter** | Filter by product category |
| **Segment Filter** | Filter by user segment (returning/anonymous) |
| **Surface Filter** | Filter by surface (super_feed, pdp, search) |
| **Days Back** | Configurable date range (1-30 days) |
| **Max Results** | Control number of results (1-50) |
| **Live Stats** | Shows result count and average NDCG |
| **Live Images** | Loads product images from Shopify CDN |

### Metrics Dashboard

The metrics dashboard computes and displays:

| Metric | Description |
|--------|-------------|
| **Avg NDCG** | Average ranking quality (0-1, higher is better) |
| **CTR** | Click-Through Rate (% impressions clicked) |
| **PTR** | Purchase-Through Rate (% impressions purchased) |
| **CVR** | Conversion Rate (% clicks that purchase) |
| **Sessions** | Total sessions analyzed |
| **Impressions** | Total products shown |
| **Recall@K (Click)** | % sessions with click in top K positions |
| **Recall@K (Purchase)** | % purchase sessions with purchase in top K |
| **Interaction Summary** | Total clicks, purchases, sessions with interactions |

### Tabs

| Tab | Description |
|-----|-------------|
| **🔍 Explorer** | Search and visualize individual sessions with NDCG rankings |
| **📊 Optimization** | Identify underperforming areas by surface, segment, or category |
| **💰 GMV Opportunity** | Calculate $ opportunity from improving NDCG to median |

### Optimization Tab

Identify underperforming areas for targeted improvements:

| Metric | Description |
|--------|-------------|
| **By Surface** | Compare NDCG across super_feed, pdp, search |
| **By Segment** | Compare NDCG for returning vs anonymous users |
| **By Category** | Compare NDCG across product categories |
| **vs Median** | Shows % deviation from median NDCG |
| **Sessions** | Volume indicator for prioritization |

### GMV Opportunity Tab

**The bottom line** - Translates ranking quality into dollar opportunity:

| Metric | Description |
|--------|-------------|
| **Total Attributed GMV** | GMV from recommendations in the time period |
| **Est. GMV Opportunity** | Potential uplift if NDCG improved to median |
| **Top Opportunities** | Categories with highest $ upside |
| **Gap to Median** | How far below median NDCG |
| **💰 GMV Opportunity** | Estimated $ uplift per dimension |

**Model Assumption**: 15% GMV increase per 10% NDCG improvement (conservative estimate based on ranking system research).

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Main visualization page |
| `GET /api/filters` | Get available filter options |
| `GET /api/metrics` | Compute aggregate metrics for filters |
| `GET /api/sessions` | Search sessions with filters |
| `GET /api/optimization` | Performance metrics by dimension |
| `GET /api/gmv_opportunity` | GMV opportunity analysis by dimension |

### Query Parameters for `/api/sessions`

```
?category=Beauty&segment=returning&surface=super_feed&days_back=7&limit=10
```

### Query Parameters for `/api/gmv_opportunity`

```
?dimension=category&days_back=7
```
- `dimension`: `surface`, `segment`, or `category`
- `days_back`: 1-30 days of data to analyze

---

## NDCG Visualizer Interactive (Offline)

`ndcg_visualizer_interactive.py` - Generates static HTML with cached images for offline use.

### Usage

```bash
# Generate with default settings
python3 tools/ndcg_visualizer_interactive.py

# Download and cache images locally (recommended for persistence)
python3 tools/ndcg_visualizer_interactive.py --download-images

# Custom output directory and session count
python3 tools/ndcg_visualizer_interactive.py --output-dir tools/output --num-sessions 10 --download-images
```

### Features

| Feature | Description |
|---------|-------------|
| **Category Filter** | Filter by product category (Beauty, Electronics, etc.) |
| **Segment Filter** | Filter by user segment (active, new_user, dormant, etc.) |
| **Surface Filter** | Filter by recommendation surface (super_feed, pdp, search) |
| **Shuffle Button** | Randomize session order |
| **Reset Button** | Clear all filters |
| **Live Stats** | Shows visible count and average NDCG |
| **Image Caching** | Downloads thumbnails to `output/images/` for offline use |

### Output Structure

```
tools/output/
├── ndcg_visualization.html   # Interactive HTML page
└── images/
    ├── img_abc123def456.jpg  # Cached product thumbnails (80x80)
    └── ...
```

### Filter Combinations

The interactive page lets you answer questions like:
- "How do rankings perform for **new users** on **search**?"
- "What's the average NDCG for **Beauty** products?"
- "Are **dormant** users getting good recommendations on **super_feed**?"

---

## Future Tools

- `recall_analyzer.py` - Recall@K analysis and visualization
- `ab_test_analyzer.py` - A/B test result analysis
- `position_decay.py` - Position-based CTR/CVR decay analysis

