FROM python:3.9

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y sqlite3 libsqlite3-dev

# Copy the project files
COPY . /app

# Ensure the database file is accessible
RUN chmod 777 /app/Stocks.db

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the correct port
EXPOSE 8080

# Start the application
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8080", "app:app"]

