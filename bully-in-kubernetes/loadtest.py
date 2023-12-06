import requests
from concurrent.futures import ThreadPoolExecutor
import time

def load_test(num_threads, num_requests_per_thread):
    response_times = []

    def send_request(_):
        try:
            start_time = time.time()
            response = requests.get(url)
            end_time = time.time()
            
            print(f"Status Code: {response.status_code}, Time Taken: {end_time - start_time:.2f} seconds")
            response_times.append(end_time - start_time)
        except Exception as e:
            print(f"Error: {e}")

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        executor.map(send_request, range(num_requests_per_thread))

    return sum(response_times) / len(response_times) if response_times else 0

url = "http://localhost:8080"
thread_counts = [10, 100, 1000, 10000, 100000, 1000000]
num_repetitions = 10
num_requests_per_thread = 1000

# Dictionary to store the average of averages for each thread count
test_results = {}

for num_threads in thread_counts:
    averages = [load_test(num_threads, num_requests_per_thread) for _ in range(num_repetitions)]
    avg_of_avgs = sum(averages) / len(averages)
    test_results[num_threads] = avg_of_avgs

# Print the test results
print("\nLoad Test Results:")
for num_threads, avg_of_avgs in test_results.items():
    print(f"{num_threads} Threads, Average of Averages Response Time: {avg_of_avgs:.2f} seconds")
