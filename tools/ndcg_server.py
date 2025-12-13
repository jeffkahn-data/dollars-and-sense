"""
NDCG Visualizer Server - Dynamic search of real recommendation data

A Flask web server that:
- Queries BigQuery for real session/impression data
- Joins with product catalog for titles and images
- Serves an interactive HTML frontend with live filtering

Usage:
    python3 tools/ndcg_server.py [--port 8080]
    
Then open: http://localhost:8080
"""

import argparse
import hashlib
import math
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from flask import Flask, render_template_string, jsonify, request
from google.cloud import bigquery

app = Flask(__name__)

# BigQuery client (initialized on first request)
bq_client = None

# Cache directory for images
CACHE_DIR = Path("tools/output/images")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def safe_float(val, default=None):
    """Convert to float safely, handling NaN, Inf, and None.
    
    Args:
        val: Value to convert to float
        default: Default value if conversion fails or result is NaN/Inf
        
    Returns:
        Float value or default if invalid
    """
    if val is None:
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


def get_bq_client():
    """Get or create BigQuery client."""
    global bq_client
    if bq_client is None:
        bq_client = bigquery.Client()
    return bq_client


def query_sessions(
    category: Optional[str] = None,
    segment: Optional[str] = None,
    surface: Optional[str] = None,
    country: Optional[str] = None,
    days_back: int = 7,
    limit: int = 10,
    min_items: int = 4,
    require_purchase: bool = True
) -> List[Dict]:
    """Query BigQuery for real session data with product details."""
    
    client = get_bq_client()
    
    # Build WHERE clauses for filters
    where_clauses = [
        f"DATE(imp.event_timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL {days_back} DAY)",
        "imp.section_y_pos > 0",
        "imp.section_y_pos <= 10",
        "imp.entity_type = 'product'",
        "imp.section_id IN ('products_from_merchant_discovery_recs', 'minis_shoppable_video', 'merchant_rec_with_deals')",
    ]
    
    if surface and surface != 'all':
        where_clauses.append(f"imp.surface = '{surface}'")
    
    # Build country join clause if needed
    country_join = ""
    country_filter = ""
    if country and country != 'all':
        country_join = """
      INNER JOIN `sdp-prd-shop-ml.mart.mart__shop_app__deduped_user_dimension` ud
        ON imp.user_id = ud.deduped_user_id"""
        country_filter = f" AND ud.last.geo.country = '{country}'"
    
    # Build the query
    query = f"""
    WITH purchase_sessions AS (
      -- Find sessions with purchases (for interesting examples)
      SELECT DISTINCT imp.session_id
      FROM `sdp-prd-shop-ml.product_recommendation.intermediate__shop_personalization__recs_impressions_enriched` imp
      {country_join}
      WHERE DATE(imp.event_timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL {days_back} DAY)
        AND imp.section_y_pos > 0
        AND imp.section_y_pos <= 10
        AND imp.entity_type = 'product'
        AND imp.section_id IN ('products_from_merchant_discovery_recs', 'minis_shoppable_video', 'merchant_rec_with_deals')
        {"AND imp.has_1d_any_touch_attr_order = true" if require_purchase else "AND (imp.is_clicked OR imp.has_1d_any_touch_attr_order)"}
        {country_filter}
      LIMIT 100
    ),
    
    session_items AS (
      SELECT
        imp.session_id,
        imp.user_id,
        CAST(imp.entity_id AS INT64) AS product_id,
        imp.section_y_pos AS position,
        imp.surface,
        imp.is_clicked,
        imp.has_1d_any_touch_attr_order AS has_purchase,
        ARRAY_TO_STRING(ARRAY(SELECT cg.cg_algorithm_name FROM UNNEST(cg_sources) AS cg LIMIT 1), '') AS cg_source,
        FORMAT_TIMESTAMP('%Y-%m-%d %H:%M', imp.event_timestamp) AS event_time,
        ROW_NUMBER() OVER (PARTITION BY imp.session_id, imp.section_y_pos ORDER BY imp.event_timestamp) AS rn
      FROM `sdp-prd-shop-ml.product_recommendation.intermediate__shop_personalization__recs_impressions_enriched` imp
      INNER JOIN purchase_sessions ps ON imp.session_id = ps.session_id
      WHERE {' AND '.join(where_clauses)}
    ),
    
    deduped_items AS (
      SELECT * FROM session_items WHERE rn = 1
    ),
    
    enriched AS (
      SELECT
        di.session_id,
        di.user_id,
        di.product_id,
        di.position,
        di.surface,
        di.is_clicked,
        di.has_purchase,
        COALESCE(di.cg_source, 'unknown') AS cg_source,
        di.event_time,
        COALESCE(p.title, 'Unknown Product') AS product_title,
        COALESCE(p.vendor, 'Unknown') AS vendor,
        COALESCE(p.category, 'Uncategorized') AS category,
        img.image_cdn_url AS product_image_url
      FROM deduped_items di
      LEFT JOIN `sdp-prd-merchandising.products_and_pricing_intermediate.products_extended` p
        ON di.product_id = p.product_id
      LEFT JOIN `sdp-prd-shop-ml.intermediate.intermediate__product_images_v2` img
        ON di.product_id = img.product_id AND img.position = 1 AND img.is_deleted = false
    ),
    
    session_stats AS (
      SELECT 
        session_id,
        COUNT(DISTINCT position) AS num_positions,
        MAX(CASE WHEN has_purchase THEN 1 ELSE 0 END) AS has_any_purchase,
        MAX(CASE WHEN is_clicked THEN 1 ELSE 0 END) AS has_any_click
      FROM enriched
      GROUP BY session_id
      HAVING COUNT(DISTINCT position) >= {min_items}
    )
    
    SELECT 
      e.*,
      ss.num_positions
    FROM enriched e
    INNER JOIN session_stats ss ON e.session_id = ss.session_id
    ORDER BY e.session_id, e.position
    LIMIT 500
    """
    
    try:
        results = client.query(query).to_dataframe()
        
        # Group by session
        sessions = []
        for session_id, group in results.groupby('session_id'):
            group = group.sort_values('position')
            
            # Get unique items by position
            seen_positions = set()
            items = []
            for _, row in group.iterrows():
                if row['position'] not in seen_positions:
                    seen_positions.add(row['position'])
                    items.append({
                        'position': int(row['position']),
                        'product_id': str(row['product_id']),
                        'product_title': row['product_title'][:50] if row['product_title'] else 'Unknown',
                        'product_image_url': row['product_image_url'],
                        'vendor': row['vendor'] or 'Unknown',
                        'category': row['category'] or 'Uncategorized',
                        'clicked': bool(row['is_clicked']),
                        'purchased': bool(row['has_purchase']),
                        'cg_source': row['cg_source'] or 'unknown'
                    })
            
            if len(items) >= min_items:
                # Determine primary category (most common)
                categories = [i['category'] for i in items if i['category'] != 'Uncategorized']
                primary_category = max(set(categories), key=categories.count) if categories else 'Uncategorized'
                
                # Determine user segment (simplified)
                user_id = group.iloc[0]['user_id']
                if user_id and user_id > 0:
                    segment = 'returning'
                else:
                    segment = 'anonymous'
                
                sessions.append({
                    'session_id': session_id[:20],
                    'user_segment': segment,
                    'surface': group.iloc[0]['surface'],
                    'timestamp': group.iloc[0]['event_time'],
                    'primary_category': primary_category,
                    'trigger_context': f"Browsing {primary_category}",
                    'items': sorted(items, key=lambda x: x['position'])[:6]
                })
        
        # Apply category filter (post-query for flexibility)
        if category and category != 'all':
            sessions = [s for s in sessions if category.lower() in s['primary_category'].lower()]
        
        # Apply segment filter
        if segment and segment != 'all':
            sessions = [s for s in sessions if s['user_segment'] == segment]
        
        return sessions[:limit]
        
    except Exception as e:
        print(f"Query error: {e}")
        return []


def get_filter_options():
    """Get available filter options from recent data including buyer countries."""
    client = get_bq_client()
    
    # Query for surfaces and categories
    query = """
    SELECT DISTINCT
      surface,
      COALESCE(p.category, 'Uncategorized') as category
    FROM `sdp-prd-shop-ml.product_recommendation.intermediate__shop_personalization__recs_impressions_enriched` imp
    LEFT JOIN `sdp-prd-merchandising.products_and_pricing_intermediate.products_extended` p
      ON CAST(imp.entity_id AS INT64) = p.product_id
    WHERE DATE(imp.event_timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY)
      AND imp.entity_type = 'product'
      AND imp.section_id IN ('products_from_merchant_discovery_recs', 'minis_shoppable_video', 'merchant_rec_with_deals')
    LIMIT 1000
    """
    
    # Query for top buyer countries
    country_query = """
    SELECT 
      last.geo.country AS buyer_country,
      COUNT(DISTINCT deduped_user_id) AS user_count
    FROM `sdp-prd-shop-ml.mart.mart__shop_app__deduped_user_dimension`
    WHERE last.geo.country IS NOT NULL
    GROUP BY buyer_country
    ORDER BY user_count DESC
    LIMIT 20
    """
    
    try:
        results = client.query(query).to_dataframe()
        surfaces = sorted(results['surface'].dropna().unique().tolist())
        categories = sorted([c for c in results['category'].dropna().unique().tolist() if c != 'Uncategorized'])[:20]
        
        # Get countries
        country_results = client.query(country_query).to_dataframe()
        countries = country_results['buyer_country'].dropna().tolist()
        
        return {
            'surfaces': surfaces,
            'categories': categories,
            'segments': ['returning', 'anonymous'],
            'countries': countries
        }
    except Exception as e:
        print(f"Error getting filter options: {e}")
        return {
            'surfaces': ['super_feed', 'pdp', 'search'],
            'categories': ['Beauty', 'Electronics', 'Apparel & Accessories', 'Home & Kitchen'],
            'segments': ['returning', 'anonymous'],
            'countries': ['US', 'CA', 'GB', 'AU', 'DE', 'FR', 'JP', 'MX', 'BR', 'IN']
        }


# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NDCG Visualizer | Live Data</title>
    <style>
        :root {
            --bg-primary: #0a0a0f;
            --bg-secondary: #12121a;
            --bg-card: #1a1a24;
            --text-primary: #e8e8ed;
            --text-secondary: #8888a0;
            --accent-green: #22c55e;
            --accent-blue: #3b82f6;
            --accent-purple: #a855f7;
            --accent-orange: #f97316;
            --accent-red: #ef4444;
            --border-color: #2a2a3a;
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            min-height: 100vh;
        }
        
        .container { max-width: 1600px; margin: 0 auto; padding: 1.5rem; }
        
        header {
            text-align: center;
            margin-bottom: 1.5rem;
            padding: 1.5rem;
            background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--bg-card) 100%);
            border-radius: 16px;
            border: 1px solid var(--border-color);
        }
        
        header h1 {
            font-size: 2rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        header p { color: var(--text-secondary); font-size: 0.95rem; margin-top: 0.25rem; }
        .live-badge { 
            display: inline-block; 
            background: var(--accent-green); 
            color: white; 
            padding: 0.2rem 0.6rem; 
            border-radius: 20px; 
            font-size: 0.7rem; 
            font-weight: 700;
            margin-left: 0.5rem;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
        
        .controls {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.25rem;
            margin-bottom: 1.5rem;
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            align-items: flex-end;
        }
        
        .filter-group { display: flex; flex-direction: column; gap: 0.4rem; }
        .filter-group label { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; color: var(--accent-purple); }
        .filter-group select, .filter-group input {
            padding: 0.6rem 0.8rem;
            border-radius: 8px;
            border: 1px solid var(--border-color);
            background: var(--bg-secondary);
            color: var(--text-primary);
            font-size: 0.9rem;
            min-width: 150px;
        }
        .filter-group select:focus, .filter-group input:focus { outline: none; border-color: var(--accent-purple); }
        
        .btn {
            padding: 0.6rem 1.2rem;
            border-radius: 8px;
            border: none;
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-primary {
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
            color: white;
        }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 4px 20px rgba(168, 85, 247, 0.4); }
        .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        .btn-secondary {
            background: var(--bg-secondary);
            color: var(--text-primary);
            border: 1px solid var(--border-color);
        }
        .btn-secondary:hover { border-color: var(--accent-purple); }
        
        .stats-bar { display: flex; gap: 1.5rem; margin-left: auto; align-items: center; }
        .stat { text-align: center; }
        .stat-value { font-size: 1.3rem; font-weight: 700; color: var(--accent-blue); }
        .stat-label { font-size: 0.65rem; text-transform: uppercase; color: var(--text-secondary); }
        
        /* Metrics Dashboard */
        .metrics-dashboard {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.25rem;
            margin-bottom: 1.5rem;
        }
        .metrics-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }
        .metrics-header h2 {
            font-size: 1rem;
            color: var(--accent-purple);
            text-transform: uppercase;
            letter-spacing: 1px;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .metrics-header .refresh-btn {
            padding: 0.4rem 0.8rem;
            font-size: 0.8rem;
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 1rem;
        }
        .metric-card {
            background: var(--bg-secondary);
            border-radius: 8px;
            padding: 1rem;
            text-align: center;
            border: 1px solid var(--border-color);
            transition: border-color 0.2s;
        }
        .metric-card:hover {
            border-color: var(--accent-purple);
        }
        .metric-card.highlight {
            border-color: var(--accent-green);
            background: rgba(34, 197, 94, 0.1);
        }
        .metric-card .value {
            font-size: 1.5rem;
            font-weight: 700;
            font-family: 'SF Mono', monospace;
            color: var(--text-primary);
        }
        .metric-card .value.good { color: var(--accent-green); }
        .metric-card .value.warning { color: var(--accent-orange); }
        .metric-card .value.bad { color: var(--accent-red); }
        .metric-card .label {
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--text-secondary);
            margin-top: 0.25rem;
        }
        .metric-card .sublabel {
            font-size: 0.65rem;
            color: var(--text-secondary);
            opacity: 0.7;
        }
        .metrics-loading {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 2rem;
            color: var(--text-secondary);
        }
        .metrics-loading .spinner-small {
            width: 20px;
            height: 20px;
            border: 2px solid var(--border-color);
            border-top-color: var(--accent-purple);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 0.75rem;
        }
        .metrics-section {
            margin-top: 1rem;
            padding-top: 1rem;
            border-top: 1px solid var(--border-color);
        }
        .metrics-section h3 {
            font-size: 0.75rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 0.75rem;
        }
        .metrics-row {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
            gap: 0.75rem;
        }
        .mini-metric {
            background: var(--bg-primary);
            border-radius: 6px;
            padding: 0.5rem 0.75rem;
            text-align: center;
        }
        .mini-metric .value {
            font-size: 1.1rem;
            font-weight: 700;
            font-family: 'SF Mono', monospace;
        }
        .mini-metric .label {
            font-size: 0.6rem;
            text-transform: uppercase;
            color: var(--text-secondary);
        }
        
        .loading {
            text-align: center;
            padding: 3rem;
            color: var(--text-secondary);
        }
        .loading .spinner {
            width: 40px;
            height: 40px;
            border: 3px solid var(--border-color);
            border-top-color: var(--accent-purple);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 1rem;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        
        .sessions-container { display: flex; flex-direction: column; gap: 1.5rem; }
        
        .session-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            overflow: hidden;
        }
        
        .session-header {
            background: var(--bg-card);
            padding: 1rem 1.25rem;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 0.75rem;
        }
        
        .session-info { display: flex; gap: 1.25rem; flex-wrap: wrap; align-items: center; }
        .session-info span { color: var(--text-secondary); font-size: 0.8rem; }
        .session-info strong { color: var(--text-primary); }
        
        .session-tags { display: flex; gap: 0.4rem; }
        .tag { padding: 0.2rem 0.6rem; border-radius: 20px; font-size: 0.7rem; font-weight: 600; }
        .tag.category { background: rgba(168, 85, 247, 0.2); color: var(--accent-purple); }
        .tag.segment { background: rgba(59, 130, 246, 0.2); color: var(--accent-blue); }
        .tag.surface { background: rgba(34, 197, 94, 0.2); color: var(--accent-green); }
        
        .trigger-context {
            padding: 0.6rem 1.25rem;
            background: rgba(168, 85, 247, 0.1);
            border-bottom: 1px solid var(--border-color);
            font-size: 0.85rem;
        }
        .trigger-label { color: var(--accent-purple); font-weight: 600; }
        
        .ndcg-score {
            font-size: 1.2rem;
            font-weight: 700;
            padding: 0.35rem 1rem;
            border-radius: 10px;
            background: var(--bg-primary);
        }
        .ndcg-score.excellent { color: var(--accent-green); border: 2px solid var(--accent-green); }
        .ndcg-score.good { color: var(--accent-blue); border: 2px solid var(--accent-blue); }
        .ndcg-score.fair { color: var(--accent-orange); border: 2px solid var(--accent-orange); }
        .ndcg-score.poor { color: var(--accent-red); border: 2px solid var(--accent-red); }
        
        .rankings-container { display: grid; grid-template-columns: 1fr 1fr; }
        @media (max-width: 1000px) { .rankings-container { grid-template-columns: 1fr; } }
        
        .ranking-panel { padding: 1rem; }
        .ranking-panel:first-child { border-right: 1px solid var(--border-color); }
        @media (max-width: 1000px) { .ranking-panel:first-child { border-right: none; border-bottom: 1px solid var(--border-color); } }
        
        .ranking-panel h3 {
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 0.75rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .ranking-panel h3 .dcg-value {
            font-family: 'SF Mono', monospace;
            background: var(--bg-card);
            padding: 0.15rem 0.5rem;
            border-radius: 6px;
            font-size: 0.75rem;
            margin-left: auto;
        }
        .actual h3 { color: var(--accent-orange); }
        .ideal h3 { color: var(--accent-green); }
        
        .items-list { display: flex; flex-direction: column; gap: 0.5rem; }
        
        .item {
            display: flex;
            align-items: center;
            padding: 0.5rem 0.6rem;
            background: var(--bg-card);
            border-radius: 8px;
            border: 1px solid var(--border-color);
            gap: 0.6rem;
            transition: transform 0.2s;
        }
        .item:hover { transform: translateX(3px); }
        
        .item.purchased {
            background: rgba(34, 197, 94, 0.15);
            border-color: var(--accent-green);
            box-shadow: 0 0 12px rgba(34, 197, 94, 0.2);
        }
        .item.clicked {
            background: rgba(59, 130, 246, 0.15);
            border-color: var(--accent-blue);
            box-shadow: 0 0 12px rgba(59, 130, 246, 0.2);
        }
        
        .item-position {
            width: 28px;
            height: 28px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: var(--bg-primary);
            border-radius: 6px;
            font-weight: 700;
            font-size: 0.85rem;
            flex-shrink: 0;
        }
        .item.purchased .item-position { background: var(--accent-green); color: white; }
        .item.clicked .item-position { background: var(--accent-blue); color: white; }
        
        .item-image {
            width: 50px;
            height: 50px;
            border-radius: 6px;
            overflow: hidden;
            flex-shrink: 0;
            background: var(--bg-secondary);
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
        }
        .item-image img { 
            width: 100%; 
            height: 100%; 
            object-fit: cover;
            opacity: 0;
            transition: opacity 0.3s ease;
        }
        .item-image img.loaded { opacity: 1; }
        .item-image .placeholder { 
            font-size: 0.55rem; 
            color: var(--text-secondary); 
            text-align: center; 
            padding: 0.2rem;
            position: absolute;
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            background: var(--bg-secondary);
        }
        .item-image .img-loading {
            position: absolute;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, var(--bg-secondary) 0%, var(--bg-card) 50%, var(--bg-secondary) 100%);
            background-size: 200% 100%;
            animation: shimmer 1.5s infinite;
        }
        @keyframes shimmer {
            0% { background-position: 200% 0; }
            100% { background-position: -200% 0; }
        }
        
        .item-content { flex: 1; min-width: 0; }
        .item-title {
            font-weight: 600;
            font-size: 0.8rem;
            color: var(--text-primary);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .item-vendor { font-size: 0.7rem; color: var(--text-secondary); }
        .item-meta { display: flex; gap: 0.3rem; margin-top: 0.2rem; flex-wrap: wrap; align-items: center; }
        .item-cg { font-size: 0.6rem; padding: 0.1rem 0.35rem; background: var(--bg-primary); border-radius: 4px; color: var(--accent-purple); }
        .item-relevance { font-size: 0.6rem; padding: 0.1rem 0.35rem; background: var(--bg-primary); border-radius: 4px; }
        
        .badge { font-size: 0.55rem; padding: 0.1rem 0.35rem; border-radius: 4px; font-weight: 700; text-transform: uppercase; }
        .badge.purchased { background: var(--accent-green); color: white; }
        .badge.clicked { background: var(--accent-blue); color: white; }
        
        .item-dcg {
            font-family: 'SF Mono', monospace;
            font-size: 0.75rem;
            padding: 0.15rem 0.5rem;
            background: var(--bg-primary);
            border-radius: 6px;
            flex-shrink: 0;
        }
        .item.purchased .item-dcg { color: var(--accent-green); }
        .item.clicked .item-dcg { color: var(--accent-blue); }
        
        .metrics-summary {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 0.75rem;
            padding: 0.75rem 1rem;
            background: var(--bg-card);
            border-top: 1px solid var(--border-color);
        }
        .metric { text-align: center; }
        .metric-label { font-size: 0.65rem; text-transform: uppercase; letter-spacing: 1px; color: var(--text-secondary); }
        .metric-value { font-size: 1rem; font-weight: 700; font-family: 'SF Mono', monospace; }
        
        .empty-state {
            text-align: center;
            padding: 4rem 2rem;
            color: var(--text-secondary);
        }
        .empty-state h3 { color: var(--text-primary); margin-bottom: 0.5rem; }
        
        .legend {
            display: flex;
            justify-content: center;
            gap: 1.5rem;
            margin-bottom: 1rem;
            font-size: 0.85rem;
        }
        .legend-item { display: flex; align-items: center; gap: 0.4rem; }
        .legend-color { width: 14px; height: 14px; border-radius: 4px; }
        .legend-color.purchased { background: var(--accent-green); }
        .legend-color.clicked { background: var(--accent-blue); }
        .legend-color.none { background: var(--bg-card); border: 1px solid var(--border-color); }
        
        footer {
            text-align: center;
            padding: 1.5rem;
            color: var(--text-secondary);
            font-size: 0.8rem;
        }
        footer a { color: var(--accent-blue); text-decoration: none; }
        
        /* Tabs */
        .tabs {
            display: flex;
            gap: 0;
            margin-bottom: 1.5rem;
            background: var(--bg-card);
            border-radius: 12px;
            padding: 0.25rem;
            border: 1px solid var(--border-color);
        }
        .tab {
            flex: 1;
            padding: 0.75rem 1.5rem;
            text-align: center;
            cursor: pointer;
            border-radius: 10px;
            font-weight: 600;
            color: var(--text-secondary);
            transition: all 0.2s;
        }
        .tab:hover { color: var(--text-primary); }
        .tab.active {
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
            color: white;
        }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        
        /* Optimization Panel */
        .optimization-panel {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.25rem;
            margin-bottom: 1.5rem;
        }
        .optimization-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
            flex-wrap: wrap;
            gap: 1rem;
        }
        .optimization-header h2 {
            font-size: 1rem;
            color: var(--accent-orange);
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .dimension-selector {
            display: flex;
            gap: 0.5rem;
        }
        .dimension-btn {
            padding: 0.5rem 1rem;
            border-radius: 8px;
            border: 1px solid var(--border-color);
            background: var(--bg-secondary);
            color: var(--text-secondary);
            cursor: pointer;
            font-size: 0.85rem;
            transition: all 0.2s;
        }
        .dimension-btn:hover { border-color: var(--accent-orange); }
        .dimension-btn.active {
            background: var(--accent-orange);
            color: white;
            border-color: var(--accent-orange);
        }
        
        .overall-benchmarks {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
            margin-bottom: 1.5rem;
            padding: 1rem;
            background: var(--bg-secondary);
            border-radius: 8px;
        }
        .benchmark {
            text-align: center;
        }
        .benchmark .label {
            font-size: 0.65rem;
            text-transform: uppercase;
            color: var(--text-secondary);
            margin-bottom: 0.25rem;
        }
        .benchmark .values {
            display: flex;
            justify-content: center;
            gap: 1rem;
        }
        .benchmark .value {
            font-size: 1rem;
            font-weight: 700;
            font-family: 'SF Mono', monospace;
        }
        .benchmark .value .type {
            font-size: 0.55rem;
            color: var(--text-secondary);
            display: block;
        }
        
        .optimization-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
        }
        .optimization-table th {
            text-align: left;
            padding: 0.75rem 0.5rem;
            border-bottom: 2px solid var(--border-color);
            color: var(--text-secondary);
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .optimization-table td {
            padding: 0.75rem 0.5rem;
            border-bottom: 1px solid var(--border-color);
        }
        .optimization-table tr:hover {
            background: var(--bg-secondary);
        }
        .optimization-table .dimension-name {
            font-weight: 600;
            max-width: 200px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .optimization-table .metric-value {
            font-family: 'SF Mono', monospace;
            text-align: right;
        }
        .optimization-table .metric-value.good { color: var(--accent-green); }
        .optimization-table .metric-value.warning { color: var(--accent-orange); }
        .optimization-table .metric-value.bad { color: var(--accent-red); }
        
        .delta {
            font-size: 0.7rem;
            padding: 0.15rem 0.4rem;
            border-radius: 4px;
            margin-left: 0.25rem;
        }
        .delta.positive { background: rgba(34, 197, 94, 0.2); color: var(--accent-green); }
        .delta.negative { background: rgba(239, 68, 68, 0.2); color: var(--accent-red); }
        
        .underperformer-badge {
            font-size: 0.55rem;
            padding: 0.15rem 0.4rem;
            border-radius: 4px;
            background: rgba(239, 68, 68, 0.2);
            color: var(--accent-red);
            margin-left: 0.5rem;
            font-weight: 700;
        }
        
        .opportunity-card {
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid var(--accent-red);
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 0.75rem;
        }
        .opportunity-card h4 {
            color: var(--accent-red);
            font-size: 0.9rem;
            margin-bottom: 0.5rem;
        }
        .opportunity-card p {
            font-size: 0.8rem;
            color: var(--text-secondary);
        }
        .opportunity-card .metrics {
            display: flex;
            gap: 1.5rem;
            margin-top: 0.5rem;
        }
        .opportunity-card .metric-item {
            font-family: 'SF Mono', monospace;
            font-size: 0.85rem;
        }
        .opportunity-card .metric-label {
            font-size: 0.65rem;
            color: var(--text-secondary);
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎯 NDCG Ranking Visualizer <span class="live-badge">● LIVE</span></h1>
            <p>Search real recommendation data from BigQuery</p>
        </header>
        
        <!-- Tabs -->
        <div class="tabs">
            <div class="tab active" onclick="switchTab('explorer')">🔍 Explorer</div>
            <div class="tab" onclick="switchTab('optimization')">📊 Optimization</div>
            <div class="tab" onclick="switchTab('gmv')">💰 GMV Opportunity</div>
            <div class="tab" onclick="switchTab('trends')">📈 Trends</div>
        </div>
        
        <!-- Explorer Tab Content -->
        <div id="explorer-tab" class="tab-content active">
        
        <div class="controls">
            <div class="filter-group">
                <label>Category</label>
                <select id="filter-category">
                    <option value="all">All Categories</option>
                </select>
            </div>
            <div class="filter-group">
                <label>Segment</label>
                <select id="filter-segment">
                    <option value="all">All Segments</option>
                    <option value="returning">Returning</option>
                    <option value="anonymous">Anonymous</option>
                </select>
            </div>
            <div class="filter-group">
                <label>Surface</label>
                <select id="filter-surface">
                    <option value="all">All Surfaces</option>
                </select>
            </div>
            <div class="filter-group">
                <label>Country</label>
                <select id="filter-country">
                    <option value="all">All Countries</option>
                </select>
            </div>
            <div class="filter-group">
                <label>Days Back</label>
                <input type="number" id="days-back" value="7" min="1" max="30" style="width: 80px;">
            </div>
            <div class="filter-group">
                <label>Max Results</label>
                <input type="number" id="max-results" value="10" min="1" max="50" style="width: 80px;">
            </div>
            <button class="btn btn-primary" id="search-btn" onclick="searchSessions()">🔍 Search</button>
            <button class="btn btn-secondary" onclick="resetFilters()">↺ Reset</button>
            <div class="stats-bar">
                <div class="stat">
                    <div class="stat-value" id="result-count">0</div>
                    <div class="stat-label">Results</div>
                </div>
                <div class="stat">
                    <div class="stat-value" id="avg-ndcg">--</div>
                    <div class="stat-label">Avg NDCG</div>
                </div>
            </div>
        </div>
        
        <!-- Metrics Dashboard -->
        <div class="metrics-dashboard" id="metrics-dashboard">
            <div class="metrics-header">
                <h2>📊 Performance Metrics</h2>
                <button class="btn btn-secondary refresh-btn" onclick="loadMetrics()">
                    <span id="metrics-refresh-icon">↻</span> Refresh
                </button>
            </div>
            <div id="metrics-content">
                <div class="metrics-loading">
                    <div class="spinner-small"></div>
                    <span>Click "Search" to load metrics...</span>
                </div>
            </div>
        </div>
        
        <div class="legend">
            <div class="legend-item"><div class="legend-color purchased"></div><span>Purchased (rel=4)</span></div>
            <div class="legend-item"><div class="legend-color clicked"></div><span>Clicked (rel=2)</span></div>
            <div class="legend-item"><div class="legend-color none"></div><span>No Interaction</span></div>
        </div>
        
        <div id="sessions-container" class="sessions-container">
            <div class="empty-state">
                <h3>Ready to Search</h3>
                <p>Click "Search" to query real recommendation data from BigQuery</p>
            </div>
        </div>
        
        </div><!-- End Explorer Tab -->
        
        <!-- Optimization Tab Content -->
        <div id="optimization-tab" class="tab-content">
            <div class="optimization-panel">
                <div class="optimization-header">
                    <h2>🎯 Performance Optimization</h2>
                    <div class="dimension-selector">
                        <button class="dimension-btn" onclick="loadOptimization('surface')">Overall</button>
                        <button class="dimension-btn active" onclick="loadOptimization('module')">By Module</button>
                        <button class="dimension-btn" onclick="loadOptimization('reranker')">By Reranker</button>
                        <button class="dimension-btn" onclick="loadOptimization('cg_source')">By CG Source</button>
                        <button class="dimension-btn" onclick="loadOptimization('category')">By Category</button>
                    </div>
                    <div class="filter-group">
                        <label>Days Back</label>
                        <input type="number" id="opt-days-back" value="7" min="1" max="30" style="width: 80px;">
                    </div>
                    <button class="btn btn-primary" onclick="loadOptimization()">🔄 Refresh</button>
                </div>
                
                <div class="overall-benchmarks" id="benchmarks">
                    <div class="benchmark">
                        <div class="label">NDCG</div>
                        <div class="values">
                            <div class="value"><span id="bench-ndcg-mean">--</span><span class="type">Mean</span></div>
                            <div class="value"><span id="bench-ndcg-median">--</span><span class="type">Median</span></div>
                        </div>
                    </div>
                    <div class="benchmark">
                        <div class="label">Recall@10 (Click)</div>
                        <div class="values">
                            <div class="value"><span id="bench-recall-click-mean">--</span><span class="type">Mean</span></div>
                            <div class="value"><span id="bench-recall-click-median">--</span><span class="type">Median</span></div>
                        </div>
                    </div>
                    <div class="benchmark">
                        <div class="label">Recall@10 (Purchase)</div>
                        <div class="values">
                            <div class="value"><span id="bench-recall-purch-mean">--</span><span class="type">Mean</span></div>
                            <div class="value"><span id="bench-recall-purch-median">--</span><span class="type">Median</span></div>
                        </div>
                    </div>
                    <div class="benchmark">
                        <div class="label">CTR</div>
                        <div class="values">
                            <div class="value"><span id="bench-ctr-mean">--</span><span class="type">Mean</span></div>
                        </div>
                    </div>
                </div>
                
                <div id="opportunities-container"></div>
                
                <div id="optimization-loading" class="metrics-loading" style="display: none;">
                    <div class="spinner-small"></div>
                    <span>Analyzing performance by dimension...</span>
                </div>
                
                <table class="optimization-table" id="optimization-table" style="display: none;">
                    <thead>
                        <tr>
                            <th>Dimension</th>
                            <th>Sessions</th>
                            <th>NDCG</th>
                            <th>vs Median</th>
                            <th>Recall@10 (Click)</th>
                            <th>Recall@10 (Purch)</th>
                            <th>CTR</th>
                            <th>PTR</th>
                        </tr>
                    </thead>
                    <tbody id="optimization-tbody">
                    </tbody>
                </table>
            </div>
        </div><!-- End Optimization Tab -->
        
        <!-- GMV Opportunity Tab Content -->
        <div id="gmv-tab" class="tab-content">
            <div class="optimization-panel">
                <div class="optimization-header">
                    <h2>💰 GMV Opportunity Analysis</h2>
                    <div class="dimension-selector">
                        <button class="dimension-btn" onclick="loadGmvOpportunity('surface')">Overall</button>
                        <button class="dimension-btn active" onclick="loadGmvOpportunity('module')">By Module</button>
                        <button class="dimension-btn" onclick="loadGmvOpportunity('reranker')">By Reranker</button>
                        <button class="dimension-btn" onclick="loadGmvOpportunity('cg_source')">By CG Source</button>
                        <button class="dimension-btn" onclick="loadGmvOpportunity('category')">By Category</button>
                        <button class="dimension-btn" onclick="loadGmvOpportunity('country')">By Country</button>
                    </div>
                    <div class="filter-group">
                        <label>Days Back</label>
                        <input type="number" id="gmv-days-back" value="7" min="1" max="30" style="width: 80px;">
                    </div>
                    <button class="btn btn-primary" onclick="loadGmvOpportunity()">🔄 Refresh</button>
                </div>
                
                <!-- GMV Summary Cards -->
                <div class="overall-benchmarks" id="gmv-benchmarks">
                    <div class="benchmark" style="background: linear-gradient(135deg, rgba(34, 197, 94, 0.15), rgba(34, 197, 94, 0.05)); border-color: var(--accent-green);">
                        <div class="label">Total Attributed GMV</div>
                        <div class="values">
                            <div class="value" style="color: var(--accent-green);"><span id="gmv-total">--</span><span class="type">7 Days</span></div>
                        </div>
                    </div>
                    <div class="benchmark">
                        <div class="label">Current NDCG</div>
                        <div class="values">
                            <div class="value"><span id="gmv-ndcg-avg">--</span><span class="type">Mean</span></div>
                        </div>
                    </div>
                    <div class="benchmark" style="background: linear-gradient(135deg, rgba(59, 130, 246, 0.15), rgba(59, 130, 246, 0.05)); border-color: var(--accent-blue);">
                        <div class="label">→ 0.6 NDCG</div>
                        <div class="values">
                            <div class="value" style="color: var(--accent-blue);"><span id="gmv-opp-06">--</span><span class="type">Period</span></div>
                            <div class="value" style="color: var(--accent-blue); font-size: 1.1rem;"><span id="gmv-opp-06-annual">--</span><span class="type">Annual</span></div>
                        </div>
                    </div>
                    <div class="benchmark" style="background: linear-gradient(135deg, rgba(168, 85, 247, 0.15), rgba(168, 85, 247, 0.05)); border-color: var(--accent-purple);">
                        <div class="label">→ 0.7 NDCG</div>
                        <div class="values">
                            <div class="value" style="color: var(--accent-purple);"><span id="gmv-opp-07">--</span><span class="type">Period</span></div>
                            <div class="value" style="color: var(--accent-purple); font-size: 1.1rem;"><span id="gmv-opp-07-annual">--</span><span class="type">Annual</span></div>
                        </div>
                    </div>
                    <div class="benchmark" style="background: linear-gradient(135deg, rgba(34, 197, 94, 0.15), rgba(34, 197, 94, 0.05)); border-color: var(--accent-green);">
                        <div class="label">→ 0.8 NDCG</div>
                        <div class="values">
                            <div class="value" style="color: var(--accent-green);"><span id="gmv-opp-08">--</span><span class="type">Period</span></div>
                            <div class="value" style="color: var(--accent-green); font-size: 1.1rem;"><span id="gmv-opp-08-annual">--</span><span class="type">Annual</span></div>
                        </div>
                    </div>
                </div>
                
                <div style="padding: 0.75rem 1rem; background: var(--bg-secondary); border-radius: 8px; margin-bottom: 1rem; font-size: 0.8rem; color: var(--text-secondary);">
                    <strong>💡 Model:</strong> Research suggests ~15% GMV increase per 10% NDCG improvement in ranking systems. <strong>Annual projections</strong> = period value × (365 / days_back). 
                    This table shows estimated GMV uplift if underperforming dimensions improved their NDCG to the median.
                </div>
                
                <div id="gmv-loading" class="loading-spinner" style="display: flex; justify-content: center; padding: 2rem;">
                    <span>Calculating GMV opportunity...</span>
                </div>
                
                <div id="gmv-top-opportunities" style="display: none; margin-bottom: 1rem;"></div>
                
                <table class="optimization-table" id="gmv-table" style="display: none;">
                    <thead>
                        <tr>
                            <th>Dimension</th>
                            <th>GMV</th>
                            <th>Sessions</th>
                            <th>NDCG</th>
                            <th style="color: var(--accent-blue);">→ 0.6</th>
                            <th style="color: var(--accent-purple);">→ 0.7</th>
                            <th style="color: var(--accent-green);">→ 0.8</th>
                            <th style="color: var(--accent-purple); font-weight: 700;">📅 Annual (0.7)</th>
                            <th>CTR</th>
                        </tr>
                    </thead>
                    <tbody id="gmv-tbody">
                    </tbody>
                </table>
            </div>
        </div><!-- End GMV Tab -->
        
        <!-- Trends Tab Content -->
        <div id="trends-tab" class="tab-content">
            <div class="optimization-panel">
                <div class="optimization-header">
                    <h2>📈 Time-Series Trends</h2>
                    <div class="dimension-selector">
                        <select id="trends-surface" style="background: var(--bg-secondary); color: var(--text-primary); border: 1px solid var(--border-color); padding: 0.5rem; border-radius: 6px;">
                            <option value="all">All Surfaces</option>
                            <option value="super_feed">super_feed</option>
                        </select>
                    </div>
                    <div class="filter-group" style="display: flex; align-items: center; gap: 0.5rem;">
                        <span style="color: var(--text-secondary);">Days Back</span>
                        <input type="number" id="trends-days" value="30" min="7" max="90" style="width: 80px; background: var(--bg-secondary); color: var(--text-primary); border: 1px solid var(--border-color); padding: 0.5rem; border-radius: 6px;">
                    </div>
                    <button class="dimension-btn active" onclick="loadTrends()">🔄 Refresh</button>
                </div>
                
                <div id="trends-loading" class="loading" style="display: none;">
                    <div class="spinner"></div>
                    <p>Loading trend data...</p>
                </div>
                
                <div id="trends-charts" style="display: none;">
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem;">
                        <div class="metric-summary-card" style="background: var(--bg-card); padding: 0.75rem; border-radius: 10px; border: 1px solid var(--border-color);">
                            <h3 style="color: var(--accent-green); margin-bottom: 0.5rem; font-size: 0.85rem;">📊 NDCG Over Time</h3>
                            <div style="height: 150px;"><canvas id="ndcg-chart"></canvas></div>
                        </div>
                        <div class="metric-summary-card" style="background: var(--bg-card); padding: 0.75rem; border-radius: 10px; border: 1px solid var(--border-color);">
                            <h3 style="color: var(--accent-blue); margin-bottom: 0.5rem; font-size: 0.85rem;">📍 CTR & PTR Over Time</h3>
                            <div style="height: 150px;"><canvas id="ctr-chart"></canvas></div>
                        </div>
                    </div>
                    <div class="metric-summary-card" style="background: var(--bg-card); padding: 0.75rem; border-radius: 10px; border: 1px solid var(--border-color);">
                        <h3 style="color: var(--accent-purple); margin-bottom: 0.5rem; font-size: 0.85rem;">📦 Sessions & Impressions</h3>
                        <div style="height: 120px;"><canvas id="volume-chart"></canvas></div>
                    </div>
                </div>
                
                <div id="trends-summary" style="display: none; margin-top: 1rem;">
                    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem;">
                        <div class="metric-summary-card" style="background: var(--bg-card); padding: 1rem; border-radius: 10px; border: 1px solid var(--border-color); text-align: center;">
                            <div style="font-size: 1.5rem; font-weight: 700; color: var(--accent-green);" id="trend-ndcg-change">--</div>
                            <div style="font-size: 0.8rem; color: var(--text-secondary);">NDCG Trend</div>
                        </div>
                        <div class="metric-summary-card" style="background: var(--bg-card); padding: 1rem; border-radius: 10px; border: 1px solid var(--border-color); text-align: center;">
                            <div style="font-size: 1.5rem; font-weight: 700; color: var(--accent-blue);" id="trend-ctr-change">--</div>
                            <div style="font-size: 0.8rem; color: var(--text-secondary);">CTR Trend</div>
                        </div>
                        <div class="metric-summary-card" style="background: var(--bg-card); padding: 1rem; border-radius: 10px; border: 1px solid var(--border-color); text-align: center;">
                            <div style="font-size: 1.5rem; font-weight: 700;" id="trend-avg-ndcg">--</div>
                            <div style="font-size: 0.8rem; color: var(--text-secondary);">Avg NDCG</div>
                        </div>
                        <div class="metric-summary-card" style="background: var(--bg-card); padding: 1rem; border-radius: 10px; border: 1px solid var(--border-color); text-align: center;">
                            <div style="font-size: 1.5rem; font-weight: 700;" id="trend-avg-ctr">--</div>
                            <div style="font-size: 0.8rem; color: var(--text-secondary);">Avg CTR</div>
                        </div>
                    </div>
                </div>
            </div>
        </div><!-- End Trends Tab -->
        
        <footer>
            <p>Powered by <a href="#">Dollars & Sense</a> | Querying live BigQuery data</p>
        </footer>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <script>
        // Load filter options on page load
        async function loadFilterOptions() {
            try {
                const response = await fetch('/api/filters');
                const data = await response.json();
                
                const categorySelect = document.getElementById('filter-category');
                data.categories.forEach(cat => {
                    const opt = document.createElement('option');
                    opt.value = cat;
                    opt.textContent = cat;
                    categorySelect.appendChild(opt);
                });
                
                const surfaceSelect = document.getElementById('filter-surface');
                data.surfaces.forEach(surf => {
                    const opt = document.createElement('option');
                    opt.value = surf;
                    opt.textContent = surf;
                    surfaceSelect.appendChild(opt);
                });
                
                const countrySelect = document.getElementById('filter-country');
                if (data.countries) {
                    data.countries.forEach(country => {
                        const opt = document.createElement('option');
                        opt.value = country;
                        opt.textContent = country;
                        countrySelect.appendChild(opt);
                    });
                }
            } catch (e) {
                console.error('Failed to load filters:', e);
            }
        }
        
        // NDCG calculations
        function getRelevance(item) {
            if (item.purchased) return 4;
            if (item.clicked) return 2;
            return 0;
        }
        
        function calculateDCG(items, k = 6) {
            let dcg = 0;
            for (let i = 0; i < Math.min(items.length, k); i++) {
                const rel = getRelevance(items[i]);
                dcg += rel / Math.log2(i + 2);
            }
            return dcg;
        }
        
        function calculateIDCG(items, k = 6) {
            const sorted = [...items].sort((a, b) => getRelevance(b) - getRelevance(a));
            return calculateDCG(sorted, k);
        }
        
        function calculateNDCG(items, k = 6) {
            const dcg = calculateDCG(items, k);
            const idcg = calculateIDCG(items, k);
            return idcg === 0 ? 0 : dcg / idcg;
        }
        
        function getIdealRanking(items) {
            return [...items].sort((a, b) => getRelevance(b) - getRelevance(a));
        }
        
        function getNDCGClass(ndcg) {
            if (ndcg >= 0.8) return 'excellent';
            if (ndcg >= 0.6) return 'good';
            if (ndcg >= 0.4) return 'fair';
            return 'poor';
        }
        
        function getNDCGColor(ndcg) {
            if (ndcg >= 0.8) return 'green';
            if (ndcg >= 0.6) return 'blue';
            if (ndcg >= 0.4) return 'orange';
            return 'red';
        }
        
        function renderItem(item, position) {
            const rel = getRelevance(item);
            const dcgContrib = rel > 0 ? (rel / Math.log2(position + 1)).toFixed(3) : '0.000';
            const itemClass = item.purchased ? 'purchased' : (item.clicked ? 'clicked' : '');
            const badge = item.purchased ? '<span class="badge purchased">PURCHASED</span>' : 
                          (item.clicked ? '<span class="badge clicked">CLICKED</span>' : '');
            
            const imageUrl = item.product_image_url;
            const imageHtml = imageUrl 
                ? `<div class="img-loading"></div><img src="${imageUrl}?width=80&height=80" alt="${item.product_title}" onload="this.classList.add('loaded'); this.previousElementSibling.remove();" onerror="this.parentElement.innerHTML='<div class=\\'placeholder\\'>📦</div>'">`
                : '<div class="placeholder">📦</div>';
            
            return `
                <div class="item ${itemClass}">
                    <div class="item-position">${position}</div>
                    <div class="item-image">${imageHtml}</div>
                    <div class="item-content">
                        <div class="item-title">${(item.product_title || 'Unknown').substring(0, 35)}</div>
                        <div class="item-vendor">${item.vendor || 'Unknown'}</div>
                        <div class="item-meta">
                            <span class="item-cg">${item.cg_source || 'unknown'}</span>
                            <span class="item-relevance">rel=${rel}</span>
                            ${badge}
                        </div>
                    </div>
                    <div class="item-dcg">+${dcgContrib}</div>
                </div>
            `;
        }
        
        function renderSession(session) {
            const items = session.items.slice(0, 6);
            const idealItems = getIdealRanking(items);
            const dcg = calculateDCG(items);
            const idcg = calculateIDCG(items);
            const ndcg = calculateNDCG(items);
            const loss = idcg > 0 ? ((1 - ndcg) * 100).toFixed(1) : 0;
            
            const actualItemsHtml = items.map((item, i) => renderItem(item, i + 1)).join('');
            const idealItemsHtml = idealItems.map((item, i) => renderItem(item, i + 1)).join('');
            
            return `
                <div class="session-card" data-ndcg="${ndcg}">
                    <div class="session-header">
                        <div class="session-info">
                            <span>Session: <strong>${session.session_id}</strong></span>
                            <span>Time: <strong>${session.timestamp}</strong></span>
                            <div class="session-tags">
                                <span class="tag category">${session.primary_category || 'Unknown'}</span>
                                <span class="tag segment">${session.user_segment || 'unknown'}</span>
                                <span class="tag surface">${session.surface || 'unknown'}</span>
                            </div>
                        </div>
                        <div class="ndcg-score ${getNDCGClass(ndcg)}">NDCG: ${ndcg.toFixed(3)}</div>
                    </div>
                    <div class="trigger-context">
                        <span class="trigger-label">🔍 Context:</span> ${session.trigger_context || 'Personalized recommendations'}
                    </div>
                    <div class="rankings-container">
                        <div class="ranking-panel actual">
                            <h3>📋 Actual <span class="dcg-value">DCG = ${dcg.toFixed(3)}</span></h3>
                            <div class="items-list">${actualItemsHtml}</div>
                        </div>
                        <div class="ranking-panel ideal">
                            <h3>⭐ Ideal <span class="dcg-value">IDCG = ${idcg.toFixed(3)}</span></h3>
                            <div class="items-list">${idealItemsHtml}</div>
                        </div>
                    </div>
                    <div class="metrics-summary">
                        <div class="metric"><div class="metric-label">DCG</div><div class="metric-value">${dcg.toFixed(3)}</div></div>
                        <div class="metric"><div class="metric-label">IDCG</div><div class="metric-value">${idcg.toFixed(3)}</div></div>
                        <div class="metric"><div class="metric-label">NDCG</div><div class="metric-value" style="color: var(--accent-${getNDCGColor(ndcg)})">${ndcg.toFixed(3)}</div></div>
                        <div class="metric"><div class="metric-label">Loss</div><div class="metric-value" style="color: var(--accent-orange)">${loss}%</div></div>
                    </div>
                </div>
            `;
        }
        
        async function searchSessions() {
            const btn = document.getElementById('search-btn');
            const container = document.getElementById('sessions-container');
            
            btn.disabled = true;
            btn.textContent = '⏳ Searching...';
            container.innerHTML = '<div class="loading"><div class="spinner"></div><p>Querying BigQuery...</p></div>';
            
            const params = new URLSearchParams({
                category: document.getElementById('filter-category').value,
                segment: document.getElementById('filter-segment').value,
                surface: document.getElementById('filter-surface').value,
                country: document.getElementById('filter-country').value,
                days_back: document.getElementById('days-back').value,
                limit: document.getElementById('max-results').value
            });
            
            try {
                const response = await fetch(`/api/sessions?${params}`);
                const sessions = await response.json();
                
                if (sessions.length === 0) {
                    container.innerHTML = '<div class="empty-state"><h3>No Results Found</h3><p>Try adjusting your filters or increasing the date range</p></div>';
                    document.getElementById('result-count').textContent = '0';
                    document.getElementById('avg-ndcg').textContent = '--';
                } else {
                    container.innerHTML = sessions.map(renderSession).join('');
                    
                    // Update stats
                    document.getElementById('result-count').textContent = sessions.length;
                    const avgNdcg = sessions.reduce((sum, s) => sum + calculateNDCG(s.items), 0) / sessions.length;
                    document.getElementById('avg-ndcg').textContent = avgNdcg.toFixed(3);
                }
            } catch (e) {
                container.innerHTML = `<div class="empty-state"><h3>Error</h3><p>${e.message}</p></div>`;
            }
            
            btn.disabled = false;
            btn.textContent = '🔍 Search';
        }
        
        function resetFilters() {
            document.getElementById('filter-category').value = 'all';
            document.getElementById('filter-segment').value = 'all';
            document.getElementById('filter-surface').value = 'all';
            document.getElementById('filter-country').value = 'all';
            document.getElementById('days-back').value = '7';
            document.getElementById('max-results').value = '10';
        }
        
        // Metrics loading and rendering
        async function loadMetrics() {
            const content = document.getElementById('metrics-content');
            const refreshIcon = document.getElementById('metrics-refresh-icon');
            
            refreshIcon.style.animation = 'spin 1s linear infinite';
            content.innerHTML = `
                <div class="metrics-loading">
                    <div class="spinner-small"></div>
                    <span>Computing metrics from BigQuery...</span>
                </div>
            `;
            
            const params = new URLSearchParams({
                category: document.getElementById('filter-category').value,
                segment: document.getElementById('filter-segment').value,
                surface: document.getElementById('filter-surface').value,
                country: document.getElementById('filter-country').value,
                days_back: document.getElementById('days-back').value
            });
            
            try {
                const response = await fetch(`/api/metrics?${params}`);
                const data = await response.json();
                
                if (data.error) {
                    content.innerHTML = `<div class="metrics-loading"><span>Error: ${data.error}</span></div>`;
                    return;
                }
                
                renderMetrics(data);
            } catch (e) {
                content.innerHTML = `<div class="metrics-loading"><span>Error loading metrics</span></div>`;
            }
            
            refreshIcon.style.animation = '';
        }
        
        function formatNumber(num) {
            if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
            if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
            return num.toLocaleString();
        }
        
        function getValueClass(value, type) {
            if (type === 'ndcg') {
                if (value >= 0.6) return 'good';
                if (value >= 0.4) return 'warning';
                return 'bad';
            }
            if (type === 'ctr') {
                if (value >= 5) return 'good';
                if (value >= 2) return 'warning';
                return 'bad';
            }
            if (type === 'ptr') {
                if (value >= 1) return 'good';
                if (value >= 0.3) return 'warning';
                return 'bad';
            }
            if (type === 'recall') {
                if (value >= 50) return 'good';
                if (value >= 25) return 'warning';
                return 'bad';
            }
            return '';
        }
        
        function renderMetrics(data) {
            const content = document.getElementById('metrics-content');
            
            content.innerHTML = `
                <div class="metrics-grid">
                    <div class="metric-card highlight">
                        <div class="value ${getValueClass(data.avg_ndcg, 'ndcg')}">${data.avg_ndcg.toFixed(3)}</div>
                        <div class="label">Avg NDCG</div>
                        <div class="sublabel">Ranking Quality</div>
                    </div>
                    <div class="metric-card">
                        <div class="value ${getValueClass(data.ctr, 'ctr')}">${data.ctr.toFixed(2)}%</div>
                        <div class="label">CTR</div>
                        <div class="sublabel">Click-Through Rate</div>
                    </div>
                    <div class="metric-card">
                        <div class="value ${getValueClass(data.ptr, 'ptr')}">${data.ptr.toFixed(3)}%</div>
                        <div class="label">PTR</div>
                        <div class="sublabel">Purchase-Through Rate</div>
                    </div>
                    <div class="metric-card">
                        <div class="value">${data.conversion_rate.toFixed(1)}%</div>
                        <div class="label">CVR</div>
                        <div class="sublabel">Click → Purchase</div>
                    </div>
                    <div class="metric-card">
                        <div class="value">${formatNumber(data.total_sessions)}</div>
                        <div class="label">Sessions</div>
                        <div class="sublabel">Total Analyzed</div>
                    </div>
                    <div class="metric-card">
                        <div class="value">${formatNumber(data.total_impressions)}</div>
                        <div class="label">Impressions</div>
                        <div class="sublabel">Products Shown</div>
                    </div>
                </div>
                
                <div class="metrics-section">
                    <h3>📍 Recall@K (Click) - % sessions with click in top K</h3>
                    <div class="metrics-row">
                        <div class="mini-metric">
                            <div class="value ${getValueClass(data.recall_click_at_1, 'recall')}">${data.recall_click_at_1.toFixed(1)}%</div>
                            <div class="label">@1</div>
                        </div>
                        <div class="mini-metric">
                            <div class="value ${getValueClass(data.recall_click_at_5, 'recall')}">${data.recall_click_at_5.toFixed(1)}%</div>
                            <div class="label">@5</div>
                        </div>
                        <div class="mini-metric">
                            <div class="value ${getValueClass(data.recall_click_at_10, 'recall')}">${data.recall_click_at_10.toFixed(1)}%</div>
                            <div class="label">@10</div>
                        </div>
                    </div>
                </div>
                
                <div class="metrics-section">
                    <h3>🛒 Recall@K (Purchase) - % purchase sessions with purchase in top K</h3>
                    <div class="metrics-row">
                        <div class="mini-metric">
                            <div class="value ${getValueClass(data.recall_purchase_at_1, 'recall')}">${data.recall_purchase_at_1.toFixed(1)}%</div>
                            <div class="label">@1</div>
                        </div>
                        <div class="mini-metric">
                            <div class="value ${getValueClass(data.recall_purchase_at_5, 'recall')}">${data.recall_purchase_at_5.toFixed(1)}%</div>
                            <div class="label">@5</div>
                        </div>
                        <div class="mini-metric">
                            <div class="value ${getValueClass(data.recall_purchase_at_10, 'recall')}">${data.recall_purchase_at_10.toFixed(1)}%</div>
                            <div class="label">@10</div>
                        </div>
                    </div>
                </div>
                
                <div class="metrics-section">
                    <h3>📈 Interaction Summary</h3>
                    <div class="metrics-row">
                        <div class="mini-metric">
                            <div class="value">${formatNumber(data.total_clicks)}</div>
                            <div class="label">Total Clicks</div>
                        </div>
                        <div class="mini-metric">
                            <div class="value">${formatNumber(data.total_purchases)}</div>
                            <div class="label">Total Purchases</div>
                        </div>
                        <div class="mini-metric">
                            <div class="value">${formatNumber(data.sessions_with_clicks)}</div>
                            <div class="label">Sessions w/ Click</div>
                        </div>
                        <div class="mini-metric">
                            <div class="value">${formatNumber(data.sessions_with_purchases)}</div>
                            <div class="label">Sessions w/ Purchase</div>
                        </div>
                    </div>
                </div>
            `;
        }
        
        // Modified searchSessions to also load metrics
        const originalSearchSessions = searchSessions;
        searchSessions = async function() {
            loadMetrics(); // Load metrics in parallel
            
            const btn = document.getElementById('search-btn');
            const container = document.getElementById('sessions-container');
            
            btn.disabled = true;
            btn.textContent = '⏳ Searching...';
            container.innerHTML = '<div class="loading"><div class="spinner"></div><p>Querying BigQuery...</p></div>';
            
            const params = new URLSearchParams({
                category: document.getElementById('filter-category').value,
                segment: document.getElementById('filter-segment').value,
                surface: document.getElementById('filter-surface').value,
                days_back: document.getElementById('days-back').value,
                limit: document.getElementById('max-results').value
            });
            
            try {
                const response = await fetch(`/api/sessions?${params}`);
                const sessions = await response.json();
                
                if (sessions.length === 0) {
                    container.innerHTML = '<div class="empty-state"><h3>No Results Found</h3><p>Try adjusting your filters or increasing the date range</p></div>';
                    document.getElementById('result-count').textContent = '0';
                    document.getElementById('avg-ndcg').textContent = '--';
                } else {
                    container.innerHTML = sessions.map(renderSession).join('');
                    
                    // Update stats
                    document.getElementById('result-count').textContent = sessions.length;
                    const avgNdcg = sessions.reduce((sum, s) => sum + calculateNDCG(s.items), 0) / sessions.length;
                    document.getElementById('avg-ndcg').textContent = avgNdcg.toFixed(3);
                }
            } catch (e) {
                container.innerHTML = `<div class="empty-state"><h3>Error</h3><p>${e.message}</p></div>`;
            }
            
            btn.disabled = false;
            btn.textContent = '🔍 Search';
        };
        
        // Tab switching
        function switchTab(tabName) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            const tabMap = { 'explorer': 1, 'optimization': 2, 'gmv': 3, 'trends': 4 };
            const tabIndex = tabMap[tabName] || 1;
            document.querySelector(`.tab:nth-child(${tabIndex})`).classList.add('active');
            document.getElementById(`${tabName}-tab`).classList.add('active');
            
            if (tabName === 'optimization') {
                loadOptimization();
            } else if (tabName === 'gmv') {
                loadGmvOpportunity();
            } else if (tabName === 'trends') {
                loadTrends();
            }
        }
        
        // Optimization functions
        let currentDimension = 'module';
        
        async function loadOptimization(dimension) {
            if (dimension) {
                currentDimension = dimension;
                document.querySelectorAll('.dimension-btn').forEach(b => b.classList.remove('active'));
                event.target.classList.add('active');
            }
            
            const loading = document.getElementById('optimization-loading');
            const table = document.getElementById('optimization-table');
            const tbody = document.getElementById('optimization-tbody');
            const opps = document.getElementById('opportunities-container');
            
            loading.style.display = 'flex';
            table.style.display = 'none';
            opps.innerHTML = '';
            
            const daysBack = document.getElementById('opt-days-back').value;
            
            try {
                const response = await fetch(`/api/optimization?dimension=${currentDimension}&days_back=${daysBack}`);
                const data = await response.json();
                
                if (data.error) {
                    loading.innerHTML = `<span>Error: ${data.error}</span>`;
                    return;
                }
                
                // Update benchmarks
                document.getElementById('bench-ndcg-mean').textContent = data.overall.avg_ndcg.toFixed(3);
                document.getElementById('bench-ndcg-median').textContent = data.overall.median_ndcg.toFixed(3);
                document.getElementById('bench-recall-click-mean').textContent = data.overall.avg_recall_click.toFixed(1) + '%';
                document.getElementById('bench-recall-click-median').textContent = data.overall.median_recall_click.toFixed(1) + '%';
                document.getElementById('bench-recall-purch-mean').textContent = data.overall.avg_recall_purchase.toFixed(1) + '%';
                document.getElementById('bench-recall-purch-median').textContent = data.overall.median_recall_purchase.toFixed(1) + '%';
                document.getElementById('bench-ctr-mean').textContent = data.overall.avg_ctr.toFixed(2) + '%';
                
                // Find underperformers (below median on NDCG)
                const underperformers = data.items.filter(item => 
                    item.avg_ndcg < data.overall.median_ndcg && item.sessions >= 1000
                ).slice(0, 5);
                
                // Render opportunities
                if (underperformers.length > 0) {
                    opps.innerHTML = '<h3 style="color: var(--accent-orange); margin-bottom: 1rem; font-size: 0.9rem;">🚨 Top Optimization Opportunities</h3>';
                    underperformers.forEach(item => {
                        const ndcgDelta = ((item.avg_ndcg - data.overall.median_ndcg) / data.overall.median_ndcg * 100).toFixed(1);
                        const recallDelta = ((item.recall_click_at_10 - data.overall.median_recall_click) / data.overall.median_recall_click * 100).toFixed(1);
                        opps.innerHTML += `
                            <div class="opportunity-card">
                                <h4>${item.dimension_value}</h4>
                                <p>Ranking quality is ${Math.abs(ndcgDelta)}% below median. Improving reranking here could significantly boost conversions.</p>
                                <div class="metrics">
                                    <div class="metric-item">
                                        <span style="color: var(--accent-red)">${item.avg_ndcg.toFixed(3)}</span>
                                        <span class="metric-label">NDCG (${ndcgDelta}%)</span>
                                    </div>
                                    <div class="metric-item">
                                        <span style="color: var(--accent-orange)">${item.recall_click_at_10.toFixed(1)}%</span>
                                        <span class="metric-label">Recall@10 (${recallDelta}%)</span>
                                    </div>
                                    <div class="metric-item">
                                        <span>${formatNumber(item.sessions)}</span>
                                        <span class="metric-label">Sessions</span>
                                    </div>
                                    <div class="metric-item">
                                        <span>${formatNumber(item.impressions)}</span>
                                        <span class="metric-label">Impressions</span>
                                    </div>
                                </div>
                            </div>
                        `;
                    });
                }
                
                // Render table
                tbody.innerHTML = '';
                data.items.forEach(item => {
                    const ndcgDelta = item.avg_ndcg - data.overall.median_ndcg;
                    const ndcgPct = (ndcgDelta / data.overall.median_ndcg * 100).toFixed(1);
                    const isUnderperformer = item.avg_ndcg < data.overall.median_ndcg;
                    
                    const ndcgClass = item.avg_ndcg >= data.overall.avg_ndcg ? 'good' : 
                                      item.avg_ndcg >= data.overall.median_ndcg ? 'warning' : 'bad';
                    
                    tbody.innerHTML += `
                        <tr>
                            <td class="dimension-name">
                                ${item.dimension_value}
                                ${isUnderperformer && item.sessions >= 1000 ? '<span class="underperformer-badge">OPTIMIZE</span>' : ''}
                            </td>
                            <td class="metric-value">${formatNumber(item.sessions)}</td>
                            <td class="metric-value ${ndcgClass}">${item.avg_ndcg.toFixed(3)}</td>
                            <td class="metric-value">
                                <span class="delta ${ndcgDelta >= 0 ? 'positive' : 'negative'}">${ndcgDelta >= 0 ? '+' : ''}${ndcgPct}%</span>
                            </td>
                            <td class="metric-value">${item.recall_click_at_10.toFixed(1)}%</td>
                            <td class="metric-value">${item.recall_purchase_at_10.toFixed(1)}%</td>
                            <td class="metric-value">${item.ctr.toFixed(2)}%</td>
                            <td class="metric-value">${item.ptr.toFixed(3)}%</td>
                        </tr>
                    `;
                });
                
                loading.style.display = 'none';
                table.style.display = 'table';
                
            } catch (e) {
                loading.innerHTML = `<span>Error loading optimization data: ${e.message}</span>`;
            }
        }
        
        // GMV Opportunity functions
        let gmvDimension = 'module';
        
        function formatCurrency(amount) {
            if (amount >= 1000000000) {
                return '$' + (amount / 1000000000).toFixed(2) + 'B';
            } else if (amount >= 1000000) {
                return '$' + (amount / 1000000).toFixed(2) + 'M';
            } else if (amount >= 1000) {
                return '$' + (amount / 1000).toFixed(1) + 'K';
            }
            return '$' + amount.toFixed(2);
        }
        
        async function loadGmvOpportunity(dimension) {
            if (dimension) {
                gmvDimension = dimension;
                // Update button states for GMV tab
                document.querySelectorAll('#gmv-tab .dimension-btn').forEach(b => b.classList.remove('active'));
                event.target.classList.add('active');
            }
            
            const loading = document.getElementById('gmv-loading');
            const table = document.getElementById('gmv-table');
            const tbody = document.getElementById('gmv-tbody');
            const topOpps = document.getElementById('gmv-top-opportunities');
            
            loading.style.display = 'flex';
            table.style.display = 'none';
            topOpps.style.display = 'none';
            tbody.innerHTML = '';
            
            const daysBack = document.getElementById('gmv-days-back').value;
            
            try {
                const response = await fetch(`/api/gmv_opportunity?dimension=${gmvDimension}&days_back=${daysBack}`);
                const data = await response.json();
                
                if (data.error) {
                    loading.innerHTML = `<span>Error: ${data.error}</span>`;
                    return;
                }
                
                // Update summary cards
                const daysBackVal = parseInt(daysBack) || 7;
                const annualFactor = 365 / daysBackVal;
                
                document.getElementById('gmv-total').textContent = formatCurrency(data.overall.total_gmv || 0);
                document.getElementById('gmv-ndcg-avg').textContent = (data.overall.avg_ndcg || 0).toFixed(3);
                
                // Period values
                document.getElementById('gmv-opp-06').textContent = '+' + formatCurrency(data.total_opp_06 || 0);
                document.getElementById('gmv-opp-07').textContent = '+' + formatCurrency(data.total_opp_07 || 0);
                document.getElementById('gmv-opp-08').textContent = '+' + formatCurrency(data.total_opp_08 || 0);
                
                // Annualized values
                document.getElementById('gmv-opp-06-annual').textContent = '+' + formatCurrency((data.total_opp_06 || 0) * annualFactor);
                document.getElementById('gmv-opp-07-annual').textContent = '+' + formatCurrency((data.total_opp_07 || 0) * annualFactor);
                document.getElementById('gmv-opp-08-annual').textContent = '+' + formatCurrency((data.total_opp_08 || 0) * annualFactor);
                
                // Show top 3 opportunities as cards (based on 0.7 target)
                const topItems = data.items.filter(i => i.gmv_opp_07 > 0).sort((a, b) => b.gmv_opp_07 - a.gmv_opp_07).slice(0, 3);
                if (topItems.length > 0) {
                    topOpps.innerHTML = `
                        <h3 style="font-size: 0.9rem; color: var(--accent-purple); margin-bottom: 0.75rem;">
                            🔥 Top GMV Opportunities (to reach 0.7 NDCG)
                        </h3>
                        ${topItems.map((item, idx) => {
                            const annual07 = item.gmv_opp_07 * annualFactor;
                            return `
                            <div class="opportunity-card" style="border-color: var(--accent-purple); background: rgba(168, 85, 247, 0.1);">
                                <h4 style="color: var(--accent-purple);">#${idx + 1}: ${item.dimension_value}</h4>
                                <p style="font-size: 0.8rem; color: var(--text-secondary); margin: 0.5rem 0;">
                                    Current NDCG: ${item.avg_ndcg.toFixed(3)}. 
                                    Reaching 0.7 could unlock <strong style="color: var(--accent-purple);">${formatCurrency(item.gmv_opp_07)}</strong> 
                                    (<strong style="color: var(--accent-purple);">${formatCurrency(annual07)}/yr</strong>).
                                </p>
                                <div class="opportunity-stats">
                                    <span style="background: rgba(59, 130, 246, 0.2); color: var(--accent-blue);">→0.6: ${formatCurrency(item.gmv_opp_06)}</span>
                                    <span style="background: rgba(168, 85, 247, 0.2); color: var(--accent-purple);">→0.7: ${formatCurrency(item.gmv_opp_07)} (${formatCurrency(annual07)}/yr)</span>
                                    <span style="background: rgba(34, 197, 94, 0.2); color: var(--accent-green);">→0.8: ${formatCurrency(item.gmv_opp_08)}</span>
                                </div>
                            </div>
                        `}).join('')}
                    `;
                    topOpps.style.display = 'block';
                }
                
                // Sort by annual opportunity (0.7 target) descending
                const sortedItems = [...data.items].sort((a, b) => {
                    const aOpp = (a.gmv_opp_07 || 0) * annualFactor;
                    const bOpp = (b.gmv_opp_07 || 0) * annualFactor;
                    return bOpp - aOpp;
                });
                
                // Populate table
                sortedItems.forEach(item => {
                    const hasOpp06 = item.gmv_opp_06 > 0;
                    const hasOpp07 = item.gmv_opp_07 > 0;
                    const hasOpp08 = item.gmv_opp_08 > 0;
                    const annualOpp07 = hasOpp07 ? item.gmv_opp_07 * annualFactor : 0;
                    tbody.innerHTML += `
                        <tr>
                            <td class="dimension-name">
                                ${item.dimension_value}
                                ${hasOpp07 ? '<span class="underperformer-badge" style="background: rgba(168, 85, 247, 0.2); color: var(--accent-purple);">OPPORTUNITY</span>' : ''}
                            </td>
                            <td class="metric-value" style="color: var(--accent-green);">${formatCurrency(item.gmv_usd)}</td>
                            <td class="metric-value">${(item.sessions / 1000000).toFixed(2)}M</td>
                            <td class="metric-value">${item.avg_ndcg.toFixed(3)}</td>
                            <td class="metric-value" style="${hasOpp06 ? 'color: var(--accent-blue); font-weight: 600;' : 'color: var(--text-secondary);'}">
                                ${hasOpp06 ? '+' + formatCurrency(item.gmv_opp_06) : '--'}
                            </td>
                            <td class="metric-value" style="${hasOpp07 ? 'color: var(--accent-purple); font-weight: 600;' : 'color: var(--text-secondary);'}">
                                ${hasOpp07 ? '+' + formatCurrency(item.gmv_opp_07) : '--'}
                            </td>
                            <td class="metric-value" style="${hasOpp08 ? 'color: var(--accent-green); font-weight: 600;' : 'color: var(--text-secondary);'}">
                                ${hasOpp08 ? '+' + formatCurrency(item.gmv_opp_08) : '--'}
                            </td>
                            <td class="metric-value" style="${hasOpp07 ? 'color: var(--accent-purple); font-weight: 700; background: rgba(168, 85, 247, 0.1);' : 'color: var(--text-secondary);'}">
                                ${hasOpp07 ? '+' + formatCurrency(annualOpp07) : '--'}
                            </td>
                            <td class="metric-value">${item.ctr.toFixed(2)}%</td>
                        </tr>
                    `;
                });
                
                loading.style.display = 'none';
                table.style.display = 'table';
                
            } catch (e) {
                loading.innerHTML = `<span>Error loading GMV data: ${e.message}</span>`;
            }
        }
        
        // Trends functions
        let ndcgChart = null;
        let ctrChart = null;
        let volumeChart = null;
        
        async function loadTrends() {
            const loading = document.getElementById('trends-loading');
            const charts = document.getElementById('trends-charts');
            const summary = document.getElementById('trends-summary');
            const daysBack = document.getElementById('trends-days').value;
            const surface = document.getElementById('trends-surface').value;
            
            loading.style.display = 'block';
            charts.style.display = 'none';
            summary.style.display = 'none';
            
            try {
                const response = await fetch(`/api/trends?days_back=${daysBack}&surface=${surface}`);
                const data = await response.json();
                
                if (data.error) {
                    loading.innerHTML = `<span>Error: ${data.error}</span>`;
                    return;
                }
                
                if (data.data.length === 0) {
                    loading.innerHTML = '<span>No trend data available</span>';
                    return;
                }
                
                const labels = data.data.map(d => d.date);
                const ndcgData = data.data.map(d => d.ndcg);
                const ctrData = data.data.map(d => d.ctr);
                const ptrData = data.data.map(d => d.ptr * 10); // Scale PTR for visibility
                const sessionsData = data.data.map(d => d.sessions / 1000000);
                const impressionsData = data.data.map(d => d.impressions / 1000000);
                
                // Destroy existing charts
                if (ndcgChart) ndcgChart.destroy();
                if (ctrChart) ctrChart.destroy();
                if (volumeChart) volumeChart.destroy();
                
                const chartOptions = {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: true, labels: { color: '#8888a0' } }
                    },
                    scales: {
                        x: { ticks: { color: '#8888a0', maxRotation: 45 }, grid: { color: '#2a2a3a' } },
                        y: { ticks: { color: '#8888a0' }, grid: { color: '#2a2a3a' } }
                    }
                };
                
                // NDCG Chart
                ndcgChart = new Chart(document.getElementById('ndcg-chart'), {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'NDCG',
                            data: ndcgData,
                            borderColor: '#22c55e',
                            backgroundColor: 'rgba(34, 197, 94, 0.1)',
                            fill: true,
                            tension: 0.3
                        }]
                    },
                    options: { ...chartOptions, scales: { ...chartOptions.scales, y: { ...chartOptions.scales.y, min: 0, max: 1 } } }
                });
                
                // CTR/PTR Chart
                ctrChart = new Chart(document.getElementById('ctr-chart'), {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [
                            {
                                label: 'CTR (%)',
                                data: ctrData,
                                borderColor: '#3b82f6',
                                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                                fill: false,
                                tension: 0.3
                            },
                            {
                                label: 'PTR (×10 for scale)',
                                data: ptrData,
                                borderColor: '#a855f7',
                                backgroundColor: 'rgba(168, 85, 247, 0.1)',
                                fill: false,
                                tension: 0.3
                            }
                        ]
                    },
                    options: chartOptions
                });
                
                // Volume Chart
                volumeChart = new Chart(document.getElementById('volume-chart'), {
                    type: 'bar',
                    data: {
                        labels: labels,
                        datasets: [
                            {
                                label: 'Sessions (M)',
                                data: sessionsData,
                                backgroundColor: 'rgba(168, 85, 247, 0.6)',
                                yAxisID: 'y'
                            },
                            {
                                label: 'Impressions (M)',
                                data: impressionsData,
                                backgroundColor: 'rgba(59, 130, 246, 0.4)',
                                yAxisID: 'y1'
                            }
                        ]
                    },
                    options: {
                        ...chartOptions,
                        scales: {
                            x: { ticks: { color: '#8888a0', maxRotation: 45 }, grid: { color: '#2a2a3a' } },
                            y: { type: 'linear', position: 'left', ticks: { color: '#a855f7' }, grid: { color: '#2a2a3a' } },
                            y1: { type: 'linear', position: 'right', ticks: { color: '#3b82f6' }, grid: { display: false } }
                        }
                    }
                });
                
                // Calculate trends (first week vs last week)
                const firstWeek = data.data.slice(0, 7);
                const lastWeek = data.data.slice(-7);
                
                const avgNdcgFirst = firstWeek.reduce((s, d) => s + d.ndcg, 0) / firstWeek.length;
                const avgNdcgLast = lastWeek.reduce((s, d) => s + d.ndcg, 0) / lastWeek.length;
                const ndcgChange = ((avgNdcgLast - avgNdcgFirst) / avgNdcgFirst * 100);
                
                const avgCtrFirst = firstWeek.reduce((s, d) => s + d.ctr, 0) / firstWeek.length;
                const avgCtrLast = lastWeek.reduce((s, d) => s + d.ctr, 0) / lastWeek.length;
                const ctrChange = ((avgCtrLast - avgCtrFirst) / avgCtrFirst * 100);
                
                const overallNdcg = data.data.reduce((s, d) => s + d.ndcg, 0) / data.data.length;
                const overallCtr = data.data.reduce((s, d) => s + d.ctr, 0) / data.data.length;
                
                // Update summary
                document.getElementById('trend-ndcg-change').textContent = (ndcgChange >= 0 ? '+' : '') + ndcgChange.toFixed(1) + '%';
                document.getElementById('trend-ndcg-change').style.color = ndcgChange >= 0 ? '#22c55e' : '#ef4444';
                
                document.getElementById('trend-ctr-change').textContent = (ctrChange >= 0 ? '+' : '') + ctrChange.toFixed(1) + '%';
                document.getElementById('trend-ctr-change').style.color = ctrChange >= 0 ? '#22c55e' : '#ef4444';
                
                document.getElementById('trend-avg-ndcg').textContent = overallNdcg.toFixed(3);
                document.getElementById('trend-avg-ctr').textContent = overallCtr.toFixed(2) + '%';
                
                loading.style.display = 'none';
                charts.style.display = 'block';
                summary.style.display = 'block';
                
            } catch (e) {
                loading.innerHTML = `<span>Error loading trends: ${e.message}</span>`;
            }
        }
        
        // Initialize
        loadFilterOptions();
    </script>
</body>
</html>
'''


@app.route('/')
def index():
    """Serve the main HTML page."""
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/filters')
def api_filters():
    """Return available filter options."""
    return jsonify(get_filter_options())


@app.route('/api/metrics')
def api_metrics():
    """Compute aggregate metrics for the selected filters."""
    category = request.args.get('category', 'all')
    segment = request.args.get('segment', 'all')
    surface = request.args.get('surface', 'all')
    country = request.args.get('country', 'all')
    days_back = int(request.args.get('days_back', 7))
    
    client = get_bq_client()
    
    # Build WHERE clauses
    where_clauses = [
        f"DATE(imp.event_timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL {days_back} DAY)",
        "imp.section_y_pos > 0",
        "imp.section_y_pos <= 20",
        "imp.entity_type = 'product'",
        "imp.section_id IN ('products_from_merchant_discovery_recs', 'minis_shoppable_video', 'merchant_rec_with_deals')",
    ]
    
    if surface and surface != 'all':
        where_clauses.append(f"imp.surface = '{surface}'")
    
    # Country join if needed
    country_join = ""
    if country and country != 'all':
        country_join = """
      INNER JOIN `sdp-prd-shop-ml.mart.mart__shop_app__deduped_user_dimension` ud
        ON imp.user_id = ud.deduped_user_id"""
        where_clauses.append(f"ud.last.geo.country = '{country}'")
    
    where_sql = ' AND '.join(where_clauses)
    
    query = f"""
    WITH impressions AS (
      SELECT
        imp.session_id,
        imp.section_y_pos AS position,
        imp.is_clicked,
        imp.has_1d_any_touch_attr_order AS has_purchase,
        CASE 
          WHEN imp.has_1d_any_touch_attr_order THEN 4
          WHEN imp.is_clicked THEN 2
          ELSE 0
        END AS relevance
      FROM `sdp-prd-shop-ml.product_recommendation.intermediate__shop_personalization__recs_impressions_enriched` imp
      {country_join}
      WHERE {where_sql}
    ),
    
    -- Compute ideal ranks for IDCG calculation
    impressions_with_ideal_rank AS (
      SELECT
        session_id,
        position,
        is_clicked,
        has_purchase,
        relevance,
        ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY relevance DESC, position ASC) AS ideal_rank
      FROM impressions
    ),
    
    -- Session-level metrics
    session_metrics AS (
      SELECT
        session_id,
        COUNT(*) AS impressions,
        SUM(CASE WHEN is_clicked THEN 1 ELSE 0 END) AS clicks,
        SUM(CASE WHEN has_purchase THEN 1 ELSE 0 END) AS purchases,
        MAX(CASE WHEN is_clicked AND position <= 1 THEN 1 ELSE 0 END) AS click_at_1,
        MAX(CASE WHEN is_clicked AND position <= 5 THEN 1 ELSE 0 END) AS click_at_5,
        MAX(CASE WHEN is_clicked AND position <= 10 THEN 1 ELSE 0 END) AS click_at_10,
        MAX(CASE WHEN has_purchase AND position <= 1 THEN 1 ELSE 0 END) AS purchase_at_1,
        MAX(CASE WHEN has_purchase AND position <= 5 THEN 1 ELSE 0 END) AS purchase_at_5,
        MAX(CASE WHEN has_purchase AND position <= 10 THEN 1 ELSE 0 END) AS purchase_at_10,
        -- DCG calculation (actual ranking)
        SUM(relevance / LOG(position + 1, 2)) AS dcg,
        -- IDCG calculation (ideal ranking)
        SUM(relevance / LOG(ideal_rank + 1, 2)) AS idcg
      FROM impressions_with_ideal_rank
      GROUP BY session_id
    ),
    
    -- Aggregate across sessions
    aggregates AS (
      SELECT
        COUNT(DISTINCT session_id) AS total_sessions,
        SUM(impressions) AS total_impressions,
        SUM(clicks) AS total_clicks,
        SUM(purchases) AS total_purchases,
        
        -- CTR and PTR
        SAFE_DIVIDE(SUM(clicks), SUM(impressions)) * 100 AS ctr,
        SAFE_DIVIDE(SUM(purchases), SUM(impressions)) * 100 AS ptr,
        SAFE_DIVIDE(SUM(purchases), SUM(clicks)) * 100 AS conversion_rate,
        
        -- Recall@K (% of sessions with click/purchase in top K)
        SAFE_DIVIDE(SUM(click_at_1), COUNT(*)) * 100 AS recall_click_at_1,
        SAFE_DIVIDE(SUM(click_at_5), COUNT(*)) * 100 AS recall_click_at_5,
        SAFE_DIVIDE(SUM(click_at_10), COUNT(*)) * 100 AS recall_click_at_10,
        SAFE_DIVIDE(SUM(purchase_at_1), NULLIF(SUM(CASE WHEN purchases > 0 THEN 1 ELSE 0 END), 0)) * 100 AS recall_purchase_at_1,
        SAFE_DIVIDE(SUM(purchase_at_5), NULLIF(SUM(CASE WHEN purchases > 0 THEN 1 ELSE 0 END), 0)) * 100 AS recall_purchase_at_5,
        SAFE_DIVIDE(SUM(purchase_at_10), NULLIF(SUM(CASE WHEN purchases > 0 THEN 1 ELSE 0 END), 0)) * 100 AS recall_purchase_at_10,
        
        -- Average NDCG
        AVG(SAFE_DIVIDE(dcg, NULLIF(idcg, 0))) AS avg_ndcg,
        
        -- Sessions with interactions
        SUM(CASE WHEN clicks > 0 THEN 1 ELSE 0 END) AS sessions_with_clicks,
        SUM(CASE WHEN purchases > 0 THEN 1 ELSE 0 END) AS sessions_with_purchases
      FROM session_metrics
    )
    
    SELECT * FROM aggregates
    """
    
    try:
        result = client.query(query).to_dataframe()
        
        if len(result) == 0:
            return jsonify({'error': 'No data found'})
        
        row = result.iloc[0]
        
        return jsonify({
            'total_sessions': int(row['total_sessions']) if row['total_sessions'] else 0,
            'total_impressions': int(row['total_impressions']) if row['total_impressions'] else 0,
            'total_clicks': int(row['total_clicks']) if row['total_clicks'] else 0,
            'total_purchases': int(row['total_purchases']) if row['total_purchases'] else 0,
            
            'ctr': float(row['ctr']) if row['ctr'] else 0,
            'ptr': float(row['ptr']) if row['ptr'] else 0,
            'conversion_rate': float(row['conversion_rate']) if row['conversion_rate'] else 0,
            
            'recall_click_at_1': float(row['recall_click_at_1']) if row['recall_click_at_1'] else 0,
            'recall_click_at_5': float(row['recall_click_at_5']) if row['recall_click_at_5'] else 0,
            'recall_click_at_10': float(row['recall_click_at_10']) if row['recall_click_at_10'] else 0,
            
            'recall_purchase_at_1': float(row['recall_purchase_at_1']) if row['recall_purchase_at_1'] else 0,
            'recall_purchase_at_5': float(row['recall_purchase_at_5']) if row['recall_purchase_at_5'] else 0,
            'recall_purchase_at_10': float(row['recall_purchase_at_10']) if row['recall_purchase_at_10'] else 0,
            
            'avg_ndcg': float(row['avg_ndcg']) if row['avg_ndcg'] else 0,
            
            'sessions_with_clicks': int(row['sessions_with_clicks']) if row['sessions_with_clicks'] else 0,
            'sessions_with_purchases': int(row['sessions_with_purchases']) if row['sessions_with_purchases'] else 0,
        })
    except Exception as e:
        print(f"Metrics query error: {e}")
        return jsonify({'error': str(e)})


@app.route('/api/optimization')
def api_optimization():
    """Compute metrics broken down by dimension for optimization analysis."""
    dimension = request.args.get('dimension', 'module')  # module, surface, segment, category, reranker, cg_source
    days_back = int(request.args.get('days_back', 7))
    
    client = get_bq_client()
    
    # Map dimension to BigQuery column
    dim_column_map = {
        'surface': 'imp.surface',
        'module': 'imp.section_id',
        'reranker': 'COALESCE(imp.algorithm_id, "unknown")',
        'cg_source': 'cg.cg_algorithm_name',
        'segment': 'CASE WHEN imp.user_id > 0 THEN "returning" ELSE "anonymous" END',
        'category': 'COALESCE(p.category, "Uncategorized")'
    }
    
    dim_column = dim_column_map.get(dimension, 'imp.section_id')
    needs_product_join = dimension == 'category'
    needs_cg_unnest = dimension == 'cg_source'
    
    # For CG source, we need to UNNEST the cg_sources array
    cg_unnest = ", UNNEST(imp.cg_sources) AS cg" if needs_cg_unnest else ""
    cg_filter = "AND cg.cg_algorithm_name IS NOT NULL" if needs_cg_unnest else ""
    
    query = f"""
    WITH impressions AS (
      SELECT
        imp.session_id,
        {dim_column} AS dimension_value,
        imp.section_y_pos AS position,
        imp.is_clicked,
        imp.has_1d_any_touch_attr_order AS has_purchase,
        CASE 
          WHEN imp.has_1d_any_touch_attr_order THEN 4
          WHEN imp.is_clicked THEN 2
          ELSE 0
        END AS relevance
      FROM `sdp-prd-shop-ml.product_recommendation.intermediate__shop_personalization__recs_impressions_enriched` imp
      {cg_unnest}
      {"LEFT JOIN `sdp-prd-merchandising.products_and_pricing_intermediate.products_extended` p ON CAST(imp.entity_id AS INT64) = p.product_id" if needs_product_join else ""}
      WHERE DATE(imp.event_timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL {days_back} DAY)
        AND imp.section_y_pos > 0
        AND imp.section_y_pos <= 20
        AND imp.entity_type = 'product'
        AND imp.section_id IN ('products_from_merchant_discovery_recs', 'minis_shoppable_video', 'merchant_rec_with_deals')
        {cg_filter}
    ),
    
    -- Compute ideal ranks for IDCG
    impressions_ranked AS (
      SELECT
        *,
        ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY relevance DESC, position ASC) AS ideal_rank
      FROM impressions
    ),
    
    -- Session-level metrics
    session_metrics AS (
      SELECT
        session_id,
        dimension_value,
        COUNT(*) AS impressions,
        SUM(CASE WHEN is_clicked THEN 1 ELSE 0 END) AS clicks,
        SUM(CASE WHEN has_purchase THEN 1 ELSE 0 END) AS purchases,
        MAX(CASE WHEN is_clicked AND position <= 5 THEN 1 ELSE 0 END) AS click_at_5,
        MAX(CASE WHEN is_clicked AND position <= 10 THEN 1 ELSE 0 END) AS click_at_10,
        MAX(CASE WHEN has_purchase AND position <= 5 THEN 1 ELSE 0 END) AS purchase_at_5,
        MAX(CASE WHEN has_purchase AND position <= 10 THEN 1 ELSE 0 END) AS purchase_at_10,
        SUM(relevance / LOG(position + 1, 2)) AS dcg,
        SUM(relevance / LOG(ideal_rank + 1, 2)) AS idcg
      FROM impressions_ranked
      GROUP BY session_id, dimension_value
    ),
    
    -- Aggregated by dimension
    dimension_metrics AS (
      SELECT
        dimension_value,
        COUNT(DISTINCT session_id) AS sessions,
        SUM(impressions) AS total_impressions,
        SUM(clicks) AS total_clicks,
        SUM(purchases) AS total_purchases,
        
        SAFE_DIVIDE(SUM(clicks), SUM(impressions)) * 100 AS ctr,
        SAFE_DIVIDE(SUM(purchases), SUM(impressions)) * 100 AS ptr,
        
        AVG(SAFE_DIVIDE(dcg, NULLIF(idcg, 0))) AS avg_ndcg,
        
        SAFE_DIVIDE(SUM(click_at_5), COUNT(*)) * 100 AS recall_click_at_5,
        SAFE_DIVIDE(SUM(click_at_10), COUNT(*)) * 100 AS recall_click_at_10,
        SAFE_DIVIDE(SUM(purchase_at_5), NULLIF(SUM(CASE WHEN purchases > 0 THEN 1 ELSE 0 END), 0)) * 100 AS recall_purchase_at_5,
        SAFE_DIVIDE(SUM(purchase_at_10), NULLIF(SUM(CASE WHEN purchases > 0 THEN 1 ELSE 0 END), 0)) * 100 AS recall_purchase_at_10
      FROM session_metrics
      GROUP BY dimension_value
      HAVING COUNT(DISTINCT session_id) >= 100  -- Only include dimensions with enough data
    ),
    
    -- Overall metrics for comparison
    overall AS (
      SELECT
        AVG(avg_ndcg) AS overall_avg_ndcg,
        APPROX_QUANTILES(avg_ndcg, 2)[OFFSET(1)] AS overall_median_ndcg,
        AVG(recall_click_at_10) AS overall_avg_recall_click,
        APPROX_QUANTILES(recall_click_at_10, 2)[OFFSET(1)] AS overall_median_recall_click,
        AVG(recall_purchase_at_10) AS overall_avg_recall_purchase,
        APPROX_QUANTILES(recall_purchase_at_10, 2)[OFFSET(1)] AS overall_median_recall_purchase,
        AVG(ctr) AS overall_avg_ctr,
        AVG(ptr) AS overall_avg_ptr
      FROM dimension_metrics
    )
    
    SELECT
      dm.*,
      o.overall_avg_ndcg,
      o.overall_median_ndcg,
      o.overall_avg_recall_click,
      o.overall_median_recall_click,
      o.overall_avg_recall_purchase,
      o.overall_median_recall_purchase,
      o.overall_avg_ctr,
      o.overall_avg_ptr
    FROM dimension_metrics dm
    CROSS JOIN overall o
    ORDER BY dm.avg_ndcg ASC
    LIMIT 100
    """
    
    try:
        result = client.query(query).to_dataframe()
        
        if len(result) == 0:
            return jsonify({'error': 'No data found', 'items': [], 'overall': {}})
        
        def safe_float(val, default=0):
            """Convert to float, handling NaN and None."""
            import math
            if val is None:
                return default
            try:
                f = float(val)
                return default if math.isnan(f) else f
            except:
                return default
        
        # Extract overall metrics from first row
        overall = {
            'avg_ndcg': safe_float(result.iloc[0]['overall_avg_ndcg']),
            'median_ndcg': safe_float(result.iloc[0]['overall_median_ndcg']),
            'avg_recall_click': safe_float(result.iloc[0]['overall_avg_recall_click']),
            'median_recall_click': safe_float(result.iloc[0]['overall_median_recall_click']),
            'avg_recall_purchase': safe_float(result.iloc[0]['overall_avg_recall_purchase']),
            'median_recall_purchase': safe_float(result.iloc[0]['overall_median_recall_purchase']),
            'avg_ctr': safe_float(result.iloc[0]['overall_avg_ctr']),
            'avg_ptr': safe_float(result.iloc[0]['overall_avg_ptr']),
        }
        
        items = []
        for _, row in result.iterrows():
            items.append({
                'dimension_value': str(row['dimension_value']) if row['dimension_value'] else 'Unknown',
                'sessions': int(row['sessions']) if row['sessions'] else 0,
                'impressions': int(row['total_impressions']) if row['total_impressions'] else 0,
                'clicks': int(row['total_clicks']) if row['total_clicks'] else 0,
                'purchases': int(row['total_purchases']) if row['total_purchases'] else 0,
                'ctr': safe_float(row['ctr']),
                'ptr': safe_float(row['ptr']),
                'avg_ndcg': safe_float(row['avg_ndcg']),
                'recall_click_at_5': safe_float(row['recall_click_at_5']),
                'recall_click_at_10': safe_float(row['recall_click_at_10']),
                'recall_purchase_at_5': safe_float(row['recall_purchase_at_5']),
                'recall_purchase_at_10': safe_float(row['recall_purchase_at_10']),
            })
        
        return jsonify({
            'dimension': dimension,
            'overall': overall,
            'items': items,
            'count': len(items)
        })
        
    except Exception as e:
        print(f"Optimization query error: {e}")
        return jsonify({'error': str(e), 'items': [], 'overall': {}})


@app.route('/api/gmv_opportunity')
def api_gmv_opportunity():
    """Compute GMV opportunity analysis by dimension.
    
    Calculates current GMV, NDCG, and potential GMV uplift if NDCG improved to median.
    
    The GMV opportunity model:
    - Current attributed GMV from recommendations
    - NDCG score indicating ranking quality
    - Estimated uplift based on improving NDCG to median
    
    Research suggests ~10-30% GMV increase per 10% NDCG improvement in ranking systems.
    We use a conservative 15% GMV lift per 10% NDCG improvement.
    """
    dimension = request.args.get('dimension', 'module')
    days_back = int(request.args.get('days_back', 7))
    
    client = get_bq_client()
    
    # Map dimension to columns
    dim_column_map = {
        'surface': 'imp.surface',
        'module': 'imp.section_id',
        'reranker': 'COALESCE(imp.algorithm_id, "unknown")',
        'cg_source': 'cg.cg_algorithm_name',
        'segment': 'CASE WHEN imp.user_id > 0 THEN "Returning" ELSE "Anonymous" END',
        'category': 'COALESCE(p.category, "Uncategorized")',
        'country': 'COALESCE(ud.last.geo.country, "Unknown")'
    }
    
    dim_column = dim_column_map.get(dimension, 'imp.section_id')
    needs_product_join = dimension == 'category'
    needs_user_join = dimension == 'country'
    needs_cg_unnest = dimension == 'cg_source'
    
    # For CG source, we need to UNNEST the cg_sources array (in addition to orders)
    cg_unnest = ", UNNEST(imp.cg_sources) AS cg" if needs_cg_unnest else ""
    cg_filter = "AND cg.cg_algorithm_name IS NOT NULL" if needs_cg_unnest else ""
    
    query = f"""
    WITH impressions AS (
      SELECT
        imp.session_id,
        {dim_column} AS dimension_value,
        CAST(imp.entity_id AS INT64) AS product_id,
        imp.section_y_pos AS position,
        imp.is_clicked,
        imp.has_1d_any_touch_attr_order AS has_purchase,
        CASE 
          WHEN imp.has_1d_any_touch_attr_order THEN 4
          WHEN imp.is_clicked THEN 2
          ELSE 0
        END AS relevance,
        orders.order_id AS attributed_order_id
      FROM `sdp-prd-shop-ml.product_recommendation.intermediate__shop_personalization__recs_impressions_enriched` imp
      LEFT JOIN UNNEST(imp.any_touch_attr_orders) AS orders
        ON orders.is_attributable_to_product_click = TRUE
      {cg_unnest}
      {"LEFT JOIN `sdp-prd-merchandising.products_and_pricing_intermediate.products_extended` p ON CAST(imp.entity_id AS INT64) = p.product_id" if needs_product_join else ""}
      {"LEFT JOIN `sdp-prd-shop-ml.mart.mart__shop_app__deduped_user_dimension` ud ON imp.user_id = ud.deduped_user_id" if needs_user_join else ""}
      WHERE DATE(imp.event_timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL {days_back} DAY)
        AND imp.section_y_pos > 0
        AND imp.section_y_pos <= 20
        AND imp.entity_type = 'product'
        AND imp.section_id IN ('products_from_merchant_discovery_recs', 'minis_shoppable_video', 'merchant_rec_with_deals')
        {cg_filter}
    ),
    
    -- Get GMV for attributed orders
    impressions_with_gmv AS (
      SELECT
        i.*,
        COALESCE(c.expected_gmv_usd, 0) AS attributed_gmv_usd
      FROM impressions i
      LEFT JOIN `sdp-prd-shop-ml.intermediate.intermediate__staging__shop_app__attributed_conversions` c
        ON i.product_id = c.product_id
        AND i.attributed_order_id = c.order_id
        AND DATE(c.order_created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL {days_back} DAY)
    ),
    
    -- Compute ideal ranks for IDCG
    impressions_ranked AS (
      SELECT
        *,
        ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY relevance DESC, position ASC) AS ideal_rank
      FROM impressions_with_gmv
    ),
    
    -- Session-level metrics
    session_metrics AS (
      SELECT
        session_id,
        dimension_value,
        COUNT(*) AS impressions,
        SUM(CASE WHEN is_clicked THEN 1 ELSE 0 END) AS clicks,
        SUM(CASE WHEN has_purchase THEN 1 ELSE 0 END) AS purchases,
        SUM(attributed_gmv_usd) AS session_gmv_usd,
        SUM(relevance / LOG(position + 1, 2)) AS dcg,
        SUM(relevance / LOG(ideal_rank + 1, 2)) AS idcg
      FROM impressions_ranked
      GROUP BY session_id, dimension_value
    ),
    
    -- Aggregated by dimension with GMV
    dimension_metrics AS (
      SELECT
        dimension_value,
        COUNT(DISTINCT session_id) AS sessions,
        SUM(impressions) AS total_impressions,
        SUM(clicks) AS total_clicks,
        SUM(purchases) AS total_purchases,
        SUM(session_gmv_usd) AS total_gmv_usd,
        
        SAFE_DIVIDE(SUM(clicks), SUM(impressions)) * 100 AS ctr,
        SAFE_DIVIDE(SUM(purchases), SUM(impressions)) * 100 AS ptr,
        
        AVG(SAFE_DIVIDE(dcg, NULLIF(idcg, 0))) AS avg_ndcg
      FROM session_metrics
      GROUP BY dimension_value
      HAVING COUNT(DISTINCT session_id) >= 50
    ),
    
    -- Overall metrics for comparison
    overall AS (
      SELECT
        AVG(avg_ndcg) AS overall_avg_ndcg,
        APPROX_QUANTILES(avg_ndcg, 2)[OFFSET(1)] AS overall_median_ndcg,
        SUM(total_gmv_usd) AS total_gmv_all,
        AVG(ctr) AS overall_avg_ctr
      FROM dimension_metrics
    )
    
    SELECT
      dm.*,
      o.overall_avg_ndcg,
      o.overall_median_ndcg,
      o.total_gmv_all,
      o.overall_avg_ctr
    FROM dimension_metrics dm
    CROSS JOIN overall o
    ORDER BY dm.total_gmv_usd DESC
    LIMIT 50
    """
    
    try:
        result = client.query(query).to_dataframe()
        
        if len(result) == 0:
            return jsonify({'error': 'No data found', 'items': [], 'overall': {}, 'total_opportunity': 0})
        
        def safe_float(val, default=0):
            """Convert to float, handling NaN and None."""
            if val is None:
                return default
            try:
                f = float(val)
                return default if math.isnan(f) else f
            except:
                return default
        
        overall_median_ndcg = safe_float(result.iloc[0]['overall_median_ndcg'])
        overall_avg_ndcg = safe_float(result.iloc[0]['overall_avg_ndcg'])
        total_gmv_all = safe_float(result.iloc[0]['total_gmv_all'])
        
        # GMV uplift factor: 15% GMV increase per 10% NDCG improvement (conservative)
        UPLIFT_FACTOR = 1.5  # 15% / 10% = 1.5
        
        # NDCG targets for opportunity calculation
        NDCG_TARGETS = [0.6, 0.7, 0.8]
        
        def calc_gmv_opportunity(current_ndcg, current_gmv, target_ndcg):
            """Calculate GMV opportunity if NDCG improves to target."""
            if current_ndcg <= 0 or current_ndcg >= target_ndcg:
                return 0
            ndcg_improvement_pct = ((target_ndcg - current_ndcg) / current_ndcg) * 100
            return current_gmv * (ndcg_improvement_pct / 100) * UPLIFT_FACTOR
        
        items = []
        total_opportunity = 0
        total_opp_06 = 0
        total_opp_07 = 0
        total_opp_08 = 0
        
        for _, row in result.iterrows():
            current_ndcg = safe_float(row['avg_ndcg'])
            current_gmv = safe_float(row['total_gmv_usd'])
            
            # Calculate opportunity: how much GMV could improve if NDCG reached median
            if current_ndcg > 0 and current_ndcg < overall_median_ndcg:
                ndcg_gap = overall_median_ndcg - current_ndcg
                ndcg_gap_pct = (ndcg_gap / current_ndcg) * 100
                potential_gmv_increase = current_gmv * (ndcg_gap_pct / 100) * UPLIFT_FACTOR
            else:
                ndcg_gap = 0
                ndcg_gap_pct = 0
                potential_gmv_increase = 0
            
            # Calculate opportunity at specific NDCG targets
            opp_06 = calc_gmv_opportunity(current_ndcg, current_gmv, 0.6)
            opp_07 = calc_gmv_opportunity(current_ndcg, current_gmv, 0.7)
            opp_08 = calc_gmv_opportunity(current_ndcg, current_gmv, 0.8)
            
            total_opportunity += potential_gmv_increase
            total_opp_06 += opp_06
            total_opp_07 += opp_07
            total_opp_08 += opp_08
            
            items.append({
                'dimension_value': str(row['dimension_value']) if row['dimension_value'] else 'Unknown',
                'sessions': int(row['sessions']) if row['sessions'] else 0,
                'impressions': int(row['total_impressions']) if row['total_impressions'] else 0,
                'clicks': int(row['total_clicks']) if row['total_clicks'] else 0,
                'purchases': int(row['total_purchases']) if row['total_purchases'] else 0,
                'gmv_usd': current_gmv,
                'ctr': safe_float(row['ctr']),
                'ptr': safe_float(row['ptr']),
                'avg_ndcg': current_ndcg,
                'ndcg_gap': ndcg_gap,
                'ndcg_gap_pct': ndcg_gap_pct,
                'gmv_opportunity': potential_gmv_increase,
                'gmv_opp_06': opp_06,
                'gmv_opp_07': opp_07,
                'gmv_opp_08': opp_08,
            })
        
        # Sort by GMV opportunity (highest first)
        items.sort(key=lambda x: x['gmv_opportunity'], reverse=True)
        
        return jsonify({
            'dimension': dimension,
            'days_back': days_back,
            'overall': {
                'avg_ndcg': overall_avg_ndcg,
                'median_ndcg': overall_median_ndcg,
                'total_gmv': total_gmv_all,
            },
            'items': items,
            'total_opportunity': total_opportunity,
            'total_opp_06': total_opp_06,
            'total_opp_07': total_opp_07,
            'total_opp_08': total_opp_08,
            'count': len(items),
            'uplift_model': f'{int(UPLIFT_FACTOR * 10)}% GMV increase per 10% NDCG improvement'
        })
        
    except Exception as e:
        print(f"GMV opportunity query error: {e}")
        return jsonify({'error': str(e), 'items': [], 'overall': {}, 'total_opportunity': 0})


@app.route('/api/trends')
def api_trends():
    """Return time-series metrics data for trend analysis."""
    days_back = int(request.args.get('days_back', 30))
    surface = request.args.get('surface', 'all')
    
    client = get_bq_client()
    
    # Build surface filter
    surface_filter = ""
    if surface and surface != 'all':
        surface_filter = f"AND surface = '{surface}'"
    
    query = f"""
    WITH daily_impressions AS (
      SELECT
        DATE(event_timestamp) AS event_date,
        session_id,
        section_y_pos AS position,
        is_clicked,
        has_1d_any_touch_attr_order AS has_purchase,
        CASE 
          WHEN has_1d_any_touch_attr_order THEN 4
          WHEN is_clicked THEN 2
          ELSE 0
        END AS relevance
      FROM `sdp-prd-shop-ml.product_recommendation.intermediate__shop_personalization__recs_impressions_enriched`
      WHERE DATE(event_timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL {days_back} DAY)
        AND DATE(event_timestamp) < CURRENT_DATE()
        AND section_y_pos > 0
        AND section_y_pos <= 20
        AND entity_type = 'product'
        AND section_id IN ('products_from_merchant_discovery_recs', 'minis_shoppable_video', 'merchant_rec_with_deals')
        {surface_filter}
    ),
    
    -- Compute ideal ranks for IDCG
    impressions_ranked AS (
      SELECT
        *,
        ROW_NUMBER() OVER (PARTITION BY event_date, session_id ORDER BY relevance DESC, position ASC) AS ideal_rank
      FROM daily_impressions
    ),
    
    -- Session-level metrics
    session_metrics AS (
      SELECT
        event_date,
        session_id,
        COUNT(*) AS impressions,
        SUM(CASE WHEN is_clicked THEN 1 ELSE 0 END) AS clicks,
        SUM(CASE WHEN has_purchase THEN 1 ELSE 0 END) AS purchases,
        SUM(relevance / LOG(position + 1, 2)) AS dcg,
        SUM(relevance / LOG(ideal_rank + 1, 2)) AS idcg
      FROM impressions_ranked
      GROUP BY event_date, session_id
    ),
    
    -- Daily aggregates
    daily_metrics AS (
      SELECT
        event_date,
        COUNT(DISTINCT session_id) AS sessions,
        SUM(impressions) AS total_impressions,
        SUM(clicks) AS total_clicks,
        SUM(purchases) AS total_purchases,
        SAFE_DIVIDE(SUM(clicks), SUM(impressions)) * 100 AS ctr,
        SAFE_DIVIDE(SUM(purchases), SUM(impressions)) * 100 AS ptr,
        AVG(SAFE_DIVIDE(dcg, NULLIF(idcg, 0))) AS avg_ndcg
      FROM session_metrics
      GROUP BY event_date
    )
    
    SELECT * FROM daily_metrics
    ORDER BY event_date ASC
    """
    
    try:
        results = client.query(query).to_dataframe()
        
        # Convert to list of dicts for JSON
        data = []
        for _, row in results.iterrows():
            data.append({
                'date': row['event_date'].strftime('%Y-%m-%d'),
                'sessions': int(row['sessions']) if row['sessions'] else 0,
                'impressions': int(row['total_impressions']) if row['total_impressions'] else 0,
                'clicks': int(row['total_clicks']) if row['total_clicks'] else 0,
                'purchases': int(row['total_purchases']) if row['total_purchases'] else 0,
                'ctr': safe_float(row['ctr'], 0),
                'ptr': safe_float(row['ptr'], 0),
                'ndcg': safe_float(row['avg_ndcg'], 0),
            })
        
        return jsonify({
            'days_back': days_back,
            'surface': surface,
            'data': data
        })
        
    except Exception as e:
        print(f"Trends query error: {e}")
        return jsonify({'error': str(e), 'data': []})


@app.route('/api/sessions')
def api_sessions():
    """Query and return session data."""
    category = request.args.get('category', 'all')
    segment = request.args.get('segment', 'all')
    surface = request.args.get('surface', 'all')
    country = request.args.get('country', 'all')
    days_back = int(request.args.get('days_back', 7))
    limit = int(request.args.get('limit', 10))
    
    sessions = query_sessions(
        category=category if category != 'all' else None,
        segment=segment if segment != 'all' else None,
        surface=surface if surface != 'all' else None,
        country=country if country != 'all' else None,
        days_back=min(days_back, 30),
        limit=min(limit, 50)
    )
    
    return jsonify(sessions)


def main():
    parser = argparse.ArgumentParser(description="Run NDCG Visualizer web server")
    parser.add_argument("--port", type=int, default=8080, help="Port to run server on")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    
    args = parser.parse_args()
    
    print(f"""
╔═══════════════════════════════════════════════════════════════╗
║          NDCG Visualizer - Live Data Search                   ║
╠═══════════════════════════════════════════════════════════════╣
║  Server running at: http://localhost:{args.port}                   ║
║                                                               ║
║  Features:                                                    ║
║    • Real-time BigQuery search                                ║
║    • Filter by category, segment, surface                     ║
║    • Product images from Shopify CDN                          ║
║    • NDCG calculations with ideal ranking comparison          ║
║                                                               ║
║  Press Ctrl+C to stop                                         ║
╚═══════════════════════════════════════════════════════════════╝
""")
    
    app.run(host='0.0.0.0', port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()

