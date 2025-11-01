#!/usr/bin/env python3
"""
Fetch all orders awaiting shipment from ShipStation API (New Auth System - Bearer Token).
"""

import requests
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# ================================
# CONFIGURATION
# ================================
PRODUCTION_KEY = os.getenv("API_KEY")
# BASE_URL = 'https://ssapi.shipstation.com'
BASE_URL = 'https://apigateway.shipstation.com'
PAGE_SIZE = 50  # Maximum is 500 per API documentation

# ================================
# FUNCTIONS
# ================================

def fetch_orders_awaiting_shipment(production_key, page_size=50):
    """
    Fetch all orders with status 'awaiting_shipment' from ShipStation using Bearer token authentication.
    
    Returns:
        list: List of order dictionaries
    """
    all_orders = []
    page = 1

    headers = {
        'Authorization': f'Bearer {production_key}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    while True:
        params = {
            'orderStatus': 'awaiting_shipment',
            'pageSize': page_size,
            'page': page
        }

        response = requests.get(
            f"{BASE_URL}/orders",
            headers=headers,
            params=params
        )

        if response.status_code != 200:
            print(f"Error fetching page {page}: {response.status_code} - {response.text}")
            break

        data = response.json()
        orders = data.get('orders', [])

        if not orders:
            # No more orders left
            break

        all_orders.extend(orders)
        print(f"Fetched page {page}, {len(orders)} orders")

        page += 1

    return all_orders


def print_orders_summary(orders):
    """
    Print a simple summary of orders.
    """
    print(f"\nTotal orders awaiting shipment: {len(orders)}\n")
    for order in orders:
        print(f"Order ID: {order['orderId']}, Customer: {order['customerUsername']}, "
              f"Order Date: {order['orderDate']}, Total: {order['orderTotal']}")


# ================================
# MAIN
# ================================

def main():
    print("Fetching orders awaiting shipment from ShipStation (new API)...\n")
    orders = fetch_orders_awaiting_shipment(PRODUCTION_KEY, PAGE_SIZE)
    print_orders_summary(orders)


if __name__ == "__main__":
    main()