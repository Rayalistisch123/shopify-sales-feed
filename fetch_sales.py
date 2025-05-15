import os
import json
import requests
import certifi
from dotenv import load_dotenv
from collections import defaultdict

# 1) Laad credentials uit .env\load_dotenv()
SHOP = os.getenv('SHOP_NAME')
TOKEN = os.getenv('ACCESS_TOKEN')
API_VER = '2025-01'
BASE_URL = f'https://{SHOP}/admin/api/{API_VER}'
HEADERS = {
    'X-Shopify-Access-Token': TOKEN,
    'Accept': 'application/json'
}

# 2) Detecteer CI en bepaal verify-parameter
CI = os.getenv('GITHUB_ACTIONS') is not None
VERIFY_PARAM = False if CI else certifi.where()

# 3) Helper voor paginatie (vind 'next' link)
def get_next_link(headers):
    link = headers.get('Link', '')
    if not link:
        return None
    for part in link.split(','):
        if 'rel="next"' in part:
            return part.split(';')[0].strip()[1:-1]
    return None

# 4) Haal alle betaalde orders op
def fetch_all_orders():
    if not SHOP or not TOKEN:
        raise RuntimeError("Missing SHOP_NAME or ACCESS_TOKEN environment variables")

    url = f"{BASE_URL}/orders.json"
    params = {'status': 'any', 'financial_status': 'paid', 'limit': 250}
    orders = []
    while url:
        response = requests.get(url, headers=HEADERS, params=params, verify=VERIFY_PARAM)
        response.raise_for_status()
        batch = response.json().get('orders', [])
        orders.extend(batch)
        url = get_next_link(response.headers)
        params = {}
    return orders

# 5) Aggregatie per variant en key-accumulatie
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
        # Verzamel alle refunds per variant_id
        refunded_items = defaultdict(int)
        for refund in order.get('refunds', []):
            for li in refund.get('refund_line_items', []):
                vid = li.get('line_item', {}).get('variant_id')
                refunded_items[vid] += li.get('quantity', 0)

        for line in order.get('line_items', []):
            vid = line.get('variant_id')
            sku = line.get('sku') or f"VARIANT_{vid}"
            gross_qty = line.get('quantity', 0)
            price = float(line.get('price', 0.0))
            refunded_qty = refunded_items.get(vid, 0)
            net_qty = gross_qty - refunded_qty

            rec = summary[sku]
            # statische fields
            rec['ID'] = sku
            rec['VariantID'] = vid
            rec['Name'] = line.get('title')
            # cumulatieve velden
            rec['SoldQuantity']     += gross_qty
            rec['ReturnedQuantity'] += refunded_qty
            rec['NetQuantity']      += net_qty
            rec['GrossRevenue']     += gross_qty * price
            rec['NetRevenue']       += net_qty * price

    return list(summary.values())

# 6) Schrijf de data naar JSON (overschrijft bestand)
def main():
    orders = fetch_all_orders()
    data = aggregate_sales_by_variant(orders)
    with open('variant_sales.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ variant_sales.json bijgewerkt (verify={VERIFY_PARAM}).")

if __name__ == '__main__':
    main()
