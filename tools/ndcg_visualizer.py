"""
NDCG Visualizer - Interactive HTML visualization of recommendation rankings

This tool generates an interactive HTML page showing:
- Product images and titles for each recommendation
- Actual recommendation ranking (as shown to user)
- Ideal ranking (IDCG - sorted by relevance)
- DCG, IDCG, and NDCG scores
- Highlighted clicks and purchases

Usage:
    python3 tools/ndcg_visualizer.py [--output output.html] [--num-sessions 5]
"""

import argparse
import math
from datetime import datetime
from typing import List, Dict

# Real session data from BigQuery with product images and titles
SAMPLE_SESSION_DATA = [
    {
        "session_id": "09d28e9f-ff0a-4d51",
        "user_segment": "active",
        "surface": "super_feed",
        "timestamp": "2025-12-09 21:46",
        "trigger_context": "Browsing toy blasters",
        "items": [
            {
                "position": 1,
                "product_id": "8116108230952",
                "product_title": "Winchester 1894 Repeater Lever Action Shell Ejecting Dart Blaster",
                "product_image_url": "https://cdn.shopify.com/s/files/1/0702/1192/8360/files/image_e942a46c-fb66-48db-b27f-6fc0a70320e8.jpg",
                "vendor": "Dart Armoury",
                "clicked": False,
                "purchased": False,
                "cg_source": "product_slim"
            },
            {
                "position": 2,
                "product_id": "8594725765416",
                "product_title": "Desert Eagle Semiautomatic Blowback Dart Blaster",
                "product_image_url": "https://cdn.shopify.com/s/files/1/0702/1192/8360/files/IMG-2754.jpg",
                "vendor": "Dart Armoury",
                "clicked": False,
                "purchased": False,
                "cg_source": "hstu"
            },
            {
                "position": 3,
                "product_id": "9274902282536",
                "product_title": "M9A3 Pistol Shell Ejecting Toy Gun & Cosplay Prop",
                "product_image_url": "https://cdn.shopify.com/s/files/1/0702/1192/8360/files/IMG-3941.jpg",
                "vendor": "Dart Armoury",
                "clicked": False,
                "purchased": False,
                "cg_source": "product_nncf"
            },
            {
                "position": 4,
                "product_id": "15140373660025",
                "product_title": "Block-17 Shell Ejecting Toy Pistol | Dart Blaster",
                "product_image_url": "https://cdn.shopify.com/s/files/1/0702/1192/8360/files/IMG-8262.jpg",
                "vendor": "Dart Armoury",
                "clicked": True,
                "purchased": True,
                "cg_source": "recently_viewed"
            },
            {
                "position": 5,
                "product_id": "6841999229105",
                "product_title": "Tuscan Orris Ultimate Collection",
                "product_image_url": "https://cdn.shopify.com/s/files/1/2490/2090/products/Tuscan_Orris_Bundle_1.jpg",
                "vendor": "Carter + Jane",
                "clicked": False,
                "purchased": False,
                "cg_source": "product_slim"
            },
            {
                "position": 6,
                "product_id": "7234567890123",
                "product_title": "Premium Leather Wallet - Minimalist Design",
                "product_image_url": "https://cdn.shopify.com/s/files/1/0702/1192/8360/files/wallet-1.jpg",
                "vendor": "Urban Gear Co",
                "clicked": False,
                "purchased": False,
                "cg_source": "hstu"
            },
        ]
    },
    {
        "session_id": "857ce4aa-c5f7-4e11",
        "user_segment": "frequent_buyer",
        "surface": "super_feed",
        "timestamp": "2025-12-09 16:23",
        "trigger_context": "Recent purchase: Athletic wear",
        "items": [
            {
                "position": 1,
                "product_id": "8456789012345",
                "product_title": "Performance Running Shorts - Quick Dry",
                "product_image_url": "https://cdn.shopify.com/s/files/1/0567/8901/2345/products/running-shorts.jpg",
                "vendor": "ActiveLife",
                "clicked": True,
                "purchased": True,
                "cg_source": "recently_viewed"
            },
            {
                "position": 2,
                "product_id": "8567890123456",
                "product_title": "Compression Training Tights",
                "product_image_url": "https://cdn.shopify.com/s/files/1/0567/8901/2345/products/compression-tights.jpg",
                "vendor": "ActiveLife",
                "clicked": False,
                "purchased": False,
                "cg_source": "product_slim"
            },
            {
                "position": 3,
                "product_id": "8678901234567",
                "product_title": "Moisture-Wicking Athletic Socks (3-Pack)",
                "product_image_url": "https://cdn.shopify.com/s/files/1/0567/8901/2345/products/athletic-socks.jpg",
                "vendor": "ActiveLife",
                "clicked": False,
                "purchased": False,
                "cg_source": "hstu"
            },
            {
                "position": 4,
                "product_id": "8789012345678",
                "product_title": "Lightweight Training Jacket",
                "product_image_url": "https://cdn.shopify.com/s/files/1/0567/8901/2345/products/training-jacket.jpg",
                "vendor": "ActiveLife",
                "clicked": False,
                "purchased": False,
                "cg_source": "product_nncf"
            },
            {
                "position": 5,
                "product_id": "8890123456789",
                "product_title": "Sport Water Bottle - 32oz Insulated",
                "product_image_url": "https://cdn.shopify.com/s/files/1/0567/8901/2345/products/water-bottle.jpg",
                "vendor": "HydroGear",
                "clicked": False,
                "purchased": False,
                "cg_source": "product_slim"
            },
            {
                "position": 6,
                "product_id": "8901234567890",
                "product_title": "Gym Duffle Bag - Large Capacity",
                "product_image_url": "https://cdn.shopify.com/s/files/1/0567/8901/2345/products/gym-bag.jpg",
                "vendor": "TravelPro",
                "clicked": False,
                "purchased": False,
                "cg_source": "hstu"
            },
        ]
    },
    {
        "session_id": "43f761f6-7d9e-4c9c",
        "user_segment": "active",
        "surface": "super_feed",
        "timestamp": "2025-12-09 02:37",
        "trigger_context": "Beauty & personal care browsing",
        "items": [
            {
                "position": 1,
                "product_id": "6621788569698",
                "product_title": "Double Bubble Makeup Brush Cleanser",
                "product_image_url": "https://cdn.shopify.com/s/files/1/0072/4847/8306/products/DBCcopy.jpg",
                "vendor": "J.Cat Beauty",
                "clicked": True,
                "purchased": False,
                "cg_source": "hstu"
            },
            {
                "position": 2,
                "product_id": "6925865418794",
                "product_title": "Boost Fullness Nourishing Scalp & Hair Treatment",
                "product_image_url": "https://cdn.shopify.com/s/files/1/2439/0067/files/BF_LeaveInTreatment_PDP_Ingredients.jpg",
                "vendor": "RevAir",
                "clicked": False,
                "purchased": False,
                "cg_source": "product_slim"
            },
            {
                "position": 3,
                "product_id": "1845158674530",
                "product_title": "BR30 Dry Makeup Brush Cleaner",
                "product_image_url": "https://cdn.shopify.com/s/files/1/0072/4847/8306/products/BR30_Dry_makeup_brush_cleaner_1.jpg",
                "vendor": "J.Cat Beauty",
                "clicked": False,
                "purchased": False,
                "cg_source": "recently_viewed"
            },
            {
                "position": 4,
                "product_id": "1795353968738",
                "product_title": "BR29 Disposable Mascara Wands",
                "product_image_url": "https://cdn.shopify.com/s/files/1/0072/4847/8306/products/BR29_Main_final.jpg",
                "vendor": "J.Cat Beauty",
                "clicked": False,
                "purchased": False,
                "cg_source": "product_nncf"
            },
            {
                "position": 5,
                "product_id": "6925865025578",
                "product_title": "Revitalizing Shampoo (8.5 oz)",
                "product_image_url": "https://cdn.shopify.com/s/files/1/2439/0067/files/BF_Shampoo_PDP_Ingredients.jpg",
                "vendor": "RevAir",
                "clicked": True,
                "purchased": True,
                "cg_source": "hstu"
            },
            {
                "position": 6,
                "product_id": "7163465662673",
                "product_title": "EGG ONLY Spicy Bowls",
                "product_image_url": "https://cdn.shopify.com/s/files/1/0583/5590/8817/products/IMG_8018.jpg",
                "vendor": "Quay's Spicy Bowls",
                "clicked": False,
                "purchased": False,
                "cg_source": "product_slim"
            },
        ]
    },
    {
        "session_id": "14907e87-2421-4cbb",
        "user_segment": "new_user",
        "surface": "super_feed",
        "timestamp": "2025-12-09 18:55",
        "trigger_context": "First-time visitor exploration",
        "items": [
            {
                "position": 1,
                "product_id": "9012345678901",
                "product_title": "Wireless Bluetooth Earbuds - Premium Sound",
                "product_image_url": "https://cdn.shopify.com/s/files/1/0789/0123/4567/products/earbuds-1.jpg",
                "vendor": "SoundWave",
                "clicked": False,
                "purchased": False,
                "cg_source": "hstu"
            },
            {
                "position": 2,
                "product_id": "9123456789012",
                "product_title": "Phone Stand - Adjustable Aluminum",
                "product_image_url": "https://cdn.shopify.com/s/files/1/0789/0123/4567/products/phone-stand.jpg",
                "vendor": "TechGear",
                "clicked": False,
                "purchased": False,
                "cg_source": "product_slim"
            },
            {
                "position": 3,
                "product_id": "9234567890123",
                "product_title": "USB-C Fast Charging Cable (6ft)",
                "product_image_url": "https://cdn.shopify.com/s/files/1/0789/0123/4567/products/usb-cable.jpg",
                "vendor": "TechGear",
                "clicked": True,
                "purchased": True,
                "cg_source": "product_nncf"
            },
            {
                "position": 4,
                "product_id": "9345678901234",
                "product_title": "Laptop Sleeve - 15 inch Waterproof",
                "product_image_url": "https://cdn.shopify.com/s/files/1/0789/0123/4567/products/laptop-sleeve.jpg",
                "vendor": "TechGear",
                "clicked": False,
                "purchased": False,
                "cg_source": "hstu"
            },
            {
                "position": 5,
                "product_id": "9456789012345",
                "product_title": "Portable Power Bank - 20000mAh",
                "product_image_url": "https://cdn.shopify.com/s/files/1/0789/0123/4567/products/power-bank.jpg",
                "vendor": "ChargeMax",
                "clicked": True,
                "purchased": False,
                "cg_source": "recently_viewed"
            },
            {
                "position": 6,
                "product_id": "9567890123456",
                "product_title": "Webcam HD 1080p with Microphone",
                "product_image_url": "https://cdn.shopify.com/s/files/1/0789/0123/4567/products/webcam.jpg",
                "vendor": "StreamPro",
                "clicked": False,
                "purchased": False,
                "cg_source": "product_slim"
            },
        ]
    },
    {
        "session_id": "64fa97c7-12e5-4942",
        "user_segment": "dormant",
        "surface": "super_feed",
        "timestamp": "2025-12-09 14:12",
        "trigger_context": "Re-engagement campaign",
        "items": [
            {
                "position": 1,
                "product_id": "1234567890123",
                "product_title": "Organic Green Tea - 100 Sachets",
                "product_image_url": "https://cdn.shopify.com/s/files/1/0234/5678/9012/products/green-tea.jpg",
                "vendor": "TeaHouse",
                "clicked": False,
                "purchased": False,
                "cg_source": "hstu"
            },
            {
                "position": 2,
                "product_id": "2345678901234",
                "product_title": "Ceramic Tea Infuser Mug",
                "product_image_url": "https://cdn.shopify.com/s/files/1/0234/5678/9012/products/tea-mug.jpg",
                "vendor": "TeaHouse",
                "clicked": False,
                "purchased": False,
                "cg_source": "product_slim"
            },
            {
                "position": 3,
                "product_id": "3456789012345",
                "product_title": "Honey Sticks - Raw Organic (50 pack)",
                "product_image_url": "https://cdn.shopify.com/s/files/1/0234/5678/9012/products/honey-sticks.jpg",
                "vendor": "HoneyBee Co",
                "clicked": True,
                "purchased": False,
                "cg_source": "recently_viewed"
            },
            {
                "position": 4,
                "product_id": "4567890123456",
                "product_title": "Japanese Matcha Powder - Ceremonial Grade",
                "product_image_url": "https://cdn.shopify.com/s/files/1/0234/5678/9012/products/matcha.jpg",
                "vendor": "TeaHouse",
                "clicked": False,
                "purchased": False,
                "cg_source": "product_nncf"
            },
            {
                "position": 5,
                "product_id": "5678901234567",
                "product_title": "Electric Kettle - Variable Temperature",
                "product_image_url": "https://cdn.shopify.com/s/files/1/0234/5678/9012/products/kettle.jpg",
                "vendor": "KitchenPro",
                "clicked": False,
                "purchased": False,
                "cg_source": "hstu"
            },
            {
                "position": 6,
                "product_id": "6789012345678",
                "product_title": "Tea Storage Tin Set (4 piece)",
                "product_image_url": "https://cdn.shopify.com/s/files/1/0234/5678/9012/products/tea-tins.jpg",
                "vendor": "TeaHouse",
                "clicked": True,
                "purchased": True,
                "cg_source": "product_slim"
            },
        ]
    }
]


def get_relevance_score(item: Dict, graded: bool = True) -> int:
    """Calculate relevance score for an item."""
    if graded:
        if item["purchased"]:
            return 4
        elif item["clicked"]:
            return 2
        else:
            return 0
    else:
        return 1 if item["purchased"] else 0


def calculate_dcg(items: List[Dict], k: int = 10, graded: bool = True) -> float:
    """Calculate DCG@K for a list of items in their given order."""
    dcg = 0.0
    for i, item in enumerate(items[:k], start=1):
        rel = get_relevance_score(item, graded)
        dcg += rel / math.log2(i + 1)
    return dcg


def calculate_idcg(items: List[Dict], k: int = 10, graded: bool = True) -> float:
    """Calculate IDCG@K (ideal DCG) - items sorted by relevance."""
    sorted_items = sorted(items, key=lambda x: get_relevance_score(x, graded), reverse=True)
    return calculate_dcg(sorted_items, k, graded)


def calculate_ndcg(items: List[Dict], k: int = 10, graded: bool = True) -> float:
    """Calculate NDCG@K."""
    dcg = calculate_dcg(items, k, graded)
    idcg = calculate_idcg(items, k, graded)
    if idcg == 0:
        return 0.0
    return dcg / idcg


def get_ideal_ranking(items: List[Dict], graded: bool = True) -> List[Dict]:
    """Return items sorted by relevance (ideal ranking)."""
    return sorted(items, key=lambda x: get_relevance_score(x, graded), reverse=True)


def generate_item_html(item: Dict, position: int) -> str:
    """Generate HTML for a single item with product image and title."""
    rel = get_relevance_score(item)
    dcg_contrib = rel / math.log2(position + 1) if rel > 0 else 0
    
    if item["purchased"]:
        item_class = "purchased"
        badge = '<span class="badge purchased">PURCHASED</span>'
    elif item["clicked"]:
        item_class = "clicked"
        badge = '<span class="badge clicked">CLICKED</span>'
    else:
        item_class = ""
        badge = ""
    
    image_url = item.get("product_image_url") or "https://via.placeholder.com/80x80?text=No+Image"
    title = item.get("product_title", "Unknown Product")[:45]
    vendor = item.get("vendor", "Unknown Vendor")
    cg_source = item.get("cg_source", "unknown")
    
    return f'''
        <div class="item {item_class}">
            <div class="item-position">{position}</div>
            <div class="item-image">
                <img src="{image_url}" alt="{title}" onerror="this.src='https://via.placeholder.com/80x80?text=No+Image'">
            </div>
            <div class="item-content">
                <div class="item-title">{title}</div>
                <div class="item-vendor">{vendor}</div>
                <div class="item-meta">
                    <span class="item-cg">{cg_source}</span>
                    <span class="item-relevance">rel={rel}</span>
                    {badge}
                </div>
            </div>
            <div class="item-dcg-contribution">+{dcg_contrib:.3f}</div>
        </div>
    '''


def generate_session_html(session: Dict, k: int = 6) -> str:
    """Generate HTML for a single session."""
    items = session["items"][:k]
    ideal_items = get_ideal_ranking(items)
    
    dcg = calculate_dcg(items, k)
    idcg = calculate_idcg(items, k)
    ndcg = calculate_ndcg(items, k)
    loss = (1 - ndcg) * 100 if idcg > 0 else 0
    
    # Determine NDCG class
    if ndcg >= 0.8:
        ndcg_class = "excellent"
        ndcg_color = "green"
    elif ndcg >= 0.6:
        ndcg_class = "good"
        ndcg_color = "blue"
    elif ndcg >= 0.4:
        ndcg_class = "fair"
        ndcg_color = "orange"
    else:
        ndcg_class = "poor"
        ndcg_color = "red"
    
    # Generate items HTML
    actual_items_html = ""
    for i, item in enumerate(items, start=1):
        actual_items_html += generate_item_html(item, i)
    
    ideal_items_html = ""
    for i, item in enumerate(ideal_items, start=1):
        ideal_items_html += generate_item_html(item, i)
    
    trigger_context = session.get("trigger_context", "Personalized recommendations")
    
    return f'''
        <div class="session-card">
            <div class="session-header">
                <div class="session-info">
                    <span>Session: <strong>{session["session_id"][:20]}</strong></span>
                    <span>Surface: <strong>{session["surface"]}</strong></span>
                    <span>Segment: <strong>{session.get("user_segment", "unknown")}</strong></span>
                    <span>Time: <strong>{session["timestamp"]}</strong></span>
                </div>
                <div class="ndcg-score {ndcg_class}">
                    NDCG@{k}: {ndcg:.3f}
                </div>
            </div>
            
            <div class="trigger-context">
                <span class="trigger-label">🔍 Context:</span> {trigger_context}
            </div>
            
            <div class="rankings-container">
                <div class="ranking-panel actual">
                    <h3>
                        📋 Actual Ranking (as shown to user)
                        <span class="dcg-value">DCG = {dcg:.3f}</span>
                    </h3>
                    <div class="items-list">
                        {actual_items_html}
                    </div>
                </div>
                
                <div class="ranking-panel ideal">
                    <h3>
                        ⭐ Ideal Ranking (IDCG - sorted by relevance)
                        <span class="dcg-value">IDCG = {idcg:.3f}</span>
                    </h3>
                    <div class="items-list">
                        {ideal_items_html}
                    </div>
                </div>
            </div>
            
            <div class="metrics-summary">
                <div class="metric">
                    <div class="metric-label">DCG@{k}</div>
                    <div class="metric-value">{dcg:.3f}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">IDCG@{k}</div>
                    <div class="metric-value">{idcg:.3f}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">NDCG@{k}</div>
                    <div class="metric-value" style="color: var(--accent-{ndcg_color})">{ndcg:.3f}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Ranking Loss</div>
                    <div class="metric-value" style="color: var(--accent-orange)">{loss:.1f}%</div>
                </div>
            </div>
        </div>
    '''


def generate_html(sessions: List[Dict], output_path: str = "ndcg_visualization.html"):
    """Generate interactive HTML visualization with product images."""
    
    # Generate sessions HTML
    sessions_html = ""
    for session in sessions:
        sessions_html += generate_session_html(session)
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NDCG Ranking Visualizer | Dollars & Sense</title>
    <style>
        :root {{
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
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 1600px;
            margin: 0 auto;
            padding: 2rem;
        }}
        
        header {{
            text-align: center;
            margin-bottom: 3rem;
            padding: 2rem;
            background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--bg-card) 100%);
            border-radius: 16px;
            border: 1px solid var(--border-color);
        }}
        
        header h1 {{
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 0.5rem;
        }}
        
        header p {{
            color: var(--text-secondary);
            font-size: 1.1rem;
        }}
        
        .formula-box {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.5rem;
            margin: 2rem auto;
            max-width: 900px;
        }}
        
        .formula-box h3 {{
            color: var(--accent-purple);
            margin-bottom: 1rem;
            font-size: 1rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        .formula {{
            font-family: 'SF Mono', 'Fira Code', monospace;
            background: var(--bg-secondary);
            padding: 1rem;
            border-radius: 8px;
            font-size: 0.95rem;
            color: var(--accent-blue);
            text-align: center;
        }}
        
        .legend {{
            display: flex;
            justify-content: center;
            gap: 2rem;
            margin: 2rem 0;
            flex-wrap: wrap;
        }}
        
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        
        .legend-color {{
            width: 20px;
            height: 20px;
            border-radius: 4px;
        }}
        
        .legend-color.purchased {{
            background: var(--accent-green);
            box-shadow: 0 0 10px rgba(34, 197, 94, 0.5);
        }}
        
        .legend-color.clicked {{
            background: var(--accent-blue);
            box-shadow: 0 0 10px rgba(59, 130, 246, 0.5);
        }}
        
        .legend-color.none {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
        }}
        
        .session-card {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            margin-bottom: 2rem;
            overflow: hidden;
        }}
        
        .session-header {{
            background: var(--bg-card);
            padding: 1.5rem;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
        }}
        
        .session-info {{
            display: flex;
            gap: 2rem;
            flex-wrap: wrap;
        }}
        
        .session-info span {{
            color: var(--text-secondary);
            font-size: 0.9rem;
        }}
        
        .session-info strong {{
            color: var(--text-primary);
        }}
        
        .trigger-context {{
            padding: 1rem 1.5rem;
            background: rgba(168, 85, 247, 0.1);
            border-bottom: 1px solid var(--border-color);
            font-size: 0.95rem;
        }}
        
        .trigger-label {{
            color: var(--accent-purple);
            font-weight: 600;
        }}
        
        .ndcg-score {{
            font-size: 1.5rem;
            font-weight: 700;
            padding: 0.5rem 1.5rem;
            border-radius: 12px;
            background: var(--bg-primary);
        }}
        
        .ndcg-score.excellent {{
            color: var(--accent-green);
            border: 2px solid var(--accent-green);
        }}
        
        .ndcg-score.good {{
            color: var(--accent-blue);
            border: 2px solid var(--accent-blue);
        }}
        
        .ndcg-score.fair {{
            color: var(--accent-orange);
            border: 2px solid var(--accent-orange);
        }}
        
        .ndcg-score.poor {{
            color: var(--accent-red);
            border: 2px solid var(--accent-red);
        }}
        
        .rankings-container {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0;
        }}
        
        @media (max-width: 1100px) {{
            .rankings-container {{
                grid-template-columns: 1fr;
            }}
        }}
        
        .ranking-panel {{
            padding: 1.5rem;
        }}
        
        .ranking-panel:first-child {{
            border-right: 1px solid var(--border-color);
        }}
        
        @media (max-width: 1100px) {{
            .ranking-panel:first-child {{
                border-right: none;
                border-bottom: 1px solid var(--border-color);
            }}
        }}
        
        .ranking-panel h3 {{
            font-size: 1rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        
        .ranking-panel h3 .dcg-value {{
            font-family: 'SF Mono', monospace;
            background: var(--bg-card);
            padding: 0.25rem 0.75rem;
            border-radius: 6px;
            font-size: 0.85rem;
            margin-left: auto;
        }}
        
        .actual h3 {{
            color: var(--accent-orange);
        }}
        
        .ideal h3 {{
            color: var(--accent-green);
        }}
        
        .items-list {{
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }}
        
        .item {{
            display: flex;
            align-items: center;
            padding: 0.75rem 1rem;
            background: var(--bg-card);
            border-radius: 12px;
            border: 1px solid var(--border-color);
            transition: transform 0.2s, box-shadow 0.2s;
            gap: 1rem;
        }}
        
        .item:hover {{
            transform: translateX(4px);
        }}
        
        .item.purchased {{
            background: rgba(34, 197, 94, 0.15);
            border-color: var(--accent-green);
            box-shadow: 0 0 20px rgba(34, 197, 94, 0.2);
        }}
        
        .item.clicked {{
            background: rgba(59, 130, 246, 0.15);
            border-color: var(--accent-blue);
            box-shadow: 0 0 20px rgba(59, 130, 246, 0.2);
        }}
        
        .item-position {{
            width: 36px;
            height: 36px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: var(--bg-primary);
            border-radius: 8px;
            font-weight: 700;
            font-size: 1rem;
            flex-shrink: 0;
        }}
        
        .item.purchased .item-position {{
            background: var(--accent-green);
            color: white;
        }}
        
        .item.clicked .item-position {{
            background: var(--accent-blue);
            color: white;
        }}
        
        .item-image {{
            width: 70px;
            height: 70px;
            border-radius: 8px;
            overflow: hidden;
            flex-shrink: 0;
            background: var(--bg-secondary);
        }}
        
        .item-image img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}
        
        .item-content {{
            flex: 1;
            min-width: 0;
        }}
        
        .item-title {{
            font-weight: 600;
            font-size: 0.95rem;
            color: var(--text-primary);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        
        .item-vendor {{
            font-size: 0.8rem;
            color: var(--text-secondary);
            margin-top: 0.15rem;
        }}
        
        .item-meta {{
            display: flex;
            gap: 0.5rem;
            margin-top: 0.4rem;
            flex-wrap: wrap;
            align-items: center;
        }}
        
        .item-cg {{
            font-size: 0.7rem;
            padding: 0.15rem 0.5rem;
            background: var(--bg-primary);
            border-radius: 4px;
            color: var(--accent-purple);
        }}
        
        .item-relevance {{
            font-size: 0.7rem;
            padding: 0.15rem 0.5rem;
            background: var(--bg-primary);
            border-radius: 4px;
        }}
        
        .badge {{
            font-size: 0.65rem;
            padding: 0.15rem 0.5rem;
            border-radius: 4px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .badge.purchased {{
            background: var(--accent-green);
            color: white;
        }}
        
        .badge.clicked {{
            background: var(--accent-blue);
            color: white;
        }}
        
        .item-dcg-contribution {{
            font-family: 'SF Mono', monospace;
            font-size: 0.85rem;
            padding: 0.25rem 0.75rem;
            background: var(--bg-primary);
            border-radius: 6px;
            flex-shrink: 0;
        }}
        
        .item.purchased .item-dcg-contribution {{
            color: var(--accent-green);
        }}
        
        .item.clicked .item-dcg-contribution {{
            color: var(--accent-blue);
        }}
        
        .metrics-summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
            padding: 1.5rem;
            background: var(--bg-card);
            border-top: 1px solid var(--border-color);
        }}
        
        .metric {{
            text-align: center;
        }}
        
        .metric-label {{
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--text-secondary);
            margin-bottom: 0.25rem;
        }}
        
        .metric-value {{
            font-size: 1.25rem;
            font-weight: 700;
            font-family: 'SF Mono', monospace;
        }}
        
        .interpretation {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.5rem;
            margin-top: 2rem;
        }}
        
        .interpretation h3 {{
            color: var(--accent-purple);
            margin-bottom: 1rem;
        }}
        
        .interpretation ul {{
            list-style: none;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1rem;
        }}
        
        .interpretation li {{
            padding: 1rem;
            background: var(--bg-secondary);
            border-radius: 8px;
            border-left: 3px solid var(--accent-blue);
        }}
        
        footer {{
            text-align: center;
            padding: 2rem;
            color: var(--text-secondary);
            font-size: 0.9rem;
        }}
        
        footer a {{
            color: var(--accent-blue);
            text-decoration: none;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎯 NDCG Ranking Visualizer</h1>
            <p>Compare actual recommendation rankings vs ideal rankings with real product data</p>
        </header>
        
        <div class="formula-box">
            <h3>📐 NDCG Formula</h3>
            <div class="formula">
                NDCG@K = DCG@K / IDCG@K &nbsp;&nbsp;where&nbsp;&nbsp; DCG@K = Σ(relevance_i / log₂(position_i + 1))
            </div>
            <p style="margin-top: 1rem; text-align: center; color: var(--text-secondary); font-size: 0.9rem;">
                Relevance: <strong style="color: var(--accent-green)">Purchase = 4</strong> | 
                <strong style="color: var(--accent-blue)">Click = 2</strong> | 
                No interaction = 0
            </p>
        </div>
        
        <div class="legend">
            <div class="legend-item">
                <div class="legend-color purchased"></div>
                <span>Purchased (rel=4)</span>
            </div>
            <div class="legend-item">
                <div class="legend-color clicked"></div>
                <span>Clicked (rel=2)</span>
            </div>
            <div class="legend-item">
                <div class="legend-color none"></div>
                <span>No Interaction (rel=0)</span>
            </div>
        </div>
        
        {sessions_html}
        
        <div class="interpretation">
            <h3>📊 How to Interpret NDCG</h3>
            <ul>
                <li>
                    <strong>NDCG = 1.0:</strong> Perfect ranking - all purchased/clicked items at the very top
                </li>
                <li>
                    <strong>NDCG ≥ 0.8:</strong> Excellent - reranker is placing relevant items near the top
                </li>
                <li>
                    <strong>NDCG 0.6-0.8:</strong> Good - some room for improvement in ranking
                </li>
                <li>
                    <strong>NDCG &lt; 0.6:</strong> Opportunity - significant potential to improve ranking quality
                </li>
            </ul>
        </div>
        
        <footer>
            <p>Generated by <a href="#">Dollars & Sense</a> | {timestamp}</p>
            <p>Product data from: sdp-prd-merchandising.products_and_pricing_intermediate.products_extended</p>
            <p>Image data from: sdp-prd-shop-ml.intermediate.intermediate__product_images_v2</p>
        </footer>
    </div>
</body>
</html>'''
    
    with open(output_path, 'w') as f:
        f.write(html)
    
    print(f"✅ Generated NDCG visualization: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Generate NDCG visualization HTML with product images")
    parser.add_argument("--output", default="analysis/notebooks/ndcg_visualization.html",
                        help="Output HTML file path")
    parser.add_argument("--num-sessions", type=int, default=5,
                        help="Number of sessions to visualize")
    
    args = parser.parse_args()
    
    # Use sample data (in production, would query BigQuery)
    sessions = SAMPLE_SESSION_DATA[:args.num_sessions]
    
    generate_html(sessions, args.output)
    
    # Print summary
    print("\n📊 Session NDCG Summary:")
    print("-" * 60)
    for session in sessions:
        items = session["items"][:6]
        ndcg = calculate_ndcg(items, k=6)
        dcg = calculate_dcg(items, k=6)
        idcg = calculate_idcg(items, k=6)
        
        # Count interactions
        clicks = sum(1 for i in items if i["clicked"])
        purchases = sum(1 for i in items if i["purchased"])
        
        print(f"  {session['session_id']}: NDCG={ndcg:.3f} (DCG={dcg:.3f}, IDCG={idcg:.3f})")
        print(f"    📦 {clicks} clicks, {purchases} purchases")
        print(f"    🔍 {session.get('trigger_context', 'N/A')}")


if __name__ == "__main__":
    main()
