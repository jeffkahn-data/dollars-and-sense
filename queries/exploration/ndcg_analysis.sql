-- NDCG (Normalized Discounted Cumulative Gain) Analysis
-- 
-- NDCG measures ranking quality by comparing actual ranking to ideal ranking.
-- Formula: NDCG@K = DCG@K / IDCG@K
-- where DCG@K = Σ(rel_i / log2(i+1)) for i=1 to K
--
-- This query computes NDCG to identify ranking inefficiencies in:
-- - Algorithms: Which CG sources produce better-ordered lists?
-- - Pages/Surfaces: Where is reranking underperforming?
-- - User Segments: Are certain users getting poorly ranked results?
--
-- Data source: intermediate__shop_personalization__recs_impressions_enriched
-- which contains session_id, section_y_pos (position), and cg_sources array.

-- ============================================
-- Part 1: Session-Level NDCG Computation
-- ============================================
WITH session_impressions AS (
  SELECT
    DATE(event_timestamp) AS date,
    session_id,
    surface,
    cg.cg_algorithm_name AS cg_algorithm_id,
    section_y_pos AS position,
    CASE WHEN has_1d_any_touch_attr_order THEN 1 ELSE 0 END AS has_conversion,
    CASE WHEN is_clicked THEN 1 ELSE 0 END AS has_click
  FROM `sdp-prd-shop-ml.product_recommendation.intermediate__shop_personalization__recs_impressions_enriched`,
       UNNEST(cg_sources) AS cg
  WHERE DATE(event_timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
    AND section_y_pos > 0
    AND section_y_pos <= 50
    AND entity_type = 'product'
    AND entity_is_unified_rec
),

-- Calculate DCG per session (Binary Relevance using conversion)
session_dcg AS (
  SELECT
    date,
    session_id,
    surface,
    cg_algorithm_id,
    -- DCG@10
    SUM(CASE WHEN position <= 10 THEN has_conversion / LOG(position + 1, 2) ELSE 0 END) AS dcg_10,
    -- DCG@20
    SUM(CASE WHEN position <= 20 THEN has_conversion / LOG(position + 1, 2) ELSE 0 END) AS dcg_20,
    -- Count of conversions for IDCG calculation
    SUM(CASE WHEN position <= 10 THEN has_conversion ELSE 0 END) AS conversions_10,
    SUM(CASE WHEN position <= 20 THEN has_conversion ELSE 0 END) AS conversions_20
  FROM session_impressions
  GROUP BY 1, 2, 3, 4
  HAVING SUM(has_conversion) > 0  -- Only sessions with at least one conversion
)

-- ============================================
-- Part 2: Aggregated NDCG by CG Algorithm
-- ============================================
SELECT
  cg_algorithm_id,
  COUNT(DISTINCT session_id) AS sessions_with_conversion,
  
  -- NDCG@10 (using lookup values for IDCG)
  ROUND(AVG(
    CASE 
      WHEN conversions_10 = 1 THEN dcg_10 / 1.0
      WHEN conversions_10 = 2 THEN dcg_10 / 1.63
      WHEN conversions_10 = 3 THEN dcg_10 / 2.13
      WHEN conversions_10 >= 4 THEN dcg_10 / 2.56
      ELSE NULL
    END
  ), 4) AS ndcg_10,
  
  -- NDCG@20
  ROUND(AVG(
    CASE 
      WHEN conversions_20 = 1 THEN dcg_20 / 1.0
      WHEN conversions_20 = 2 THEN dcg_20 / 1.63
      WHEN conversions_20 = 3 THEN dcg_20 / 2.13
      WHEN conversions_20 >= 4 THEN dcg_20 / 2.56
      ELSE NULL
    END
  ), 4) AS ndcg_20,
  
  -- Average conversions in top 10
  ROUND(AVG(conversions_10), 2) AS avg_conversions_in_top_10

FROM session_dcg
WHERE cg_algorithm_id IS NOT NULL
GROUP BY cg_algorithm_id
HAVING COUNT(DISTINCT session_id) >= 100  -- Minimum sample size
ORDER BY ndcg_10 DESC;


-- ============================================
-- Part 3: NDCG by Page/Surface (uncomment to run)
-- ============================================
/*
SELECT
  surface,
  COUNT(DISTINCT session_id) AS sessions_with_conversion,
  ROUND(AVG(
    CASE 
      WHEN conversions_10 = 1 THEN dcg_10 / 1.0
      WHEN conversions_10 = 2 THEN dcg_10 / 1.63
      WHEN conversions_10 >= 3 THEN dcg_10 / 2.13
      ELSE NULL
    END
  ), 4) AS ndcg_10,
  ROUND(AVG(conversions_10), 2) AS avg_conversions_in_top_10
FROM session_dcg
WHERE conversions_10 > 0
GROUP BY surface
HAVING COUNT(DISTINCT session_id) >= 50
ORDER BY ndcg_10 DESC;
*/


-- ============================================
-- Part 4: Daily NDCG Trends (uncomment to run)
-- ============================================
/*
SELECT
  date,
  COUNT(DISTINCT session_id) AS sessions_with_conversion,
  ROUND(AVG(
    CASE 
      WHEN conversions_10 = 1 THEN dcg_10 / 1.0
      WHEN conversions_10 = 2 THEN dcg_10 / 1.63
      WHEN conversions_10 >= 3 THEN dcg_10 / 2.13
      ELSE NULL
    END
  ), 4) AS ndcg_10
FROM session_dcg
GROUP BY date
ORDER BY date;
*/

