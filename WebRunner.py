import websocket
import json
import time
import hashlib
import hmac
import CoinbaseAPI
import threading


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

# Create a global variable to hold the latest market data for each product_id
websocket_data = {}

# Threading lock for printing messages
print_lock = threading.Lock()

def get_websocket_data():
    return websocket_data

def sign_message(message):
    message = hmac.new(SIGNING_KEY.encode('utf-8'), message.encode('utf-8'), digestmod=hashlib.sha256).hexdigest()
    return message

def on_message(ws, message, product_id):
    try:
        parsed_data = json.loads(message)
        websocket_data[product_id] = parsed_data
        with print_lock:
            print()
            print(f"Received message for {product_id}: {websocket_data[product_id]}")
    except Exception as e:
        with print_lock:
            print(f"Error while processing message: {e}")

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
        on_message=lambda ws, message: on_message(ws, message, product_id)
    )

    def on_open(ws):
        print(f"WebSocket connection opened for {product_id}")
        ws.send(subscribe_msg)

    def on_error(ws, error):
        with print_lock:
            print(f"WebSocket error for {product_id}: {error}")

    def on_close(ws, close_status_code, close_msg):
        with print_lock:
            print(f"WebSocket connection closed for {product_id} with status code {close_status_code} and message: {close_msg}")

    ws.on_open = on_open
    ws.on_error = on_error
    ws.on_close = on_close

    ws.run_forever()

if __name__ == '__main__':
    threads = [threading.Thread(target=create_websocket, args=(product_id,)) for product_id in CoinbaseAPI.PRODUCT_IDS]
    for thread in threads:
        thread.start()

    # Keep the main thread running
    while True:
        time.sleep(1)
