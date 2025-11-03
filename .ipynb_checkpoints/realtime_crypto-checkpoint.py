import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go
from plotly.subplots import make_subplots # NEW: Required for plotting multiple traces on separate rows
import pandas as pd
import numpy as np
import datetime
import ccxt 

# Configuration 
TICKER = 'XRP/USDT'
INTERVAL_SECONDS = 5    # How often the chart attempts to update 
N_CANDLES_DISPLAY = 60  # Number of 1-minute candles to show
TIME_DELTA = datetime.timedelta(minutes=1) 

# Connect to Binance
try:
    # Use 'binanceusdm' for USD-M Futures, 'binance' for Spot
    exchange = ccxt.binance()
except Exception as e:
    print(f"Failed to initialize CCXT exchange: {e}")
    exchange = None

# Define the Real-Time Data Fetch Function (CCXT)
def get_live_data_ccxt(ticker=TICKER, timeframe='1m', limit=N_CANDLES_DISPLAY):
    """
    Fetches real-time OHLCV data from Binance via CCXT, then simulates the
    next live candle for continuous movement.
    """
    if exchange is None:
        return pd.DataFrame()
        
    try:
        symbol = ticker
        
        # Fetch OHLCV data
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
        
        # Convert timestamp (milliseconds) to datetime objects and set as index
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        # Inject Mock Live Candle Data Logic 
        # This simulates a constantly developing candle until the next minute starts
        
        last_close = df['Close'].iloc[-1]
        new_time = df.index[-1] + TIME_DELTA 
        
        mock_data = {
            'Open': last_close * (1 + np.random.uniform(-0.0005, 0.0005)), 
            'High': last_close * (1 + np.random.uniform(0, 0.001)),
            'Low': last_close * (1 + np.random.uniform(-0.001, 0)),
            'Close': last_close * (1 + np.random.uniform(-0.0005, 0.0005)),
            'Volume': np.random.randint(1000, 5000)
        }
        
        new_candle = pd.DataFrame(mock_data, index=[new_time])
        df = pd.concat([df, new_candle])
        
        return df.iloc[-limit:]

    except Exception as e:
        # In a real application, you might use logging here
        print(f"CCXT Error fetching live data: {e}") 
        return pd.DataFrame()


# 3. Define the Dash App Layout
app = dash.Dash(__name__) 

app.layout = html.Div(children=[
    html.H1(f'Real-Time Candlestick Chart: {TICKER} (1-Minute Interval)', style={'textAlign': 'center', 'color': '#f0f0f0', 'paddingTop': '20px'}),
    
    dcc.Graph(id='live-candlestick-graph'),
    
    # Interval component to trigger updates every 5 seconds
    dcc.Interval(
        id='interval-component',
        interval=INTERVAL_SECONDS * 1000, 
        n_intervals=0
    )
], style={'backgroundColor': '#1e1e1e'}) # Dark background for the whole app

# 4. Define the Callback (The Real-Time Engine)
@app.callback(Output('live-candlestick-graph', 'figure'),
              [Input('interval-component', 'n_intervals')])
def update_graph_live(n):
    
    # Calling the new CCXT function 
    df = get_live_data_ccxt(TICKER) 
    
    if df.empty:
        # Return a blank figure if data fetching fails
        return {
            'layout': go.Layout(
                xaxis={'visible': False}, 
                yaxis={'visible': False},
                plot_bgcolor='#1e1e1e',
                paper_bgcolor='#1e1e1e',
                annotations=[{
                    'text': "Data fetch failed. Check network or CCXT configuration.",
                    'xref': "paper", 'yref': "paper", 
                    'showarrow': False, 'font': {'size': 20, 'color': '#ff6347'}
                }]
            )
        }

    # --- START FIGURE CREATION WITH VOLUME SUBPLOT ---

    # Initialize a figure with subplots (2 rows, 1 column)
    # Row 1 (Price) gets 80% height, Row 2 (Volume) gets 20%
    fig = make_subplots(
        rows=2, cols=1, 
        shared_xaxes=True, # Critical: Scrolling/Zooming on one affects the other
        vertical_spacing=0.05, 
        row_width=[0.2, 0.8] # [Volume row height, Candlestick row height]
    )

    # 1. Add Candlestick trace (Price Chart) to Row 1
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        name='Price', # Changed name for simpler legend
        increasing_fillcolor='limegreen',
        decreasing_fillcolor='tomato',
        increasing_line_color='green',
        decreasing_line_color='red',
        whiskerwidth=0.05
    ), row=1, col=1) # <-- Specify Row 1

    # 2. Add Volume trace (Bar Chart) to Row 2
    # Determine colors for volume bars based on price change
    colors = ['limegreen' if c > o else 'tomato' for c, o in zip(df['Close'], df['Open'])]
    fig.add_trace(go.Bar(
        x=df.index, 
        y=df['Volume'], 
        marker_color=colors, # Color bars by price change
        name='Volume'
    ), row=2, col=1) # <-- Specify Row 2
        
    # Update layout and axes for a professional display
    
    # Increase height to accommodate the volume subplot
    fig.update_layout(
        template='plotly_dark',
        margin=dict(l=20, r=20, t=40, b=20),
        height=700, # Increased height from 500 to 700
        xaxis_rangeslider_visible=False, # Hide the default slider in the main chart area
        title_text=f'Real-Time Candlestick Chart: {TICKER} (1-Minute Interval)',
        showlegend=False
    )

    # Price Chart (Row 1) Axes Configuration
    fig.update_yaxes(title_text='Price (USDT)', row=1, col=1)
    
    # Hide the X-axis labels/ticks on the Candlestick chart (Row 1)
    fig.update_xaxes(
        showticklabels=False, 
        rangeslider_visible=False,
        range=[df.index[0], df.index[-1]], # Fix the x-axis to always show the last N_CANDLES
        row=1, col=1
    )

    # Volume Chart (Row 2) Axes Configuration
    fig.update_yaxes(title_text='Volume', row=2, col=1)
    
    # Show X-axis labels/ticks on the Volume chart (Row 2)
    fig.update_xaxes(
        range=[df.index[0], df.index[-1]], # Fix the x-axis to always show the last N_CANDLES
        row=2, col=1
    )

    return fig

# Run the App
if __name__ == '__main__':
    # Setting host='0.0.0.0' for environment compatibility
    app.run(host='127.0.0.1', debug=True)
