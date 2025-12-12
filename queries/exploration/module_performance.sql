-- Module (Slot) Performance Analysis
-- Analyzes performance by position, card type, and padding effectiveness
-- Use this to identify underperforming slots and UI optimization opportunities

-- Note: Run in BigQuery console or via bq command
-- Project: sdp-prd-shop-ml

-- ============================================
-- Query 1: Performance by Section Position
-- ============================================
-- Shows how CTR/CVR varies by position in feed

SELECT
  event_date,
  section_id,
  section_y_pos,
  section_y_pos_bucket,
  app_user_segment_l365d,
  SUM(impressions) AS impressions,
  SUM(clicks) AS clicks,
  SUM(orders) AS orders,
  SAFE_DIVIDE(SUM(clicks), SUM(impressions)) AS ctr,
  SAFE_DIVIDE(SUM(orders), SUM(impressions)) AS cvr
FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_super_feed_card_position_impressions_metrics`
WHERE event_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY 1, 2, 3, 4, 5
ORDER BY event_date, section_y_pos;


-- ============================================
-- Query 2: Position Decay Analysis
-- ============================================
-- Shows how engagement drops off as users scroll

WITH position_metrics AS (
  SELECT
    section_y_pos_bucket,
    SUM(impressions) AS total_impressions,
    SUM(clicks) AS total_clicks,
    SUM(orders) AS total_orders,
    SAFE_DIVIDE(SUM(clicks), SUM(impressions)) AS ctr,
    SAFE_DIVIDE(SUM(orders), SUM(impressions)) AS cvr
  FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_super_feed_card_position_impressions_metrics`
  WHERE event_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
  GROUP BY 1
)

SELECT
  section_y_pos_bucket,
  total_impressions,
  ctr,
  cvr,
  FIRST_VALUE(ctr) OVER (ORDER BY section_y_pos_bucket) AS top_position_ctr,
  SAFE_DIVIDE(ctr, FIRST_VALUE(ctr) OVER (ORDER BY section_y_pos_bucket)) AS ctr_relative_to_top
FROM position_metrics
ORDER BY section_y_pos_bucket;


-- ============================================
-- Query 3: Merchant Card Padding Effectiveness
-- ============================================
-- Compares performance of unified rec products vs padding products

SELECT
  period,
  app_user_segment_l365d,
  is_full_card_viewed,
  distinct_products_viewed,
  distinct_unified_rec_products_viewed,
  distinct_padding_products_viewed,
  SUM(impressions) AS impressions,
  SUM(unified_rec_impressions) AS unified_rec_impressions,
  SUM(padding_impressions) AS padding_impressions,
  SUM(unified_rec_clicks) AS unified_rec_clicks,
  SUM(padding_clicks) AS padding_clicks,
  SAFE_DIVIDE(SUM(unified_rec_clicks), SUM(unified_rec_impressions)) AS unified_rec_ctr,
  SAFE_DIVIDE(SUM(padding_clicks), SUM(padding_impressions)) AS padding_ctr
FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_merchant_card_padding_metrics`
WHERE period >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
  AND frequency = 'daily'
GROUP BY 1, 2, 3, 4, 5, 6
ORDER BY period, app_user_segment_l365d;


-- ============================================
-- Query 4: Exploration vs Exploitation Slots
-- ============================================
-- Compares performance of top-ranked vs exploration slots

SELECT
  event_day,
  algorithm_type,
  CASE 
    WHEN algorithm_type = 'exploration' THEN 'exploration_slot'
    ELSE 'exploitation_slot'
  END AS slot_type,
  SUM(impressions) AS impressions,
  SUM(clicks) AS clicks,
  SUM(orders) AS orders,
  SAFE_DIVIDE(SUM(clicks), SUM(impressions)) AS ctr,
  SAFE_DIVIDE(SUM(orders), SUM(impressions)) AS cvr
FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_super_feed_impressions_metrics_daily`
WHERE event_day >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY 1, 2, 3
ORDER BY event_day, slot_type;


-- ============================================
-- Query 5: Module Staleness Impact
-- ============================================
-- Analyzes how recommendation staleness affects performance

SELECT
  period,
  app_user_segment_l365d,
  surface,
  recommendation_grain,
  previous_period_timeframe,
  current_distinct_shops_shown_bucket,
  previous_distinct_shops_shown_bucket,
  SUM(impressions) AS impressions,
  SUM(fresh_impressions) AS fresh_impressions,
  SUM(stale_impressions) AS stale_impressions,
  SAFE_DIVIDE(SUM(fresh_clicks), SUM(fresh_impressions)) AS fresh_ctr,
  SAFE_DIVIDE(SUM(stale_clicks), SUM(stale_impressions)) AS stale_ctr
FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_staleness_metrics`
WHERE period >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
  AND period_type = 'daily'
GROUP BY 1, 2, 3, 4, 5, 6, 7
ORDER BY period, surface;


-- ============================================
-- Query 6: Session Start Freshness Analysis
-- ============================================
-- Shows latency distribution for recommendation freshness

SELECT
  session_started_at_date,
  app_user_segment_l365d,
  latency_bucket,
  COUNT(*) AS session_count,
  SUM(CASE WHEN has_fresh_recs THEN 1 ELSE 0 END) AS sessions_with_fresh_recs,
  SAFE_DIVIDE(SUM(CASE WHEN has_fresh_recs THEN 1 ELSE 0 END), COUNT(*)) AS fresh_recs_rate
FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_session_start_freshness`
WHERE session_started_at_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY 1, 2, 3
ORDER BY session_started_at_date, latency_bucket;


-- ============================================
-- Query 7: Hidden Content Analysis
-- ============================================
-- Analyzes products/merchants users have hidden (disliked)

SELECT
  event_date,
  content_type,
  action,
  COUNT(*) AS action_count
FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_hidden_metrics`
WHERE event_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY 1, 2, 3
ORDER BY event_date, content_type, action;


-- ============================================
-- Query 8: Duplicate Detection
-- ============================================
-- Identifies duplicate merchants/products being recommended

SELECT
  date,
  'merchants' AS entity_type,
  merchants_changed AS entities_changed
FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_duplicate_merchants`
WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)

UNION ALL

SELECT
  date,
  'products' AS entity_type,
  products_changed AS entities_changed
FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_duplicate_products`
WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)

ORDER BY date, entity_type;

