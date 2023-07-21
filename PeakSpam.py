# PeakSpam.py file

import logging
import asyncio
import talib
import numpy as np
import ta.momentum
import ta.volatility
import ta.trend
from enum import Enum
from datetime import datetime
import uuid
import json
from coinbase_advanced_trader.cb_auth import CBAuth
from coinbase_advanced_trader import coinbase_client
from coinbase_advanced_trader.coinbase_client import Side


from collections.abc import MutableMapping

import CoinbaseAPI
from CoinbaseExchange import CoinbaseExchange


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class PeakSpam:
    def __init__(self, name):
        self.name = name
        self.client = coinbase_client
        self.exchange = CoinbaseExchange(CoinbaseAPI.API_KEY, CoinbaseAPI.API_SECRET)
        self.product_ids = CoinbaseAPI.PRODUCT_IDS
        self.bot_token = CoinbaseAPI.BOT_TOKEN
        self.chat_id = CoinbaseAPI.CHAT_ID

        # Initialize necessary variables and parameters
        self.price_data = {product_id: [] for product_id in self.product_ids}
        self.zigzag_data = {product_id: [] for product_id in self.product_ids}
        self.entry_price = {}  # Dictionary to store entry price for each product
        self.position_occupied = {}  # Dictionary to store position occupation status for each product

    async def execute(self, product_id, amount):
        if self.should_buy(product_id):
            self.exchange.colored_log('green', "Calling execute_buy")
            await self.exchange.execute_buy(product_id, amount)
            await self.pass_should_buy(product_id)
                
        if self.should_sell(product_id):
            self.exchange.colored_log('green', "Calling execute_sell")
            await self.exchange.execute_sell(product_id, amount)
            await self.pass_should_sell(product_id)
            await self.exchange.update_usdc_balance




    async def pass_should_buy(self, product_id):
        if self.should_buy(product_id):
            self.position_occupied[product_id] = True
            self.entry_price[product_id] = self.exchange.price

            return True
    

    async def pass_should_sell(self, product_id):
        if product_id in self.position_occupied:
            self.position_occupied[product_id] = False  # Set position_occupied to False for the specific product ID
            if product_id in self.entry_price:
                del self.entry_price[product_id]  # Remove entry_price for the specific product ID being sold

            return True
        

    def should_buy(self, product_id):
        if product_id not in self.product_ids:
            return False

        if product_id not in self.price_data:
            return False

        price_data = self.price_data[product_id]  # Retrieve the price data for the specific product ID

        if len(price_data) < 1:
            # If price_data is empty, return False or handle the condition accordingly
            return False

        zigzag_data = self.zigzag_data[product_id]
        if len(zigzag_data) < 2:
            return False

        sma_value = self.calculate_sma(product_id, period=10)
        if sma_value is None:
            return False

        if sma_value >= 20 and zigzag_data[-1] > zigzag_data[-2]:
            # Rest of the code
            self.exchange.buyable_product_id = product_id  # Set the buyable product ID to the current product ID
            return True

        return False


    def should_sell(self, product_id):
        if product_id not in self.position_occupied:
            return False
        
        zigzag_data = self.zigzag_data.get(product_id, [])
        if len(zigzag_data) < 2:
            return False

        current_direction = zigzag_data[-1].direction
        previous_direction = zigzag_data[-2].direction

        if current_direction == 'down':
            # ZigZag indicator started moving downward
            entry_price = self.entry_price[product_id]  # Retrieve the entry_price from the dictionary
            current_price = self.exchange.get_latest_price(product_id)
            price_change_percentage = (current_price - entry_price) / entry_price * 100

            if price_change_percentage <= -1.5:
                # Apply stop-loss if the trade is down 1.5%
                self.exchange.sellable_product_id = product_id  # Set the sellable product ID to the current product ID
                return True

        if current_direction == 'up':
            # ZigZag indicator started moving upward
            entry_price = self.entry_price[product_id]  # Retrieve the entry_price from the dictionary
            current_price = self.exchange.get_current_price(product_id)
            price_change_percentage = (current_price - entry_price) / entry_price * 100

            if price_change_percentage >= 5.0:
                # Apply take-profit if the trade is up 5.0%
                self.exchange.sellable_product_id = product_id  # Set the sellable product ID to the current product ID
                return True

        return False
    
    def calculate_sma(self, product_id, period=10):
        # Calculate the simple moving average for the given product_id and period
        if product_id not in self.price_data:
            return None

        price_data = self.price_data[product_id]
        if len(price_data) < period:
            return None

        close_prices = np.array(price_data)
        return talib.SMA(close_prices, timeperiod=period)[-1]


    def calculate_zigzag(self, price_data, deviation=0.03, pivot_legs=10):
        # Calculate the ZigZag indicator for the given price_data with the specified deviation and pivot_legs
        if not price_data:
            return None

        close_prices = np.array(price_data)
        pivot_points = []
        pivot_low = pivot_high = close_prices[0]

        for price in close_prices:
            if price > pivot_high:
                pivot_high = price
                pivot_low = price * (1 - deviation)

            elif price < pivot_low:
                pivot_low = price
                pivot_high = price * (1 + deviation)

            else:
                continue

            pivot_points.append((pivot_low, pivot_high))

        zz_indicator = np.zeros(len(close_prices))

        for i, price in enumerate(close_prices):
            for pivot_low, pivot_high in pivot_points:
                if pivot_low <= price <= pivot_high:
                    zz_indicator[i] = price
                    break

        logging.info("ZigZag Data: %s", zz_indicator)
        return zz_indicator