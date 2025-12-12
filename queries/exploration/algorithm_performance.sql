-- Algorithm Performance Analysis
-- Compares CTR, CVR, and recall metrics across L1 candidate generation algorithms
-- Use this to identify underperforming algorithms and optimization opportunities

-- Note: Run in BigQuery console or via bq command
-- Project: sdp-prd-shop-ml

-- ============================================
-- Query 1: Daily Algorithm Performance (Last 30 Days)
-- ============================================
WITH daily_metrics AS (
  SELECT
    event_day,
    algorithm_id,
    algorithm_type,
    cg_algorithm_id,
    recommendation_grain,
    app_user_segment_l365d,
    SUM(impressions) AS impressions,
    SUM(clicks) AS clicks,
    SUM(orders) AS orders,
    SUM(hq_clicks) AS hq_clicks
  FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_super_feed_impressions_metrics_daily`
  WHERE event_day >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
    AND recommendation_grain = 'product'  -- or 'merchant'
  GROUP BY 1, 2, 3, 4, 5, 6
)

SELECT
  algorithm_id,
  algorithm_type,
  cg_algorithm_id,
  COUNT(DISTINCT event_day) AS days_active,
  SUM(impressions) AS total_impressions,
  SUM(clicks) AS total_clicks,
  SUM(orders) AS total_orders,
  SAFE_DIVIDE(SUM(clicks), SUM(impressions)) AS ctr,
  SAFE_DIVIDE(SUM(orders), SUM(impressions)) AS cvr,
  SAFE_DIVIDE(SUM(hq_clicks), SUM(impressions)) AS hq_ctr
FROM daily_metrics
GROUP BY 1, 2, 3
HAVING total_impressions > 1000  -- Filter for statistical significance
ORDER BY cvr DESC;


-- ============================================
-- Query 2: Algorithm Performance by User Segment
-- ============================================
-- Identifies which algorithms perform best for different user segments

SELECT
  algorithm_id,
  app_user_segment_l365d,
  SUM(impressions) AS impressions,
  SUM(orders) AS orders,
  SAFE_DIVIDE(SUM(clicks), SUM(impressions)) AS ctr,
  SAFE_DIVIDE(SUM(orders), SUM(impressions)) AS cvr
FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_super_feed_impressions_metrics_daily`
WHERE event_day >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY 1, 2
HAVING impressions > 1000
ORDER BY algorithm_id, app_user_segment_l365d;


-- ============================================
-- Query 3: Recall@K by Algorithm
-- ============================================
-- Shows recall performance at different K values

SELECT
  algorithm_id,
  algorithm_type,
  algorithm_level,
  is_online,
  period,
  period_type,
  app_user_segment_l365d,
  AVG(recall_at_1) AS avg_recall_at_1,
  AVG(recall_at_2) AS avg_recall_at_2,
  AVG(recall_at_10) AS avg_recall_at_10,
  AVG(recall_at_100) AS avg_recall_at_100
FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_recall_metrics`
WHERE period >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
  AND period_type = 'daily'
GROUP BY 1, 2, 3, 4, 5, 6, 7
ORDER BY algorithm_id, period;


-- ============================================
-- Query 4: Algorithm Contribution Analysis
-- ============================================
-- Shows how much each CG source contributes to final recommendations

SELECT
  cg_algorithm_id,
  COUNT(*) AS recommendation_count,
  SUM(CASE WHEN clicked = 1 THEN 1 ELSE 0 END) AS clicks,
  SUM(CASE WHEN ordered = 1 THEN 1 ELSE 0 END) AS orders,
  SAFE_DIVIDE(SUM(CASE WHEN clicked = 1 THEN 1 ELSE 0 END), COUNT(*)) AS ctr,
  SAFE_DIVIDE(SUM(CASE WHEN ordered = 1 THEN 1 ELSE 0 END), COUNT(*)) AS cvr
FROM `sdp-prd-shop-ml.product_recommendation.intermediate__shop_personalization__recs_impressions_enriched`
WHERE DATE(impression_timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
GROUP BY 1
ORDER BY recommendation_count DESC;


-- ============================================
-- Query 5: Underperforming Algorithm Detection
-- ============================================
-- Flags algorithms performing below baseline

WITH algorithm_performance AS (
  SELECT
    algorithm_id,
    SAFE_DIVIDE(SUM(clicks), SUM(impressions)) AS ctr,
    SAFE_DIVIDE(SUM(orders), SUM(impressions)) AS cvr,
    SUM(impressions) AS impressions
  FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_super_feed_impressions_metrics_daily`
  WHERE event_day >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
  GROUP BY 1
  HAVING impressions > 10000
),

baseline AS (
  SELECT
    AVG(ctr) AS avg_ctr,
    AVG(cvr) AS avg_cvr,
    STDDEV(ctr) AS stddev_ctr,
    STDDEV(cvr) AS stddev_cvr
  FROM algorithm_performance
)

SELECT
  ap.algorithm_id,
  ap.ctr,
  ap.cvr,
  ap.impressions,
  CASE
    WHEN ap.ctr < (b.avg_ctr - b.stddev_ctr) THEN 'UNDERPERFORMING_CTR'
    WHEN ap.ctr > (b.avg_ctr + b.stddev_ctr) THEN 'OUTPERFORMING_CTR'
    ELSE 'NORMAL_CTR'
  END AS ctr_status,
  CASE
    WHEN ap.cvr < (b.avg_cvr - b.stddev_cvr) THEN 'UNDERPERFORMING_CVR'
    WHEN ap.cvr > (b.avg_cvr + b.stddev_cvr) THEN 'OUTPERFORMING_CVR'
    ELSE 'NORMAL_CVR'
  END AS cvr_status
FROM algorithm_performance ap
CROSS JOIN baseline b
ORDER BY ap.cvr ASC;

