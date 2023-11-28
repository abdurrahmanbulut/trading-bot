from flask import Flask, render_template, request, session, redirect, url_for
from functools import wraps
import time
from flask import jsonify
from flask import Flask
import requests
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from datetime import datetime, timedelta
import talib
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from threading import Thread
from time import sleep
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

is_running = False
trade_history_global = []
coin_amount = 0.0
remaining_balance = 0.0

model = LinearRegression()
scaler = StandardScaler()

app = Flask(__name__)



def fetch_coin_data(coin, interval):
    symbol = coin + 'USDT'
    limit = 1000
    url = f'https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}'
    response = requests.get(url)
    data = response.json()
    df = pd.DataFrame(data, columns=['Open time', 'Open', 'High', 'Low', 'Close', 'Volume', 'Close time', 'Quote asset volume', 'Number of trades', 'Taker buy base asset volume', 'Taker buy quote asset volume', 'Ignore'])
    df = df.iloc[:, :6]
    df.columns = ['Datetime', 'Open', 'High', 'Low', 'Close', 'Volume']
    df['Datetime'] = pd.to_datetime(df['Datetime'], unit='ms')
    df['Close'] = df['Close'].astype(float)
    
    return df

def fetch_current_price(coin):
    symbol = coin + 'USDT'
    url = f'https://api.binance.com/api/v3/ticker/price?symbol={symbol}'
    response = requests.get(url)
    data = response.json()
    return data['price']

def add_indicators(df):
    # Veri temizleme ve özellik mühendisliği
    df['SMA_20'] = df['Close'].rolling(window=20).mean()
 
    df['RSI'] = talib.RSI(df['Close'].values, timeperiod=14)
    df['UpperBand'], df['MiddleBand'], df['LowerBand'] = talib.BBANDS(df['Close'].values, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
   
    df['MACD'], df['MACDSignal'], df['MACDHist'] = talib.MACD(df['Close'].values, fastperiod=12, slowperiod=26, signalperiod=9)
    df.bfill(inplace=True)
    return df

def train_model(coin, interval):
    # Örnek bir coin için model eğitimi
    df = fetch_coin_data(coin, interval)  # Örnek olarak BTC kullanıldı
    df = add_indicators(df)
        
    X = df[['SMA_20', 'RSI', 'UpperBand', 'LowerBand', 'MACD']]
    y = df['Close']
    
    X = scaler.fit_transform(X)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
    model.fit(X_train, y_train)
        
def predict_price(coin, interval, times_to_predict):

    df = fetch_coin_data(coin, interval=interval)
    df = add_indicators(df)

    predictions = []
    for _ in range(times_to_predict):  # Gelecek 10 saat için
        X = df[['SMA_20', 'RSI', 'UpperBand', 'LowerBand', 'MACD']]
        X = scaler.transform(X)
       
        last_hour_data = X[-1].reshape(1, -1)
        next_hour_price = model.predict(last_hour_data)[0]
        predictions.append(next_hour_price)

        # Son tahmini veri setine ekle ve indikatörleri güncelle
        next_row = df.iloc[-1].to_dict()
        next_row['Close'] = next_hour_price
        df = pd.concat([df, pd.DataFrame([next_row])], ignore_index=True)
        df = add_indicators(df)  # Indikatörleri yeniden hesapla

    predicted_value = predictions[0]
    return predictions, predicted_value

def get_data(index, data):
    return data[index]

def interval_to_seconds(interval):
    if interval.endswith('h'):
        return int(interval.rstrip('h')) * 3600
    elif interval.endswith('m'):
        return int(interval.rstrip('m')) * 60
    else:
        return 3600  # Default to 1 hour if format is unrecognized

def trade_loop(coin_name, data_range, balance, amount_percentage):
  
    global coin_amount
    global trade_history_global
    global remaining_balance

    trade_history_global = []
    usable_balance = float(balance)

    while is_running:
        df = fetch_coin_data(coin_name, data_range)
        df = add_indicators(df)
        train_model(coin_name, data_range)
        _, predicted_value = predict_price(coin_name, data_range, 1)  # Predict next interval
        
        current_price = df['Close'].iloc[-1]
        
        if predicted_value > current_price:
            usable_amount = (float(usable_balance) * int(amount_percentage)) / 100
            usable_balance = usable_balance - usable_amount
            print("Buy signal")
            current_coin_amount = usable_amount / current_price
            coin_amount = coin_amount + current_coin_amount
            remaining_balance = usable_balance
            # Impt buy logic here
            trade_history_global.append({'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'action': 'BUY', 'amount': current_coin_amount})
            get_trade_history()

        elif(coin_amount != 0.0):
            print("Sell signal")
            remaining_balance = usable_balance + coin_amount * current_price
            trade_history_global.append({'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'action': 'SELL', 'amount': coin_amount})
            get_trade_history()
            coin_amount = 0
        
        # Wait for the next interval
        sleep(interval_to_seconds(data_range))
    
    return remaining_balance

def calculate_signals(df, predictions):
    # Assuming 'predictions' is a list of predicted prices and df['Close'] contains the current prices
    signals = []
    for i in range(len(predictions)):
        if predictions[i] > df['Close'].iloc[i]:
            signals.append('Buy')
        elif predictions[i] < df['Close'].iloc[i]:
            signals.append('Sell')
        else:
            signals.append('Neutral')
    return signals

@app.route('/get-technical-data', methods=['POST'])
def get_technical_data():
    data = request.json
    coin_name = data.get('coin_name')
    data_range = data.get('data_range')

    # Fetch and process data
    df = fetch_coin_data(coin_name, data_range)
    df = add_indicators(df)  # Assuming add_indicators adds technical indicators to your DataFrame

    # Example: sending back a simple moving average (SMA) as a technical indicator
    technical_data = df['SMA_20'].tail(50).tolist()  # Or use any other technical indicator

    labels = [str(d) for d in df.index[-50:]]  # Last 50 data points

    return jsonify({'labels': labels, 'values': technical_data})

@app.route('/get-trade-history', methods=['POST'])
def get_trade_history():
    global trade_history_global
    return jsonify(trade_history_global)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start-stop', methods=['POST'])
def start_stop_bot():
    global trade_history_global
    global coin_amount

    
    data = request.json
    running = data.get('running')
    coin_name = data.get('coin_name').upper()
    data_range = data.get('data_range')
    balance = data.get('balance')
    amount_percentage = data.get('amount_percentage')

    df = fetch_coin_data(coin_name, data_range)
    df = add_indicators(df)
    train_model(coin_name, data_range)
    predictions, predicted_value = predict_price(coin_name, data_range, 10)

    last_20_values = df.values.tolist()[-20:]
    predictions = last_20_values + predictions
    print(predictions)
    print(last_20_values)

    if running:
        new_balance = start_bot(coin_name, data_range, balance, amount_percentage)
    else:
        new_balance = stop_bot(coin_name, balance)  


    return jsonify({
        'status': 'success',
        'running': running,
        'new_balance': new_balance,
        'predictions': predictions,
        'predicted_value': predicted_value
    })

@app.route('/get-chart-data', methods=['POST'])
def get_chart_data():
    data = request.json
    coin_name = data.get('coin_name').upper()
    data_range = data.get('data_range')
    df = fetch_coin_data(coin_name, data_range)
    df = add_indicators(df)
    train_model(coin_name, data_range)
    predictions, predicted_value = predict_price(coin_name, data_range, 10)
    historical_data = [1,3,4,5,56,6]  # Get historical data
    prediction_data = [4,53,6,3,6,3]  # Get prediction data
    return jsonify({
        'historical_data': historical_data,
        'prediction_data': df.to_dict(orient='records')
    })

def start_bot(coin_name, data_range, balance, amount_percentage):
    global is_running
    is_running = True
    print(f"Bot started for {coin_name} with data range {data_range} and balance {balance}")
    
    new_balance = trade_loop(coin_name, data_range, balance, amount_percentage)
    return new_balance
   
def stop_bot(coin_name, balance):
    global is_running
    global coin_amount
    global remaining_balance
    print("Bot stopped")
    is_running = False
    current_price = fetch_current_price(coin_name)
    
    print(current_price)
    print(coin_amount)
    print(remaining_balance)

    if(coin_amount != 0):
        new_balance = float(current_price) * float(coin_amount) + float(remaining_balance)
        trade_history_global.append({'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'action': 'SELL', 'amount': coin_amount})
        get_trade_history()
    else:
        new_balance = balance

    
    print(new_balance)
    return new_balance

if __name__ == '__main__':
    app.run(debug=True)
