from flask import Flask, request, render_template, redirect, url_for
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
import requests
import sqlite3  # NEW: Library for database
from datetime import datetime  # NEW: To get current time

app = Flask(__name__)

# NEW: Function to initialize the database
def init_db():
    conn = sqlite3.connect('sentiment_history.db')
    c = conn.cursor()
    # Create a table if it doesn't exist
    c.execute('''CREATE TABLE IF NOT EXISTS analyses
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  ticker TEXT,
                  positive INTEGER,
                  neutral INTEGER,
                  negative INTEGER,
                  timestamp DATETIME)''')
    conn.commit()
    conn.close()

# NEW: Function to save an analysis to the database
def save_analysis(ticker, positive, neutral, negative):
    conn = sqlite3.connect('sentiment_history.db')
    c = conn.cursor()
    # Insert the data
    c.execute("INSERT INTO analyses (ticker, positive, neutral, negative, timestamp) VALUES (?, ?, ?, ?, ?)",
              (ticker, positive, neutral, negative, datetime.now()))
    conn.commit()
    conn.close()

# NEW: Function to get all historical analyses from the database
def get_history():
    conn = sqlite3.connect('sentiment_history.db')
    c = conn.cursor()
    c.execute("SELECT * FROM analyses ORDER BY timestamp DESC")  # Get most recent first
    history = c.fetchall()
    conn.close()
    return history

# Initialize the database when the app starts
init_db()

NEWS_API_KEY = '5a71e2ab1f5e4e4f8af67592fa154e40'

def fetch_news(ticker):
    """Fetches real news headlines for a given stock ticker from NewsAPI"""
    # Debug: Check if the key is loaded (this will appear in Railway logs)
    print(f"[DEBUG] Attempting to fetch news for: {ticker}")
    
    url = f"https://newsapi.org/v2/everything?q={ticker}&apiKey={NEWS_API_KEY}&sortBy=publishedAt&language=en"
    try:
        response = requests.get(url)
        data = response.json()
        print(f"[DEBUG] News API Response Status: {data.get('status')}") # Log the status

        # Check if the response is successful and has articles
        if data.get('status') == 'ok' and 'articles' in data:
            headlines = [article['title'] for article in data['articles'][:10]] # Get top 10 headlines
            print(f"[DEBUG] Successfully fetched {len(headlines)} headlines.")
            return headlines
        else:
            # Return a helpful error message that will be shown to the user
            error_message = data.get('message', 'Unknown error from News API.')
            print(f"[ERROR] News API Error: {error_message}")
            return [f"News API Error: {error_message}. Please try manual mode."]

    except Exception as e:
        # This catches any network errors or other unexpected issues
        error_msg = f"A network error occurred: {str(e)}"
        print(f"[ERROR] {error_msg}")
        return [error_msg]
def analyze_sentiment(text):
    # ... [Your existing analyze_sentiment function code remains exactly the same] ...
    text = text.lower()
    for char in '.,?!"\'':
        text = text.replace(char, ' ')

    word_scores = {
        'boom': 2, 'record': 2, 'surge': 2, 'rocket': 2, 'dominant': 2, 'win': 2,
        'up': 1, 'rise': 1, 'high': 1, 'good': 1, 'great': 1, 'buy': 1, 'profit': 1, 'success': 1, 'bull': 1, 'strong': 1, 'gain': 1, 'growth': 1,
        'down': -1, 'fall': -1, 'low': -1, 'bad': -1, 'sell': -1, 'loss': -1, 'fail': -1, 'slump': -1, 'bear': -1, 'weak': -1, 'drop': -1, 'cut': -1,
        'crash': -2, 'crisis': -2, 'fraud': -2, 'plummet': -2, 'collapse': -2, 'bankrupt': -2, 'layoff': -2
    }

    total_score = 0
    for word in text.split():
        if word in word_scores:
            total_score += word_scores[word]
        else:
            for known_word, score in word_scores.items():
                if len(word) > 3 and known_word in word:
                    total_score += score
                    break

    if total_score > 1:
        return "Positive"
    elif total_score < -1:
        return "Negative"
    else:
        return "Neutral"

@app.route('/', methods=['GET', 'POST'])
def index():
    chart_url = None
    summary = None
    headlines_used = []

    if request.method == 'POST':
        ticker = request.form['ticker']
        use_live_news = request.form.get('use_live_news') == 'on'

        if use_live_news:
            headlines = fetch_news(ticker)
        else:
            raw_headlines = request.form['headlines']
            headlines = [h.strip() for h in raw_headlines.split('\n') if h.strip()]

        headlines_used = headlines

        positive_count = 0
        negative_count = 0
        neutral_count = 0
        results = []

        for headline in headlines:
            sentiment = analyze_sentiment(headline)
            results.append((headline, sentiment))
            
            if sentiment == "Positive":
                positive_count += 1
            elif sentiment == "Negative":
                negative_count += 1
            else:
                neutral_count += 1

        # NEW: SAVE THE ANALYSIS TO THE DATABASE!
        save_analysis(ticker, positive_count, neutral_count, negative_count)

        # Create the chart
        labels = ['Positive', 'Neutral', 'Negative']
        counts = [positive_count, neutral_count, negative_count]
        colors = ['green', 'gray', 'red']

        plt.figure(figsize=(8, 5))
        plt.bar(labels, counts, color=colors)
        plt.title(f'Sentiment Analysis for {ticker}')
        plt.ylabel('Number of Headlines')
        
        for i, count in enumerate(counts):
            plt.text(i, count + 0.1, str(count), ha='center')

        img = io.BytesIO()
        plt.savefig(img, format='png')
        img.seek(0)
        chart_url = base64.b64encode(img.getvalue()).decode('utf-8')
        plt.close()

        total = positive_count + neutral_count + negative_count
        summary = {
            'ticker': ticker,
            'positive': positive_count,
            'neutral': neutral_count,
            'negative': negative_count,
            'total': total,
            'source': 'Live News' if use_live_news else 'Manual Input'
        }

    return render_template('index.html', chart_url=chart_url, summary=summary, headlines_used=headlines_used)

# NEW: Create a new route for the history page
@app.route('/history')
def history():
    # Get all analyses from the database
    analyses = get_history()
    # Pass the data to a new template
    return render_template('history.html', analyses=analyses)

if __name__ == '__main__':
    app.run(debug=True)