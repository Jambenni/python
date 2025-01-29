# Use an official Python image as the base
FROM python:3.9

# Set the working directory in the container
WORKDIR /app

# Copy all files from your repo into the container
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 8080 (used by Railway)
EXPOSE 8080

# Start the application
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8080", "app:app"]
