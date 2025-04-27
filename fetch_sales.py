import os
import json
import requests
import certifi
from dotenv import load_dotenv
from collections import defaultdict

# 1) Laad credentials uit .env
load_dotenv()
SHOP = os.getenv('SHOP_NAME')
TOKEN = os.getenv('ACCESS_TOKEN')
API_VER = '2025-01'
BASE_URL = f'https://{SHOP}/admin/api/{API_VER}'
HEADERS = {
    'X-Shopify-Access-Token': TOKEN,
    'Content-Type': 'application/json'
}

# 2) Helper voor paginatie (vind 'next' link)
def get_next_link(headers):
    link = headers.get('Link', '')
    for part in link.split(','):
        if 'rel="next"' in part:
            return part.split(';')[0].strip()[1:-1]
    return None

# 3) Haal alle betaalde orders op
# Voeg verify=certifi.where() toe om SSL-certificaten goed te valideren
def fetch_all_orders():
    url = f"{BASE_URL}/orders.json"
    params = {'status': 'any', 'financial_status': 'paid', 'limit': 250}
    orders = []
    while url:
        response = requests.get(
            url,
            headers=HEADERS,
            params=params,
            verify=certifi.where()
        )
        response.raise_for_status()
        batch = response.json().get('orders', [])
        orders.extend(batch)
        url = get_next_link(response.headers)
        params = {}
    return orders

# 4) Aggregeer op variant_sku en exporteer als 'ID'
def aggregate_sales_by_variant(orders):
    summary = defaultdict(lambda: {
        'ID': None,
        'VariantID': None,
        'Name': None,
        'SoldQuantity': 0,
        'RevenueTotal': 0.0
    })
    for order in orders:
        for line in order.get('line_items', []):
            # Haal de echte variant_sku op
            variant_sku = line.get('sku')
            if not variant_sku:
                # fallback naar variant_id als sku niet beschikbaar
                variant_sku = f"VARIANT_{line.get('variant_id')}"

            record = summary[variant_sku]
            record['ID'] = variant_sku
            record['VariantID'] = line.get('variant_id')
            record['Name'] = line.get('title')
            quantity = line.get('quantity', 0)
            price = float(line.get('price', 0.0))
            record['SoldQuantity'] += quantity
            record['RevenueTotal'] += quantity * price

    return list(summary.values())

# 5) Schrijf result naar variant_sales.json
def main():
    orders = fetch_all_orders()
    data = aggregate_sales_by_variant(orders)
    with open('variant_sales.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("✅ variant_sales.json bijgewerkt met variant_sku als ID.")

if __name__ == '__main__':
    main()
