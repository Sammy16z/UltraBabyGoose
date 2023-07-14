# CoinbaseExchange.py file
import asyncio
import base64
import csv
import datetime
import hashlib
import hmac
import json
import logging
import time
import websocket

import numpy as np
import requests

from coinbase_advanced_trader import coinbase_client
from coinbase_advanced_trader.cb_auth import CBAuth
from coinbase_advanced_trader.coinbase_client import Side
from coinbase.wallet.client import Client

from datetime import datetime, timedelta
from enum import Enum

import CoinbaseAPI

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class CoinbaseExchange:
    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret
        self.product_ids = CoinbaseAPI.PRODUCT_IDS
        self.client = coinbase_client

        self.buyable_product_id = None
        self.sellable_product_id = None
        self.product_pair = None

        self.trade_history_file = "TradingLogs.csv"  # File to store trade history
        self.load_trade_history()  # Load existing trade history
        self.credentials = None

        self.trade_history = []  # List to store trade history
        self.usdc_balance = None

        self.price = None  # Price at which the order was executed
        self.order_id = None

        self.last_request_time = time.time()  # Initialize last_request_time

    async def update_usdc_balance(self):
        await self.rate_limit()

        accounts = self.client.getAccount('232eaaa0-2d70-5357-9848-53c1db4befcd')
        account = accounts['account']
        self.usdc_balance = float(account['available_balance']['value'])
        print(f"USDC Balance: {self.usdc_balance}")
        return self.usdc_balance

    def check_insufficient_funds(self, amount_spent):
        if self.usdc_balance is None:
            self.usdc_balance = 0.0
        elif not isinstance(self.usdc_balance, (int, float)):
            raise ValueError("Invalid USDC balance.")
        elif amount_spent > self.usdc_balance:
            return False  # Return False if there are insufficient funds
        return True  # Return True if there are sufficient funds

    def handle_failed_order(self, response):
        """
        Handles a failed order by checking the response from the API and logging the error message.
        """
        try:
            error_message = response.json()['message']
            print(f"Failed to place order: {error_message}")
            # You can add additional error handling or logging here
        except (KeyError, ValueError):
            print("Failed to place order. Error message not available.")
            # Handle the failed order in an appropriate way based on your requirements

    async def get_latest_price(self, product_id):
        await self.rate_limit()  # Enforce rate limit for public endpoint

        try:
            product = self.client.getProduct(product_id)
            if 'price' in product:
                latest_price = float(product['price'])
                return latest_price

        except Exception as e:
            print("Failed to retrieve latest price:", str(e))

        return None
        
    def loadCredentials(self, product_id, side, price, order_id):
        self.side = side
        self.price = price
        self.order_id = order_id
        now = datetime.datetime.now()
        trade = [now.date(), now.time(), product_id, side, price, order_id]
        self.add_trade_to_history(trade)

    def load_trade_history(self):
        try:
            with open(self.trade_history_file, "r") as file:
                reader = csv.reader(file)
                self.trade_history = list(reader)
        except FileNotFoundError:
            self.trade_history = []

    def save_trade_history(self):
        with open(self.trade_history_file, "a", newline="") as file:  # Use "a" mode to append data
            writer = csv.writer(file)
            writer.writerows(self.trade_history)

    def add_trade_to_history(self, trade):
        trade_data = [str(value) for value in trade]
        self.trade_history.append(trade_data)
        self.save_trade_history()
        
    '''def get_buyable_product_id(self):
        for product_id in self.product_ids:
            if self.should_buy(product_id):
                self.buyable_product_id = product_id
                break

        return self.buyable_product_id

    def get_sellable_product_id(self):
        for product_id in self.product_ids:
            if self.should_sell(product_id):
                self.sellable_product_id = product_id
                break

        return self.sellable_product_id'''

    async def rate_limit(self):
        # Define the rate limit for Advanced Trade API endpoints (20 requests per second)
        max_requests_per_second = 20
        interval = 1 / max_requests_per_second

        current_time = time.time()
        elapsed_time = current_time - self.last_request_time

        if elapsed_time < interval:
            # Sleep for the remaining time to comply with the rate limit
            sleep_time = interval - elapsed_time
            await asyncio.sleep(sleep_time)

        # Update the last request time
        self.last_request_time = time.time()

    async def get_currency_balance(self, product_id):
        await self.rate_limit()  # Enforce rate limit for private endpoint

        currency = product_id.split('-')[0]  # Extract the currency from the product ID

        account_ids = [
            'dbbeda8c-124f-5b39-b9fa-3d3abba1c4f8',
            'de612fc5-1292-5a89-acb4-ba4de2d7f230',
            '03112cca-11e5-5256-baba-6289fd75892e',
            'ee6ab972-ba2b-56f2-b32c-ffc9969a1d2b',
            '5b484971-a8cb-59f8-ba4c-bde76d0f9226',
            'd02683f1-0cbd-569b-880c-365957e61208',
            '15d779d9-afe7-528b-bf7e-6cdf895a83c4'
        ]

        for account_id in account_ids:
            accounts = self.client.getAccount(account_id)
            if 'account' in accounts:
                account = accounts['account']
                if 'currency' in account and account['currency'] == currency:
                    name = account['name']
                    balance = float(account['available_balance']['value'])
                    print(f"Account Name: {name}")
                    print(f"Account Balance: {balance}")
                    return f"{balance:.3f}"


        return None, 0.000

    async def calculate_amount_spent(self):
        if self.usdc_balance is not None:
            amount_spent = 0.25 * self.usdc_balance  # 25% of the usdc balance
        return amount_spent

    async def buy_logic(self, buyable_product_id, amount):
        self.price = None
        try:
            self.price = await self.get_latest_price(buyable_product_id)
            print("Got latest price:", self.price)

            if self.price:
                order_type = "limit_limit_gtc"
                order_configuration = {
                    order_type: {
                        "base_size": str(amount),
                        "limit_price": str(self.price)
                    }
                }
            else:
                order_type = "market_market_ioc"
                order_configuration = {
                    order_type: {
                        "quote_size": str(amount),
                    }
                }

            client_order_id = coinbase_client.generate_client_order_id()
            side = Side.BUY.name

            response = coinbase_client.createOrder(
                client_order_id=client_order_id,
                product_id=buyable_product_id,
                side=side,
                order_configuration=order_configuration
            )
            print("Order created")

            if 'success' in response and response['success']:
                success_response = response.get('success_response', {})
                order_id = success_response.get('order_id')
                trade_data = {
                    'date': str(datetime.now().date()),
                    'time': str(datetime.now().time()),
                    'product_id': buyable_product_id,
                    'side': side,
                    'base_size': str(amount),
                    'price': str(self.price),
                    'order_type': order_type,
                    'order_id': order_id
                }

                # Add trade data to history
                self.add_trade_to_history(list(trade_data.values()))

                print(response)
            else:
                self.handle_failed_order(response)

        except Exception as e:
            print("Failed to place buy order:", str(e))

    async def convert_to_usdc(self, amount, product_id):
        self.price = None
        if product_id == 'usdc':
            return amount

        try:
            self.price = await self.get_latest_price(product_id)
            print("Got latest price:", self.price)

            if self.price:
                order_type = "limit_limit_gtc"
                order_configuration = {
                    order_type: {
                        "base_size": str(amount),
                        "limit_price": str(self.price)
                    }
                }
            else:
                order_type = "market_market_ioc"
                order_configuration = {
                    order_type: {
                        "quote_size": str(amount),
                    }
                }

            client_order_id = coinbase_client.generate_client_order_id()
            side = Side.SELL.name

            response = coinbase_client.createOrder(
                client_order_id=client_order_id,
                product_id=product_id,
                side=side,
                order_configuration=order_configuration
            )
            print("Order created")

            if 'success' in response and response['success']:
                success_response = response.get('success_response', {})
                order_id = success_response.get('order_id')
                trade_data = {
                    'date': str(datetime.now().date()),
                    'time': str(datetime.now().time()),
                    'product_id': self.sellable_product_id,
                    'side': side,
                    'base_size': str(amount),
                    'price': str(self.price),
                    'order_type': order_type,
                    'order_id': order_id
                }

                # Add trade data to history
                self.add_trade_to_history(list(trade_data.values()))

                print(response)
            else:
                self.handle_failed_order(response)

        except Exception as e:
            print("Failed to place sell order:", str(e))

    async def execute_buy(self, buyable_product_id, amount):
        await self.rate_limit()  # Enforce rate limit for private endpoint
        # Access the updated product IDs
        self.buyable_product_id = buyable_product_id

        print("Executing buy order...")
        await self.buy_logic(buyable_product_id, amount)

        # Reset the buyable_product_id to None if the buy operation was successful
        if self.order_id:
            self.buyable_product_id = None
            self.order_id = None

    async def execute_sell(self, sellable_product_id):
        await self.rate_limit()  # Enforce rate limit for private endpoint

        self.sellable_product_id = sellable_product_id


        # Convert the product to usdc
        sell_amount = await self.get_currency_balance(sellable_product_id)

        if self.sellable_product_id is not None:
            # Perform the sell operation using the new instance
            await self.convert_to_usdc(sell_amount, sellable_product_id)

        # Check if credentials are found
        if self.order_id:
            self.sellable_product_id = None
            self.order_id = None
            print("Order placed successfully!")