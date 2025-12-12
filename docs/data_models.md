# Data Models Reference

This document describes the key BigQuery tables and data models used for recommendations analysis.

## Project: `sdp-prd-shop-ml`

All recommendation data models live in the `sdp-prd-shop-ml` GCP project.

---

## Intermediate Tables

### `product_recommendation.intermediate__shop_personalization__recs_impressions_enriched`
**Purpose**: Event-level impression data with enrichments - **PRIMARY SOURCE FOR NDCG COMPUTATION**

| Column | Type | Description |
|--------|------|-------------|
| `event_timestamp` | TIMESTAMP | When impression occurred |
| `session_id` | STRING | Session identifier (key for NDCG) |
| `user_id` | STRING | User identifier |
| `entity_id` | STRING | Recommended product ID |
| `shop_id` | STRING | Product's merchant |
| `surface` | STRING | Page/surface type |
| `section_id` | STRING | UI section identifier |
| `section_y_pos` | INT64 | Vertical position in feed (key for NDCG) |
| `entity_type` | STRING | Type: 'product' or 'merchant' |
| `entity_is_unified_rec` | BOOLEAN | Whether from unified recommendations |
| `algorithm_id` | STRING | Which algorithm generated this rec |
| `cg_sources` | ARRAY | L1 candidate generation sources (STRUCT with cg_algorithm_name, cg_rank, cg_algorithm_version) |
| `is_clicked` | BOOLEAN | Whether user clicked |
| `is_padding` | BOOLEAN | Whether this is a padding product |
| `click_quality_classification` | STRING | Click quality: 'High Quality' or other |
| `has_1d_any_touch_attr_order` | BOOLEAN | 1-day attributed conversion (key for NDCG) |
| `has_7d_any_touch_attr_order` | BOOLEAN | 7-day attributed conversion |

**NDCG Use Case**: This is the **primary table for NDCG computation** because it has:
- `session_id`: Group recommendations by session
- `section_y_pos`: Position for DCG discounting
- `cg_sources`: Array to get CG algorithm attribution
- `has_1d_any_touch_attr_order`: Conversion flag for relevance

```sql
-- Example: Computing NDCG by CG algorithm
SELECT cg.cg_algorithm_name, 
       AVG(has_1d_any_touch_attr_order / LOG(section_y_pos + 1, 2)) AS dcg
FROM `sdp-prd-shop-ml.product_recommendation.intermediate__shop_personalization__recs_impressions_enriched`,
     UNNEST(cg_sources) AS cg
WHERE section_y_pos <= 10 AND entity_is_unified_rec
GROUP BY 1
```

See `queries/exploration/ndcg_analysis.sql` for full NDCG implementation.

**Use Cases**:
- **NDCG computation** (ranking quality analysis)
- Granular click/conversion analysis
- CG source attribution
- A/B test analysis

**GitHub**: [shop-ml/dbt/models/intermediate/shop_personalization/product_recommendation/recs_impressions_enriched](https://github.com/Shopify/shop-ml/tree/main/dbt/models/intermediate/shop_personalization/product_recommendation/recs_impressions_enriched)

---

### `product_recommendation.intermediate__shop_personalization__recs_orders_enriched`
**Purpose**: Order-level data with recommendation attribution

| Column | Type | Description |
|--------|------|-------------|
| `order_id` | STRING | Unique order identifier |
| `user_id` | STRING | User who placed order |
| `product_id` | STRING | Purchased product |
| `order_timestamp` | TIMESTAMP | When order was placed |
| `algorithm_level` | STRING | L1/L2/L3 attribution |
| `algorithm_id` | STRING | Attributed algorithm |
| `is_online` | BOOLEAN | Online vs offline evaluation |
| `revenue_usd` | FLOAT64 | Order revenue |

**Use Cases**:
- Order attribution analysis
- Revenue impact measurement
- Algorithm contribution

**GitHub**: [shop-ml/dbt/models/intermediate/shop_personalization/product_recommendation/recs_orders_enriched](https://github.com/Shopify/shop-ml/tree/main/dbt/models/intermediate/shop_personalization/product_recommendation/recs_orders_enriched)

---

### `product_recommendation.intermediate__shop_personalization__recs_user_segments`
**Purpose**: User segment assignments for analysis

| Column | Type | Description |
|--------|------|-------------|
| `user_id` | STRING | User identifier |
| `date` | DATE | Segment assignment date |
| `app_user_segment_l365d` | STRING | Engagement segment |

---

## Mart Tables (Aggregated Metrics)

### `mart.mart__shop_personalization__recs_super_feed_impressions_metrics_daily`
**Purpose**: Daily impression metrics by algorithm and segment

| Column | Type | Description |
|--------|------|-------------|
| `event_day` | DATE | Metric date |
| `recommendation_grain` | STRING | product/merchant |
| `section_id` | STRING | UI section |
| `app_user_segment_l365d` | STRING | User segment |
| `algorithm_type` | STRING | Algorithm category |
| `algorithms_included` | STRING | Combined algorithms |
| `algorithm_id` | STRING | Specific algorithm |
| `cg_algorithm_id` | STRING | CG source |
| `impressions` | INT64 | Count of impressions |
| `clicks` | INT64 | Count of clicks |
| `orders` | INT64 | Count of orders |
| `hq_clicks` | INT64 | High-quality clicks |

**Aggregation Frequency**: Daily (incremental)

**GitHub**: [shop-ml/dbt/models/mart/shop_personalization/product_recommendation/recs_impressions_metrics/recs_super_feed_impressions_metrics_daily](https://github.com/Shopify/shop-ml/tree/main/dbt/models/mart/shop_personalization/product_recommendation/recs_impressions_metrics/recs_super_feed_impressions_metrics_daily)

---

### `mart.mart__shop_personalization__recs_recall_metrics`
**Purpose**: Recall@K metrics by algorithm

| Column | Type | Description |
|--------|------|-------------|
| `period` | DATE | Metric period |
| `frequency` | STRING | daily/weekly |
| `period_type` | STRING | Period aggregation |
| `app_user_segment_l365d` | STRING | User segment |
| `recommendation_grain` | STRING | product/merchant |
| `algorithm_type` | STRING | Algorithm category |
| `algorithm_level` | STRING | L1/L2/L3 |
| `is_online` | BOOLEAN | Online evaluation |
| `algorithm_id` | STRING | Specific algorithm |
| `recall_at_1` | FLOAT64 | Recall@1 |
| `recall_at_2` | FLOAT64 | Recall@2 |
| `recall_at_10` | FLOAT64 | Recall@10 |
| `recall_at_100` | FLOAT64 | Recall@100 |

**Aggregation Frequency**: Full load

---

### `mart.mart__shop_personalization__recs_executive_summary_metrics`
**Purpose**: Executive-level summary metrics

| Column | Type | Description |
|--------|------|-------------|
| `period` | DATE | Metric period |
| `metric_type` | STRING | CTR/CVR/impressions/etc |
| `surface` | STRING | Page/surface |
| `frequency` | STRING | daily/weekly/monthly |
| `period_type` | STRING | Period aggregation |
| `app_user_segment_l365d` | STRING | User segment |
| `recommendation_grain` | STRING | product/merchant |
| `algorithm_level` | STRING | L1/L2/L3 |
| `value` | FLOAT64 | Metric value |

---

### `mart.mart__shop_personalization__recs_super_feed_card_position_impressions_metrics`
**Purpose**: Metrics by feed position - key table for **NDCG computation**

| Column | Type | Description |
|--------|------|-------------|
| `event_date` | DATE | Metric date |
| `event_week` | DATE | Metric week |
| `period` | TIMESTAMP | Period timestamp |
| `session_id` | STRING | Session identifier |
| `section_id` | STRING | UI section |
| `section_y_pos` | INT64 | Y position (1=first item) |
| `section_y_pos_bucket` | STRING | Position bucket |
| `ubi_type` | STRING | Surface/page type |
| `app_user_segment_l365d` | STRING | User segment |
| `cg_algorithm_id` | STRING | CG source algorithm |
| `recommendation_grain` | STRING | product/merchant |
| `impressions_count` | INT64 | Impressions count |
| `clicks_count` | INT64 | Clicks count |
| `impressions_with_attributed_orders_1d_count` | INT64 | Conversions |

**NDCG Use Case**: This table provides position data needed to compute NDCG (Normalized Discounted Cumulative Gain). Use `section_y_pos` as the ranking position and conversion flags to calculate DCG:

```sql
-- DCG@K formula: Σ(relevance_i / log2(position_i + 1))
-- NDCG@K = DCG@K / IDCG@K (normalized by ideal ranking)
SUM(CASE WHEN section_y_pos <= 10 
    THEN has_conversion / LOG(section_y_pos + 1, 2) 
    ELSE 0 END) AS dcg_10
```

See `queries/exploration/ndcg_analysis.sql` for full implementation.

---

### `mart.mart__shop_personalization__recs_merchant_card_padding_metrics`
**Purpose**: Merchant card padding effectiveness

| Column | Type | Description |
|--------|------|-------------|
| `period` | DATE | Metric period |
| `frequency` | STRING | Period frequency |
| `period_type` | STRING | Period type |
| `app_user_segment_l365d` | STRING | User segment |
| `is_full_card_viewed` | BOOLEAN | Full card viewed |
| `distinct_products_viewed` | INT64 | Products viewed |
| `distinct_unified_rec_products_viewed` | INT64 | Rec products viewed |
| `distinct_padding_products_viewed` | INT64 | Padding products viewed |
| `unified_rec_impressions` | INT64 | Rec impressions |
| `padding_impressions` | INT64 | Padding impressions |
| `unified_rec_clicks` | INT64 | Rec clicks |
| `padding_clicks` | INT64 | Padding clicks |

---

## Measures Tables (Experiment Metrics)

### `measures.measures__shop_personalization__l3p_recall_at_*_ttest`
**Purpose**: T-test metrics for product-level recall experiments

Variants: `l3p_recall_at_1_ttest`, `l3p_recall_at_2_ttest`, `l3p_recall_at_10_ttest`, `l3p_recall_at_100_ttest`

| Column | Type | Description |
|--------|------|-------------|
| `experiment_handle` | STRING | Experiment identifier |
| `variant` | STRING | Treatment/control |
| `subject_id` | STRING | User identifier |
| `first_assigned_at` | TIMESTAMP | Assignment time |

---

### `measures.measures__shop_personalization__l3m_recall_at_*_ttest`
**Purpose**: T-test metrics for merchant-level recall experiments

Same structure as L3P variants.

---

### `measures.measures__shop_personalization__recommendation_l3p_recall_facts`
**Purpose**: Raw recall facts for product-level analysis

### `measures.measures__shop_personalization__recommendation_l3m_recall_facts`
**Purpose**: Raw recall facts for merchant-level analysis

---

## Additional Useful Tables

| Table | Description |
|-------|-------------|
| `mart.mart__shop_personalization__recs_ads_sessions_metrics` | Ads session-level metrics |
| `mart.mart__shop_personalization__recs_ads_impressions_metrics` | Ads impression metrics |
| `mart.mart__shop_personalization__recs_staleness_metrics` | Recommendation staleness |
| `mart.mart__shop_personalization__recs_session_start_freshness` | Session freshness metrics |
| `mart.mart__shop_personalization__recs_hidden_metrics` | Hidden/disliked content |
| `mart.mart__shop_personalization__recs_duplicate_merchants` | Duplicate merchant tracking |
| `mart.mart__shop_personalization__recs_duplicate_products` | Duplicate product tracking |
| `mart.mart__shop_personalization__recs_order_attribution_metrics` | Order attribution |
| `mart.mart__shop_personalization__recs_super_feed_sessions_metrics` | Session metrics |
| `mart.mart__shop_personalization__session_facts` | Session-level facts |

---

## Access

1. Request access to `sdp-prd-shop-ml` via helpdesk
2. Follow [Data Platform Access Permissions](https://vault.shopify.io/page/Data-Platform-Access-Permissions~rfTW.md)
3. Add yourself to appropriate Google groups

---

## GitHub Repository

All dbt models are in: [github.com/Shopify/shop-ml](https://github.com/Shopify/shop-ml)

- `dbt/models/intermediate/shop_personalization/` - Intermediate models
- `dbt/models/mart/shop_personalization/` - Mart models
- `dbt/models/measures/shop_personalization/` - Experiment measures

