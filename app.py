from flask import Flask, render_template, request, jsonify
import yfinance as yf
import pandas as pd
import alpaca_trade_api as tradeapi
import matplotlib.pyplot as plt
import sqlite3
from transformers import pipeline  # For NLP sentiment analysis
from datetime import datetime, timedelta

app = Flask(__name__)

def get_db_connection():
    db_path = '/Users/benjaminquinngiroud/Library/Mobile Documents/com~apple~CloudDocs/Python.nosync/Stocks.db'
    return sqlite3.connect(db_path)

@app.template_filter('strftime')
def format_datetime(value, format='%d/%m/%Y %H:%M'):
    if value:
        try:
            # Match format '%Y-%m-%dT%H:%M'
            return datetime.strptime(value, "%Y-%m-%dT%H:%M").strftime(format)
        except ValueError:
            # If other formats are needed, handle them here
            return value
    return value


@app.route("/")
def index():
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row  # To get dictionary-like rows
    stock_cursor = conn.execute("SELECT * FROM stocks WHERE symbol = 'T'")
    stock = stock_cursor.fetchone()

    if stock is None:
        conn.close()
        return "<h1>Stock not found</h1>"

    # Fetch the most recent announcement for this stock
    announcement_cursor = conn.execute(
        """
        SELECT title, date_time
        FROM announcements
        WHERE stock_id = ?
        ORDER BY date_time DESC
        LIMIT 1
        """,
        (stock["id"],)
    )
    latest_announcement = announcement_cursor.fetchone()

    # Fetch mean sentiment score
    sentiment_cursor = conn.execute(
        """
        SELECT AVG(sentiment) AS mean_sentiment, 
               SUM(CASE WHEN pertinency = 1 THEN 1 ELSE 0 END) AS positive_count,
               SUM(CASE WHEN pertinency = 2 THEN 1 ELSE 0 END) AS negative_count
        FROM messages
        WHERE stock_id = ?
        """,
        (stock["id"],)
    )
    sentiment_data = sentiment_cursor.fetchone()

    mean_sentiment = round(sentiment_data["mean_sentiment"], 2) if sentiment_data["mean_sentiment"] else 0
    buy_sell = "Buy" if sentiment_data["positive_count"] > sentiment_data["negative_count"] else "Sell"

    conn.close()

    return render_template(
        "index.html",
        stock=dict(stock),
        latest_announcement=dict(latest_announcement) if latest_announcement else None,
        mean_sentiment=mean_sentiment,
        buy_sell=buy_sell
    )

@app.route("/stock-data/<ticker>")
def get_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        historical_data = stock.history(period="1mo", interval="1d")  # Changed from "3wk" to "1mo"

        if historical_data.empty:
            return jsonify({"error": "No data found for the ticker"}), 404

        formatted_data = []
        for date, row in historical_data.iterrows():
            timestamp = int(pd.Timestamp(date).timestamp() * 1000)  # Convert to milliseconds
            formatted_data.append({
                "t": timestamp,  # Use milliseconds timestamp
                "o": float(row["Open"]),
                "h": float(row["High"]),
                "l": float(row["Low"]),
                "c": float(row["Close"])
            })

        return jsonify(formatted_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500





# Alpaca API Setup
ALPACA_API_KEY = "your_alpaca_api_key"
ALPACA_SECRET_KEY = "your_alpaca_secret_key"
BASE_URL = "https://paper-api.alpaca.markets"
alpaca = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, BASE_URL, api_version="v2")


@app.route("/add_stock", methods=["POST"])
def add_stock():
    data = request.json  # Expect JSON payload with `name` and `symbol`
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO stocks (name, symbol) VALUES (?, ?)",
            (data["name"], data["symbol"])
        )
        conn.commit()
        return jsonify({"message": "Stock added successfully!"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route("/update_description/<int:stock_id>", methods=["PUT"])
def update_description(stock_id):
    data = request.json
    description = data.get("description")

    if not description:
        return jsonify({"error": "Description is required"}), 400

    conn = get_db_connection()
    try:
        cursor = conn.execute(
            """
            UPDATE description
            SET description = ?
            WHERE stock_id = ?
            """,
            (description, stock_id),
        )
        conn.commit()

        # Check if the update was successful
        if cursor.rowcount == 0:
            return jsonify({"error": "Stock ID not found or no changes made"}), 404

        return jsonify({"message": "Description updated successfully!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/search", methods=["POST"])
def search_stocks():
    query = request.json.get("query")
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM stocks WHERE name LIKE ?", (f"%{query}%",))
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(results)

@app.route("/stock-info/<ticker>")
def get_stock_info(ticker):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row

    stock_cursor = conn.execute("SELECT * FROM stocks WHERE symbol = ?", (ticker,))
    stock = stock_cursor.fetchone()

    if not stock:
        conn.close()
        return jsonify({"error": "Stock not found"}), 404

    stock_id = stock["id"]

    # Fetch latest announcement for this stock
    announcement_cursor = conn.execute(
        "SELECT title, date_time FROM announcements WHERE stock_id = ? ORDER BY date_time DESC LIMIT 1",
        (stock_id,)
    )
    latest_announcement = announcement_cursor.fetchone()

    # Fetch sentiment analysis (ensure no NULL values)
    sentiment_cursor = conn.execute(
        """
        SELECT 
            COALESCE(AVG(sentiment), 0) AS mean_sentiment,
            COALESCE(SUM(CASE WHEN pertinency = 1 THEN 1 ELSE 0 END), 0) AS positive_count,
            COALESCE(SUM(CASE WHEN pertinency = 2 THEN 1 ELSE 0 END), 0) AS negative_count
        FROM messages 
        WHERE stock_id = ?
        """,
        (stock_id,)
    )
    sentiment_data = sentiment_cursor.fetchone()

    mean_sentiment = round(sentiment_data["mean_sentiment"], 2) if sentiment_data["mean_sentiment"] else 0
    positive_count = sentiment_data["positive_count"]
    negative_count = sentiment_data["negative_count"]

    # Avoid NoneType error
    if positive_count is None:
        positive_count = 0
    if negative_count is None:
        negative_count = 0

    buy_sell = "Buy" if positive_count > negative_count else "Sell"

    conn.close()

    return jsonify({
        "id": stock_id,
        "name": stock["name"],
        "latest_announcement": dict(latest_announcement) if latest_announcement else None,
        "mean_sentiment": mean_sentiment,
        "buy_sell": buy_sell
    })



@app.route("/announcements", methods=["GET"])
def get_announcements():
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("""
        SELECT a.title, a.date_time
        FROM announcements a
        JOIN stocks s ON a.stock_id = s.id
        WHERE s.symbol = 'T'  # Replace 'T' with the current stock's symbol dynamically
    """)
    announcements = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(announcements)


@app.route("/add_announcement", methods=["POST"])
def add_announcement():
    data = request.json
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO announcements (stock_id, title, date_time) VALUES (?, ?, ?)",
        (data["stock_id"], data["title"], data["date_time"])
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Announcement added successfully!"})


# Load FinBERT financial sentiment analysis model
sentiment_analyzer = pipeline("sentiment-analysis", model="ProsusAI/finbert")

@app.route("/add_message", methods=["POST"])
def add_message():
    data = request.json  # Get JSON data from request

    print("Received Data:", data)  # Debugging

    try:
        stock_id = data.get("stock_id")
        title = data.get("title")
        content = data.get("content")
        source = data.get("source")
        start_price = float(data.get("start_price"))
        end_price = float(data.get("end_price"))
        date_time = data.get("date_time")

        if not all([stock_id, title, content, source, start_price, end_price, date_time]):
            return jsonify({"error": "Missing required fields"}), 400

        # **Advanced Pertinency Analysis with Weighting**
        positive_keywords = {
            "growth": 3, "profit": 3, "increase": 2, "rise": 2, "gain": 2,
            "revenue": 2, "strong": 3, "surge": 4, "outperform": 4,
            "upgrade": 2, "bullish": 3, "record-high": 3, "forecast": 3
        }
        negative_keywords = {
            "decline": 3, "loss": 3, "drop": 2, "fall": 2, "decrease": 2,
            "underperform": 4, "weak": 3, "plunge": 4, "downgrade": 3,
            "bearish": 3, "recession": 4, "sell-off": 4, "warning": 4
        }

        pertinency_score = 0

        # Assign weights based on detected financial terms
        for word, weight in positive_keywords.items():
            if word in content.lower():
                pertinency_score += weight

        for word, weight in negative_keywords.items():
            if word in content.lower():
                pertinency_score -= weight

        # **Run NLP Sentiment Analysis (FinBERT)**
        sentiment_result = sentiment_analyzer(content)[0]
        sentiment_label = sentiment_result["label"]
        sentiment_score = sentiment_result["score"]

        # Adjust pertinency using NLP Sentiment Score
        if sentiment_label == "positive":
            pertinency_score += sentiment_score * 5  # High-confidence positive news
        elif sentiment_label == "negative":
            pertinency_score -= sentiment_score * 5  # High-confidence negative news

        # **Fine-Tune Pertinency Score**
        if pertinency_score >= 5:
            pertinency = 1  # Positive
        elif pertinency_score <= -5:
            pertinency = 2  # Negative
        else:
            pertinency = 0  # Neutral/Mixed

        # **Adjust Sentiment Based on Market Volatility**
        volatility = abs((end_price - start_price) / start_price) * 100
        if volatility >= 10:
            sentiment = 5
        elif volatility >= 7.5:
            sentiment = 4
        elif volatility >= 5:
            sentiment = 3
        elif volatility >= 2.5:
            sentiment = 2
        else:
            sentiment = 1

        # **Boost Score for Certain Contexts**
        if "earnings report" in content.lower():
            pertinency += 1  # Earnings have more weight
        if "forecast" in content.lower() or "dividends" in content.lower():
            pertinency += 1  # Forecasts and dividends are crucial

        print(f"Inserting: {title}, Pertinency: {pertinency}, Sentiment: {sentiment}, Score: {sentiment_score}, Date: {date_time}")

        # Insert into the database
        conn = get_db_connection()
        conn.execute(
            """
            INSERT INTO messages (stock_id, title, content, pertinency, sentiment, source, start_price, end_price, date_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (stock_id, title, content, pertinency, sentiment, source, start_price, end_price, date_time)
        )
        conn.commit()
        conn.close()

        return jsonify({"message": "Message added successfully!"})

    except Exception as e:
        print("Error inserting message:", str(e))  # Debugging
        return jsonify({"error": str(e)}), 500


@app.route("/update_message/<int:message_id>", methods=["PUT"])
def update_message(message_id):
    data = request.json
    conn = get_db_connection()
    try:
        conn.execute(
            """
            UPDATE messages
            SET date_time = ?, title = ?, content = ?, source = ?, start_price = ?, end_price = ?
            WHERE id = ?
            """,
            (
                data["date_time"],
                data["title"],
                data["content"],
                data["source"],
                data["start_price"],
                data["end_price"],
                message_id,
            ),
        )
        conn.commit()
        return jsonify({"message": "Message updated successfully!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()



@app.route("/get_messages")
def get_messages():
    stock_id = request.args.get("stock_id")
    offset = int(request.args.get("offset", 0))  # Default offset is 0
    limit = int(request.args.get("limit", 5))   # Load 5 messages per request

    if not stock_id:
        return jsonify({"error": "Stock ID is required"}), 400

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        """
        SELECT id, title, content, pertinency, sentiment, source, start_price, end_price, date_time
        FROM messages
        WHERE stock_id = ?
        ORDER BY date_time DESC
        LIMIT ? OFFSET ?
        """,
        (stock_id, limit, offset)
    )
    messages = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify(messages)




@app.route("/add_description", methods=["POST"])
def add_description():
    data = request.json
    stock_id = data.get("stock_id")
    description = data.get("description")

    if not stock_id or not description:
        return jsonify({"error": "Stock ID and description are required"}), 400

    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO description (stock_id, description) VALUES (?, ?)",
            (stock_id, description),
        )
        conn.commit()
        return jsonify({"message": "Description added successfully!"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route("/get_description")
def get_description():
    stock_id = request.args.get("stock_id")

    if not stock_id:
        return jsonify({"error": "Stock ID is required"}), 400

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT description FROM description WHERE stock_id = ?", (stock_id,)
    )
    description = cursor.fetchone()
    conn.close()

    if not description:
        return jsonify({"description": None}), 404

    return jsonify({"description": description["description"]})

# Helper Functions
def analyze_message(content):
    # Dummy NLP analysis for pertinency and sentiment
    score = len(content.split()) % 5  # Example scoring
    sentiment = "positive" if "buy" in content.lower() else "negative"
    return {"score": score, "sentiment": sentiment}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
