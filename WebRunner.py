import websocket
import json
import time
import hashlib
import hmac
import CoinbaseAPI
from threading import Thread
import queue

# Derived from your Coinbase Retail API Key
# SIGNING_KEY: the signing key provided as a part of your API key. Also called the "SECRET KEY"
# API_KEY: the api key provided as a part of your API key. Also called the "PUBLIC KEY"
SIGNING_KEY = CoinbaseAPI.API_SECRET
API_KEY = CoinbaseAPI.API_KEY

if not SIGNING_KEY or not API_KEY:
    raise ValueError('missing mandatory environment variable(s)')

CHANNEL_NAMES = {
    'level2': 'level2',
    'user': 'user',
    'tickers': 'ticker',
    'ticker_batch': 'ticker_batch',
    'status': 'status',
    'market_trades': 'market_trades',
}

# The base URL of the API
WS_API_URL = 'wss://advanced-trade-ws.coinbase.com'

def sign_message(message):
    message = hmac.new(SIGNING_KEY.encode('utf-8'), message.encode('utf-8'), digestmod=hashlib.sha256).hexdigest()
    return message

websocket_data = {}
websocket_data_queue = queue.Queue()


def on_message(ws, message):
    try:
        parsed_data = json.loads(message)
        websocket_data_queue.put(parsed_data)
    except Exception as e:
        print(f"Error processing received message: {e}, Message: {message}")

def create_websocket(product_id):
    channel = 'ticker'
    timestamp = str(int(time.time()))
    subscribe_msg = {
        'type': 'subscribe',
        'product_ids': [
            product_id
        ],
        'channel': 'ticker',
        'api_key': API_KEY,
        'timestamp': timestamp,
        'signature': sign_message(timestamp + channel + product_id)
    }
    subscribe_msg = json.dumps(subscribe_msg)

    ws = websocket.WebSocketApp(
        WS_API_URL,
        on_message=on_message
    )

    def on_open(ws):
        ws.send(subscribe_msg)

    def on_close(ws):
        print('Websocket connection closed')

    ws.on_open = on_open
    ws.on_close = on_close

    ws.run_forever()

# ... (existing code)

# In the if __name__ == '__main__': block, replace the loop with the following:
if __name__ == '__main__':
    for product_id in CoinbaseAPI.PRODUCT_IDS:
        websocket_thread = Thread(target=create_websocket, args=(product_id,))
        websocket_thread.daemon = True
        websocket_thread.start()
        time.sleep(1)
    # Keep the WebSocket threads running
    while True:
        time.sleep(1)