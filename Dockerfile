# Use a Python image
FROM python:3.10

# Set working directory
WORKDIR /app

# Copy files
COPY . .

# Update system and install dependencies
RUN apt-get update && apt-get install -y python3 python3-pip

# Install Python dependencies separately
RUN pip install --no-cache-dir -r requirements.txt

# Expose the correct port
EXPOSE 5000

# Start the app properly
CMD ["python3", "app.py"]
