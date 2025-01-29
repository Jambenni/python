# Use official lightweight Python image
FROM python:3.9

# Set the working directory in the container
WORKDIR /app

# Install system dependencies (including SQLite3)
RUN apt-get update && apt-get install -y sqlite3 libsqlite3-dev

# Copy the project files into the container
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the correct port for Railway
EXPOSE 8080

# Start the application
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8080", "app:app"]
