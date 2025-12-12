-- Data Quality Diagnostics
-- Use these queries to validate data freshness and completeness
-- Run before starting analysis to ensure data is reliable

-- Note: Run in BigQuery console or via bq command
-- Project: sdp-prd-shop-ml

-- ============================================
-- Query 1: Check Data Freshness
-- ============================================
-- Verify latest data available in key tables

SELECT 
  'recs_super_feed_impressions_metrics_daily' AS table_name,
  MAX(event_day) AS latest_date,
  DATE_DIFF(CURRENT_DATE(), MAX(event_day), DAY) AS days_behind
FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_super_feed_impressions_metrics_daily`

UNION ALL

SELECT 
  'recs_recall_metrics' AS table_name,
  MAX(period) AS latest_date,
  DATE_DIFF(CURRENT_DATE(), MAX(period), DAY) AS days_behind
FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_recall_metrics`
WHERE period_type = 'daily'

UNION ALL

SELECT 
  'recs_impressions_enriched' AS table_name,
  DATE(MAX(impression_timestamp)) AS latest_date,
  DATE_DIFF(CURRENT_DATE(), DATE(MAX(impression_timestamp)), DAY) AS days_behind
FROM `sdp-prd-shop-ml.product_recommendation.intermediate__shop_personalization__recs_impressions_enriched`

UNION ALL

SELECT 
  'recs_executive_summary_metrics' AS table_name,
  MAX(period) AS latest_date,
  DATE_DIFF(CURRENT_DATE(), MAX(period), DAY) AS days_behind
FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_executive_summary_metrics`
WHERE period_type = 'daily'

ORDER BY days_behind DESC;


-- ============================================
-- Query 2: Check for Missing Dates
-- ============================================
-- Identify gaps in daily data

WITH date_range AS (
  SELECT date
  FROM UNNEST(GENERATE_DATE_ARRAY(
    DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY),
    DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
  )) AS date
),

available_dates AS (
  SELECT DISTINCT event_day AS date
  FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_super_feed_impressions_metrics_daily`
  WHERE event_day >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
)

SELECT
  dr.date,
  CASE WHEN ad.date IS NULL THEN 'MISSING' ELSE 'OK' END AS status
FROM date_range dr
LEFT JOIN available_dates ad ON dr.date = ad.date
WHERE ad.date IS NULL
ORDER BY dr.date;


-- ============================================
-- Query 3: Check Algorithm Coverage
-- ============================================
-- Verify all expected algorithms have data

SELECT
  algorithm_id,
  MIN(event_day) AS first_seen,
  MAX(event_day) AS last_seen,
  COUNT(DISTINCT event_day) AS days_with_data
FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_super_feed_impressions_metrics_daily`
WHERE event_day >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY 1
ORDER BY days_with_data ASC;


-- ============================================
-- Query 4: Check for Null/Zero Values
-- ============================================
-- Identify potential data quality issues

SELECT
  event_day,
  algorithm_id,
  impressions,
  clicks,
  orders,
  CASE 
    WHEN impressions = 0 THEN 'ZERO_IMPRESSIONS'
    WHEN impressions IS NULL THEN 'NULL_IMPRESSIONS'
    WHEN clicks IS NULL THEN 'NULL_CLICKS'
    WHEN orders IS NULL THEN 'NULL_ORDERS'
    WHEN clicks > impressions THEN 'CLICKS_GT_IMPRESSIONS'
    WHEN orders > clicks THEN 'ORDERS_GT_CLICKS'
    ELSE 'OK'
  END AS quality_check
FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_super_feed_impressions_metrics_daily`
WHERE event_day = DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
  AND (impressions = 0 
       OR impressions IS NULL 
       OR clicks IS NULL 
       OR orders IS NULL
       OR clicks > impressions
       OR orders > clicks)
ORDER BY algorithm_id;


-- ============================================
-- Query 5: Volume Anomaly Detection
-- ============================================
-- Flag days with unusual impression volumes

WITH daily_volumes AS (
  SELECT
    event_day,
    SUM(impressions) AS total_impressions
  FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_super_feed_impressions_metrics_daily`
  WHERE event_day >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
  GROUP BY 1
),

stats AS (
  SELECT
    AVG(total_impressions) AS avg_impressions,
    STDDEV(total_impressions) AS stddev_impressions
  FROM daily_volumes
)

SELECT
  dv.event_day,
  dv.total_impressions,
  s.avg_impressions,
  ROUND((dv.total_impressions - s.avg_impressions) / s.stddev_impressions, 2) AS z_score,
  CASE
    WHEN ABS((dv.total_impressions - s.avg_impressions) / s.stddev_impressions) > 2 THEN 'ANOMALY'
    ELSE 'NORMAL'
  END AS status
FROM daily_volumes dv
CROSS JOIN stats s
ORDER BY dv.event_day DESC;


-- ============================================
-- Query 6: Table Row Counts
-- ============================================
-- Quick check of table sizes

SELECT 'mart__recs_super_feed_impressions_metrics_daily' AS table_name,
  COUNT(*) AS row_count
FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_super_feed_impressions_metrics_daily`

UNION ALL

SELECT 'mart__recs_recall_metrics' AS table_name,
  COUNT(*) AS row_count
FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_recall_metrics`

UNION ALL

SELECT 'intermediate__recs_impressions_enriched (7d)' AS table_name,
  COUNT(*) AS row_count
FROM `sdp-prd-shop-ml.product_recommendation.intermediate__shop_personalization__recs_impressions_enriched`
WHERE DATE(impression_timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY);

