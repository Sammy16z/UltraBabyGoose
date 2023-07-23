# MainFrame.py file

# Standard libraries
from enum import Enum
from datetime import datetime
import uuid
import http.client
import json
import socket
from coinbase_advanced_trader.cb_auth import CBAuth
from coinbase_advanced_trader import coinbase_client
from coinbase_advanced_trader.coinbase_client import Side
from coinbase.wallet.client import Client


from datetime import timedelta
import time
import logging
import coloredlogs
import asyncio
import signal

# Third-party libraries
import ccxt
import talib
import requests
import numpy as np
import pandas

import telegram
from telegram import Bot, Update
from telegram.ext import Updater, CommandHandler, MessageHandler

from collections.abc import MutableMapping

import socket
import CoinbaseAPI
from WebRunner import websocket_data, websocket_data_queue

from CoinbaseExchange import CoinbaseExchange
from PeakSpam import PeakSpam


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Set your API key and secret
API_KEY = CoinbaseAPI.API_KEY
API_SECRET = CoinbaseAPI.API_SECRET
coinbase_client.set_credentials(API_KEY, API_SECRET)
cb_auth = CBAuth(API_KEY, API_SECRET)

# Start of Code

class MainFrame:
    def __init__(self):
        self.client = coinbase_client
        self.wallet = Client(CoinbaseAPI.API_KEY, CoinbaseAPI.API_SECRET)
        self.exchange = CoinbaseExchange(CoinbaseAPI.API_KEY, CoinbaseAPI.API_SECRET)
        self.api_key = CoinbaseAPI.API_KEY
        self.api_secret = CoinbaseAPI.API_SECRET
        self.product_ids = CoinbaseAPI.PRODUCT_IDS
        self.bot_token = CoinbaseAPI.BOT_TOKEN
        self.chat_id = CoinbaseAPI.CHAT_ID

        self.portfolio_balance = None

        self.trade_bot = PeakSpam('PeakSpamBot')
    

    async def send_notification(self, message):
        logging.info("Sending Notification...")

        bot = telegram.Bot(token=self.bot_token)
        await bot.send_message(chat_id=self.chat_id, text=message)

    
    async def get_portfolio_balance(self):
        account_ids = [
            '232eaaa0-2d70-5357-9848-53c1db4befcd',
            'dbbeda8c-124f-5b39-b9fa-3d3abba1c4f8',
            'de612fc5-1292-5a89-acb4-ba4de2d7f230',
            '03112cca-11e5-5256-baba-6289fd75892e',
            'ee6ab972-ba2b-56f2-b32c-ffc9969a1d2b',
            '5b484971-a8cb-59f8-ba4c-bde76d0f9226',
            'd02683f1-0cbd-569b-880c-365957e61208',
            '15d779d9-afe7-528b-bf7e-6cdf895a83c4'
        ]

        wallet_data = []

        for account_id in account_ids:
            accounts = coinbase_client.getAccount(account_id)
            account = accounts['account']
            wallet_name = account['name']
            wallet_balance = account['available_balance']['value']
            wallet_data.append(f"{wallet_name} balance: {wallet_balance}")

        # Send balance via Telegram bot as a single message
        await self.send_notification("\n\n".join(wallet_data))


    # Terminate all bots by typing CTRL + C or /Terminate in Telegram
    async def killSwitch(self):
        # Configure the logger
        logger = logging.getLogger()
        coloredlogs.install(level='INFO', logger=logger, fmt='%(asctime)s - %(levelname)s - %(message)s', level_styles={'info': {'color': 'red'}})

        # Define a signal handler for CTRL+C
        def signal_handler(signal, frame):
            logger.info("All Bots Have Been Terminated")
            asyncio.run(self.send_notification("All Bots Have Been Terminated"))
            asyncio.run(self.get_portfolio_balance())  # Call the get_portfolio_balance() method
            raise SystemExit(0)  # Raise SystemExit to exit the program gracefully

        # Set the signal handler for SIGINT (CTRL+C)
        signal.signal(signal.SIGINT, signal_handler)

        # Set the signal handler for SIGTERM (COMMAND+C for Mac)
        signal.signal(signal.SIGTERM, signal_handler)

        # Define the command handler for the termination command from Telegram

    

    async def executeBot(self):
        # Change the logging level to INFO or lower
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.exchange.colored_log('green', "Starting Strategies...")

        # Update the usdc_balance before executing the trades
        await self.exchange.update_usdc_balance()
        amount = await self.exchange.calculate_amount_spent()

        # Check if there are sufficient funds
        if self.exchange.check_insufficient_funds(amount):
            running = True
        else:
            running = False
            self.exchange.colored_log('red', "Insufficient funds. Cannot execute trades.")

        await asyncio.sleep(1)  # Add a delay of 1 second to give WebRunner.py time to update websocket_data

        while running:
            # Retrieve data from the queue if available (timeout to prevent blocking)
            parsed_data = websocket_data_queue.get(timeout=1)

            # Extract the necessary information from parsed_data
            for event in parsed_data['events']:
                product_id = event['tickers'][0]['product_id']
                latest_price = float(event['tickers'][0]['price'])
                self.trade_bot.price_data[product_id].append(latest_price)

                # Calculate the ZigZag indicator and update zigzag_data for the specific product_id
                zigzag = self.trade_bot.calculate_zigzag(self.trade_bot.price_data[product_id])
                self.trade_bot.zigzag_data[product_id] = zigzag

                # Log the latest_prices for each product_id
                logging.info(f"Latest Price for {product_id}: {latest_price}")

                # Execute the PeakSpam bot for the current product_id and amount
                await self.trade_bot.execute(product_id, amount)

            # This should be at the bottom of execution

            # Test if transaction was successful
            if self.exchange.order_id is not None and self.exchange.side == 'BUY':
                order = self.client.getOrder(self.exchange.order_id)
                if order['status'] == 'filled':
                    self.exchange.order_id = None
                    self.exchange.side = None
                    await self.send_notification(f"Buy order executed:\nProduct ID: {product_id}\nAmount Spent: {amount}\nPrice: {self.exchange.price}")

            if self.exchange.order_id is not None and self.exchange.side == 'SELL':
                order = self.client.getOrder(self.exchange.order_id)
                if order['status'] == 'filled':
                    self.exchange.order_id = None
                    self.exchange.side = None
                    await self.send_notification(f"Sell order executed:\nProduct ID: {product_id}\nAmount Spent: {amount}\nPrice: {self.exchange.price}")

            time.sleep(5)



# Create an instance of the MainFrame class
bot = MainFrame()

if __name__ == '__main__':
    logging.info("Running Files...")

    # Run the executeBot function in the main thread
    asyncio.run(bot.executeBot())
