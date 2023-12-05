import requests
from concurrent.futures import ThreadPoolExecutor
import time

# The URL of your local server
url = "http://localhost:8080"

# Number of concurrent requests per thread
num_requests_per_thread = 100

# Total number of threads
num_threads = 10

# List to store response times
response_times = []

# Function to send a single request
def send_request(_):
    try:
        start_time = time.time()
        response = requests.get(url)
        end_time = time.time()
        
        # Print the response status code and time taken
        print(f"Status Code: {response.status_code}, Time Taken: {end_time - start_time:.2f} seconds")
        
        # Append the response time to the list
        response_times.append(end_time - start_time)
    except Exception as e:
        print(f"Error: {e}")

# Use ThreadPoolExecutor to send multiple requests concurrently
with ThreadPoolExecutor(max_workers=num_threads) as executor:
    # Use map to apply the function to each value in the range
    executor.map(send_request, range(num_requests_per_thread))

# Calculate and print the average response time
average_response_time = sum(response_times) / len(response_times) if response_times else 0
print(f"Average Response Time: {average_response_time:.2f} seconds")
