# app_pro.py - SENTIMENT ANALYZER DASHBOARD (WITH AUTHENTICATION)
from flask import Flask, request, render_template, redirect, url_for, session, flash
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
import requests
import sqlite3
from datetime import datetime
import os
from werkzeug.security import generate_password_hash, check_password_hash
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this to a random secret key!

# Initialize sentiment analyzer
analyzer = SentimentIntensityAnalyzer()

# --- Configuration ---
NEWS_API_KEY = '5a71e2ab1f5e4e4f8af67592fa154e40'
FINNHUB_API_KEY = 'cnq0jq1r01qo9lj6n2mgcnq0jq1r01qo9lj6n2n0'

# --- Database Setup ---
def init_db():
    """Initialize databases for users and analyses"""
    conn = sqlite3.connect('sentiment_dashboard.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE,
                  password_hash TEXT,
                  created_at DATETIME)''')
    
    # Analyses table (now with user_id foreign key)
    c.execute('''CREATE TABLE IF NOT EXISTS analyses
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  ticker TEXT,
                  positive INTEGER,
                  neutral INTEGER,
                  negative INTEGER,
                  timestamp DATETIME,
                  FOREIGN KEY (user_id) REFERENCES users (id))''')
    
    conn.commit()
    conn.close()

# --- Authentication Functions ---
def register_user(username, password):
    """Register a new user"""
    conn = sqlite3.connect('sentiment_dashboard.db')
    c = conn.cursor()
    try:
        password_hash = generate_password_hash(password)
        c.execute("INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                 (username, password_hash, datetime.now()))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Username already exists
    finally:
        conn.close()

def verify_user(username, password):
    """Verify user credentials"""
    conn = sqlite3.connect('sentiment_dashboard.db')
    c = conn.cursor()
    c.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,))
    user = c.fetchone()
    conn.close()
    
    if user and check_password_hash(user[1], password):
        return user[0]  # Return user_id
    return None

# --- API Functions (Same as before) ---
def fetch_news(ticker):
    """Fetches real news headlines"""
    # ... [Keep the same fetch_news function from previous code] ...
    print(f"[LOG] Fetching news for: {ticker}")
    url = f"https://newsapi.org/v2/everything?q={ticker}&apiKey={NEWS_API_KEY}&sortBy=publishedAt&language=en"
    
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get('status') == 'ok' and data.get('articles'):
            headlines = [article['title'] for article in data['articles'][:7]]
            print(f"[LOG] Success! Found {len(headlines)} headlines.")
            return headlines
        else:
            error_msg = data.get('message', 'Unknown API error. Please try manual mode.')
            print(f"[ERROR] News API: {error_msg}")
            return [error_msg]

    except Exception as e:
        error_msg = f"Network error: {str(e)}. Please try again later."
        print(f"[ERROR] {error_msg}")
        return [error_msg]

def get_stock_price(ticker):
    """Gets the live stock price"""
    # ... [Keep the same get_stock_price function] ...
    print(f"[LOG] Fetching price for: {ticker}")
    url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_API_KEY}"
    
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        current_price = data.get('c', 'N/A')
        print(f"[LOG] {ticker} Price: ${current_price}")
        return current_price
    except Exception as e:
        print(f"[ERROR] Could not fetch price: {e}")
        return "N/A"

def analyze_sentiment_vader(text):
    """Uses VADER for advanced sentiment analysis"""
    # ... [Keep the same analyze_sentiment_vader function] ...
    sentiment_dict = analyzer.polarity_scores(text)
    compound_score = sentiment_dict['compound']
    
    if compound_score >= 0.05:
        return "Positive", compound_score
    elif compound_score <= -0.05:
        return "Negative", compound_score
    else:
        return "Neutral", compound_score

def save_analysis(user_id, ticker, positive, neutral, negative):
    """Save analysis to database for specific user"""
    conn = sqlite3.connect('sentiment_dashboard.db')
    c = conn.cursor()
    c.execute("INSERT INTO analyses (user_id, ticker, positive, neutral, negative, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
              (user_id, ticker, positive, neutral, negative, datetime.now()))
    conn.commit()
    conn.close()

def get_user_history(user_id):
    """Get analysis history for specific user"""
    conn = sqlite3.connect('sentiment_dashboard.db')
    c = conn.cursor()
    c.execute("SELECT * FROM analyses WHERE user_id = ? ORDER BY timestamp DESC", (user_id,))
    history = c.fetchall()
    conn.close()
    return history

# Initialize database
init_db()

# --- Authentication Routes ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user_id = verify_user(username, password)
        if user_id:
            session['user_id'] = user_id
            session['username'] = username
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if register_user(username, password):
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Username already exists', 'error')
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

# --- Dashboard Routes ---
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    chart_url = None
    summary = None
    headlines_used = []
    current_price = "N/A"

    if request.method == 'POST':
        ticker = request.form['ticker'].upper().strip()
        use_live_news = request.form.get('use_live_news') == 'on'

        current_price = get_stock_price(ticker)
        
        if use_live_news:
            headlines = fetch_news(ticker)
        else:
            raw_headlines = request.form['headlines']
            headlines = [h.strip() for h in raw_headlines.split('\n') if h.strip()]
        
        headlines_used = headlines

        positive_count = 0
        negative_count = 0
        neutral_count = 0

        for headline in headlines:
            sentiment, score = analyze_sentiment_vader(headline)
            if sentiment == "Positive":
                positive_count += 1
            elif sentiment == "Negative":
                negative_count += 1
            else:
                neutral_count += 1

        if headlines and not headlines[0].startswith("Error"):
            save_analysis(session['user_id'], ticker, positive_count, neutral_count, negative_count)

        if positive_count + neutral_count + negative_count > 0:
            labels = ['Positive', 'Neutral', 'Negative']
            counts = [positive_count, neutral_count, negative_count]
            colors = ['#2E8B57', '#696969', '#DC143C']

            plt.figure(figsize=(10, 6))
            bars = plt.bar(labels, counts, color=colors, alpha=0.8)
            plt.title(f'Sentiment Analysis for {ticker} (Live: ${current_price})', fontsize=14, fontweight='bold')
            plt.ylabel('Number of Headlines', fontweight='bold')
            
            for i, bar in enumerate(bars):
                height = bar.get_height()
                plt.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                        f'{counts[i]}', ha='center', va='bottom', fontweight='bold')
            
            plt.tight_layout()
            
            img = io.BytesIO()
            plt.savefig(img, format='png', dpi=100, bbox_inches='tight')
            img.seek(0)
            chart_url = base64.b64encode(img.getvalue()).decode('utf-8')
            plt.close()

        total = positive_count + neutral_count + negative_count
        if total > 0:
            summary = {
                'ticker': ticker,
                'positive': positive_count,
                'neutral': neutral_count,
                'negative': negative_count,
                'total': total,
                'source': 'Live News' if use_live_news else 'Manual Input',
                'price': current_price
            }

    return render_template('dashboard.html', 
                         chart_url=chart_url, 
                         summary=summary, 
                         headlines_used=headlines_used,
                         username=session.get('username'))

@app.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    analyses = get_user_history(session['user_id'])
    return render_template('history.html', analyses=analyses)

@app.route('/trends', methods=['GET', 'POST'])
def trend_analysis():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # ... [Keep the same trend_analysis function] ...
    trend_chart_url = None
    ticker = ""
    trend_data = []

    if request.method == 'POST':
        ticker = request.form['ticker'].upper().strip()
        
        conn = sqlite3.connect('sentiment_dashboard.db')
        c = conn.cursor()
        c.execute("SELECT timestamp, positive, neutral, negative FROM analyses WHERE user_id = ? AND ticker = ? ORDER BY timestamp", 
                 (session['user_id'], ticker))
        data = c.fetchall()
        conn.close()

        if data:
            dates = []
            sentiment_scores = []
            
            for record in data:
                timestamp, positive, neutral, negative = record
                total = positive + neutral + negative
                if total > 0:
                    sentiment_score = ((positive - negative) / total) * 100
                    dates.append(datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S.%f'))
                    sentiment_scores.append(sentiment_score)
            
            if dates and sentiment_scores:
                plt.figure(figsize=(12, 6))
                plt.plot(dates, sentiment_scores, marker='o', linestyle='-', color='#2E8B57', linewidth=2, markersize=6)
                plt.title(f'Sentiment Trend for {ticker}', fontsize=16, fontweight='bold')
                plt.ylabel('Sentiment Score (%)', fontweight='bold')
                plt.xlabel('Date', fontweight='bold')
                plt.grid(True, alpha=0.3)
                plt.axhline(y=0, color='red', linestyle='--', alpha=0.5)
                plt.xticks(rotation=45)
                plt.tight_layout()
                
                img = io.BytesIO()
                plt.savefig(img, format='png', dpi=100)
                img.seek(0)
                trend_chart_url = base64.b64encode(img.getvalue()).decode('utf-8')
                plt.close()
                
                trend_data = list(zip(dates, sentiment_scores))
            else:
                trend_data = ["not_enough"]
        else:
            trend_data = ["no_data"]

    return render_template('trends.html', 
                         trend_chart_url=trend_chart_url,
                         ticker=ticker,
                         trend_data=trend_data)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)