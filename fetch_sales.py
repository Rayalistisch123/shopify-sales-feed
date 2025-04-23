import os
import json
import requests
from dotenv import load_dotenv
from collections import defaultdict

# 1) Laad credentials
load_dotenv()
SHOP      = os.getenv('SHOP_NAME')
TOKEN     = os.getenv('ACCESS_TOKEN')
API_VER   = '2025-01'
BASE_URL  = f'https://{SHOP}/admin/api/{API_VER}'
HEADERS   = {'X-Shopify-Access-Token': TOKEN, 'Content-Type': 'application/json'}

# 2) Paginatie-helper
def get_next_link(headers):
    link = headers.get('Link','')
    for part in link.split(','):
        if 'rel="next"' in part:
            return part.split(';')[0].strip()[1:-1]
    return None

# 3) Haal alle orders op
def fetch_all_orders():
    url = f"{BASE_URL}/orders.json"
    params = {'status':'any','financial_status':'paid','limit':250}
    orders = []
    while url:
        r = requests.get(url, headers=HEADERS, params=params)
        r.raise_for_status()
        batch = r.json().get('orders', [])
        orders.extend(batch)
        url = get_next_link(r.headers)
        params = {}
    return orders

# 4) Aggregatie per variant SKU
def aggregate_sales_by_variant(orders):
    summary = defaultdict(lambda:{
        'ID': None,
        'variant_id': None,
        'Artikel': None,
        'TotaalVerkocht': 0,
        'TotaalOmzet': 0.0
    })
    for order in orders:
        for line in order.get('line_items', []):
            sku   = line.get('sku') or f"variant_{line.get('variant_id')}"
            item  = summary[sku]
            item['variant_sku']   = sku
            item['variant_id']    = line.get('variant_id')
            item['variant_title'] = line.get('title')
            q, p = line.get('quantity',0), float(line.get('price',0))
            item['total_quantity'] += q
            item['total_revenue']  += q * p
    return list(summary.values())

# 5) Schrijf JSON-bestand
if __name__ == '__main__':
    orders = fetch_all_orders()
    data   = aggregate_sales_by_variant(orders)
    with open('variant_sales.json','w',encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("✅ variant_sales.json bijgewerkt.")
