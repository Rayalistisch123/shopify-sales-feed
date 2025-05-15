import os
import json
import requests
import certifi
from dotenv import load_dotenv
from collections import defaultdict

# ---- 1) Laad credentials uit .env ----
load_dotenv()
SHOP = os.getenv('SHOP_NAME')
TOKEN = os.getenv('ACCESS_TOKEN')
if not SHOP or not TOKEN:
    raise RuntimeError("Missing SHOP_NAME or ACCESS_TOKEN environment variables")

# ---- 2) API-configuratie ----
API_VER = '2025-01'
BASE_URL = f"https://{SHOP}/admin/api/{API_VER}"
HEADERS = {
    'X-Shopify-Access-Token': TOKEN,
    'Accept': 'application/json'
}

# ---- 3) SSL-verificatie ----
CI = os.getenv('GITHUB_ACTIONS') is not None
VERIFY_PARAM = False if CI else certifi.where()

# ---- 4) Paginate helper ----
def get_next_link(headers):
    link = headers.get('Link', '')
    for part in link.split(','):
        if 'rel="next"' in part:
            return part.split(';')[0].strip()[1:-1]
    return None

# ---- 5) Haal alle orders op (inclusief refunds) ----
def fetch_all_orders():
    url = f"{BASE_URL}/orders.json"
    params = {
        'status': 'any',
        'financial_status': 'any',
        'limit': 250
    }
    orders = []
    while True:
        resp = requests.get(url, headers=HEADERS, params=params, verify=VERIFY_PARAM)
        resp.raise_for_status()
        batch = resp.json().get('orders', [])
        if not batch:
            break
        orders.extend(batch)
        next_link = get_next_link(resp.headers)
        if not next_link:
            break
        url = next_link
        params = {}
    return orders

# ---- 6) Aggregatie per variant SKU met Shopify-velden ----
def aggregate_sales_by_variant(orders):
    summary = defaultdict(lambda: {
        'ID': None,
        'VariantID': None,
        'Name': None,
        'SoldQuantity': 0,
        'ReturnedQuantity': 0,
        'NetQuantity': 0,
        'GrossRevenue': 0.0,
        'NetRevenue': 0.0
    })

    for order in orders:
        for line in order.get('line_items', []):
            vid = line.get('variant_id')
            sku = line.get('sku') or f"VARIANT_{vid}"
            # Gebruik Shopify-veld names: quantity_ordered & quantity_returned
            gross_qty = line.get('quantity_ordered', line.get('quantity', 0))
            returned_qty = line.get('quantity_returned', 0)
            net_qty = gross_qty - returned_qty
            price = float(line.get('price', 0.0))

            rec = summary[sku]
            rec['ID'] = sku
            rec['VariantID'] = vid
            rec['Name'] = line.get('title')
            rec['SoldQuantity']     += gross_qty
            rec['ReturnedQuantity'] += returned_qty
            rec['NetQuantity']      += net_qty
            rec['GrossRevenue']     += gross_qty * price
            rec['NetRevenue']       += net_qty   * price

    return list(summary.values())

# ---- 7) Schrijf JSON-output ----
def main():
    orders = fetch_all_orders()
    print(f"Fetched {len(orders)} orders")  # debug
    data = aggregate_sales_by_variant(orders)
    with open('variant_sales.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ variant_sales.json bijgewerkt (verify={VERIFY_PARAM}). Totale varianten: {len(data)}")

if __name__ == '__main__':
    main()
