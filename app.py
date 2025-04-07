import os
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import plotly.io as pio
from flask import Flask, render_template, jsonify
from newsapi import NewsApiClient
from dotenv import load_dotenv
from datetime import datetime, timedelta
import logging

# --- Configuration ---
load_dotenv()  # Load environment variables from .env file
app = Flask(__name__)
NEWS_API_KEY = os.getenv('NEWS_API_KEY')

# Configure logging
logging.basicConfig(level=logging.INFO)

# Check if NewsAPI key is loaded
if not NEWS_API_KEY:
    logging.error("NewsAPI key not found. Make sure it's set in the .env file.")
    # You might want to exit or handle this more gracefully depending on requirements
    # For now, we'll allow the app to run but news fetching will fail.

# Initialize NewsAPI client only if the key exists
newsapi = None
if NEWS_API_KEY:
    try:
        newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    except Exception as e:
        logging.error(f"Error initializing NewsAPI client: {e}")


# --- Tickers and Company Info ---
# Using Yahoo Finance tickers. Macrotech Developers Ltd. is LODHA.NS on Yahoo Finance India.
TICKERS = ['TSLA', 'GOOGL', 'LODHA.NS']
COMPANY_NAMES = {
    'TSLA': 'Tesla',
    'GOOGL': 'Google OR Alphabet', # Use OR for broader search
    'LODHA.NS': 'Macrotech Developers OR Lodha'
}
STOCK_FETCH_PERIOD = "1mo" # Fetch last 1 month of data for graph
STOCK_FETCH_INTERVAL = "1d" # Daily interval
NEWS_FETCH_DAYS = 7 # Fetch news from the last 7 days
NEWS_PAGE_SIZE = 5 # Max number of news articles per company


# --- Helper Functions ---

def get_stock_data(ticker):
    """Fetches historical stock data and current price info."""
    try:
        stock = yf.Ticker(ticker)
        # Fetch historical data for the graph
        hist_data = stock.history(period=STOCK_FETCH_PERIOD, interval=STOCK_FETCH_INTERVAL)
        # Get current market data (more fields available in 'info')
        info = stock.info
        current_price = info.get('currentPrice', info.get('regularMarketPrice')) # Try different fields
        prev_close = info.get('previousClose')
        change = None
        change_percent = None
        if current_price and prev_close:
            change = current_price - prev_close
            change_percent = (change / prev_close) * 100

        data = {
            'history': hist_data,
            'current_price': current_price,
            'change': change,
            'change_percent': change_percent,
            'currency': info.get('currency', 'USD'), # Default to USD if not found
             'name': info.get('shortName', ticker) # Get company name
        }
        logging.info(f"Successfully fetched stock data for {ticker}")
        return data
    except Exception as e:
        logging.error(f"Error fetching stock data for {ticker}: {e}")
        return None

def create_stock_graph(df, ticker, company_name):
    """Creates an interactive Plotly graph from stock data."""
    if df is None or df.empty:
        logging.warning(f"No data provided to create graph for {ticker}")
        return "<p>Could not load graph data.</p>"
    try:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df.index, y=df['Close'], mode='lines', name='Close Price'))
        fig.update_layout(
            title=f'{company_name} ({ticker}) Stock Price ({STOCK_FETCH_PERIOD})',
            xaxis_title='Date',
            yaxis_title='Price',
            margin=dict(l=40, r=20, t=40, b=20), # Adjust margins
            height=300 # Adjust height
        )
        # Convert graph to HTML div
        graph_html = pio.to_html(fig, full_html=False, include_plotlyjs='cdn')
        logging.info(f"Successfully created graph for {ticker}")
        return graph_html
    except Exception as e:
        logging.error(f"Error creating graph for {ticker}: {e}")
        return f"<p>Error generating graph for {ticker}.</p>"


def get_company_news(query):
    """Fetches recent news articles for a given query."""
    if not newsapi:
        logging.warning("NewsAPI client not initialized. Skipping news fetch.")
        return [] # Return empty list if NewsAPI is not configured

    try:
        # Calculate 'from' date for news search
        from_date = (datetime.now() - timedelta(days=NEWS_FETCH_DAYS)).strftime('%Y-%m-%d')

        all_articles = newsapi.get_everything(
            q=query,
            language='en',
            sort_by='publishedAt', # Use publishedAt for recency
            page_size=NEWS_PAGE_SIZE,
            from_param=from_date # Fetch news from the specified date onwards
        )
        logging.info(f"Fetched {len(all_articles.get('articles', []))} news articles for query: '{query}'")
        return all_articles.get('articles', []) # Return the list of articles
    except Exception as e:
        # Catch potential NewsAPI exceptions (e.g., rate limits, key errors)
        logging.error(f"Error fetching news for query '{query}': {e}")
        return [] # Return empty list on error

# --- Flask Route ---

@app.route('/')
def index():
    """Main route to display the dashboard."""
    all_data = {}
    for ticker in TICKERS:
        logging.info(f"--- Processing ticker: {ticker} ---")
        stock_info = get_stock_data(ticker)
        graph_html = "Graph data unavailable."
        news_articles = []
        company_name = COMPANY_NAMES.get(ticker, ticker) # Use mapped name or ticker itself

        if stock_info:
            # Use company name from stock info if available, otherwise use mapped name
            display_name = stock_info.get('name', company_name)
            graph_html = create_stock_graph(stock_info['history'], ticker, display_name)
            # Fetch news using the more specific company name from COMPANY_NAMES
            news_articles = get_company_news(COMPANY_NAMES.get(ticker, ticker))
            all_data[ticker] = {
                'stock': stock_info,
                'graph': graph_html,
                'news': news_articles,
                'display_name': display_name # Pass name to template
            }
        else:
            # Handle case where stock data fetching failed
             all_data[ticker] = {
                'stock': {'current_price': 'N/A', 'change': 'N/A', 'change_percent': 'N/A', 'currency': ''},
                'graph': '<p>Could not load stock data.</p>',
                'news': get_company_news(COMPANY_NAMES.get(ticker, ticker)), # Still try to get news
                'display_name': company_name # Use default name
            }
        logging.info(f"--- Finished processing ticker: {ticker} ---")


    return render_template('index.html', all_data=all_data, tickers=TICKERS)

# --- Run the App ---
if __name__ == '__main__':
    # Use host='0.0.0.0' to make it accessible on your network
    # debug=True is helpful during development but should be False in production
    app.run(debug=True, host='0.0.0.0')