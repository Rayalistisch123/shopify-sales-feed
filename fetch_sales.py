import os
import json
import requests
import certifi
from dotenv import load_dotenv
from collections import defaultdict


load_dotenv()
SHOP = os.getenv('SHOP_NAME')
TOKEN = os.getenv('ACCESS_TOKEN')
API_VER = '2025-01'
BASE_URL = f'https://{SHOP}/admin/api/{API_VER}'
HEADERS = {
    'X-Shopify-Access-Token': TOKEN,
    'Content-Type': 'application/json'
}


CI = os.getenv('GITHUB_ACTIONS') is not None

VERIFY_PARAM = False if CI else certifi.where()


def get_next_link(headers):
    link = headers.get('Link', '')
    if not link:
        return None
    for part in link.split(','):
        if 'rel="next"' in part:
            return part.split(';')[0].strip()[1:-1]
    return None

# ---- 3) Haal alle betaalde orders op ----
def fetch_all_orders():
    url = f"{BASE_URL}/orders.json"
    params = {'status': 'any', 'financial_status': 'paid', 'limit': 250}
    orders = []
    while url:
        response = requests.get(
            url,
            headers=HEADERS,
            params=params,
            verify=VERIFY_PARAM
        )
        response.raise_for_status()
        batch = response.json().get('orders', [])
        orders.extend(batch)
        url = get_next_link(response.headers)
        params = {}
    return orders


def aggregate_sales_by_variant(orders):
    summary = defaultdict(lambda: {
        'ID': None,
        'VariantID': None,
        'Name': None,
        'SoldQuantity': 0,
        'RevenueTotal': 0.0
    })
    for order in orders:
        # Verzamel eerst alle refunds per variant_id
        refunded_items = defaultdict(int)
        for refund in order.get('refunds', []):
            for line_item in refund.get('refund_line_items', []):
                variant_id = line_item.get('line_item', {}).get('variant_id')
                quantity = line_item.get('quantity', 0)
                refunded_items[variant_id] += quantity

        for line in order.get('line_items', []):
            variant_id = line.get('variant_id')
            sku = line.get('sku') or f"VARIANT_{variant_id}"
            quantity = line.get('quantity', 0)
            price = float(line.get('price', 0.0))

            refunded_qty = refunded_items.get(variant_id, 0)
            sold_qty = quantity  # <- dit is bruto verkoop

            record = summary[sku]
            record['ID'] = sku
            record['VariantID'] = variant_id
            record['Name'] = line.get('title')
            record['SoldQuantity'] += sold_qty
            record['RevenueTotal'] += sold_qty * price

    return list(summary.values())

# ---- 5) Schrijf de data naar JSON ----
def main():
    orders = fetch_all_orders()
    data = aggregate_sales_by_variant(orders)
    with open('variant_sales.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("✅ variant_sales.json bijgewerkt (verify={}).".format(VERIFY_PARAM))

if __name__ == '__main__':
    main()
