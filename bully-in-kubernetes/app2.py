import asyncio
from aiohttp import web
import os
import socket
import random
import aiohttp
import requests

POD_IP = str(os.environ['POD_IP'])
WEB_PORT = int(os.environ['WEB_PORT'])
POD_ID = random.randint(0, 100)
leader = False
other_pods = dict()
ip_list = []
web_running = False
error = False

# List of fortune cookies
FORTUNE_COOKIES = [
    "Today it’s up to you to create the peacefulness you long for.",
    "A friend asks only for your time not your money.",
    "If you refuse to accept anything but the best, you very often get it.",
    # ... Add more fortunes here
]

async def setup_k8s():
    print("K8S setup completed")
 
async def run_bully():
    global leader, other_pods, ip_list, web_running, error

    while True:
        error = False
        print("Running bully")
        await asyncio.sleep(5)  # wait for everything to be up

        # Get all pods doing bully
        print("Making a DNS lookup to service")
        try:
            response = socket.getaddrinfo("bully-service", 0, 0, 0, 0)
            print("Got response from DNS")
            for result in response:
                ip_list.append(result[-1][0])
            ip_list = list(set(ip_list))
        except Exception as e:
            print("DNS lookup failed")
            print("error: %s" % e)
            error = True

        # Remove own POD IP from the list of pods
        ip_list.remove(POD_IP)
        
        print("Got %d other pod IPs" % len(ip_list))

        # Get IDs of other pods by sending a GET request to them
        await asyncio.sleep(random.randint(1, 5))
        for pod_ip in ip_list:
            endpoint = '/pod_id'
            url = f'http://{pod_ip}:{WEB_PORT}{endpoint}'
            response = requests.get(url)
            other_pods[pod_ip] = response.json()

        print(other_pods)

        # If own ID is the highest, send coordinator message to all other pods
        if not error and POD_ID > max(other_pods.values()):
            print("I am the coordinator")
            leader = True
            try:
                for pod_ip in ip_list:
                    endpoint = '/receive_coordinator'
                    url = f'http://{pod_ip}:{WEB_PORT}{endpoint}'
                    requests.post(url)
            except Exception as e:
                print(f"An error occurred: {e}")

            if leader and not web_running:
                await serve_cookie()
                web_running = True
                break
        else:
            print("I am not the coordinator")
            try:
                for pod_ip in ip_list:
                    if other_pods[pod_ip] > POD_ID:
                        endpoint = '/receive_election'
                        url = f'http://{pod_ip}:{WEB_PORT}{endpoint}'
                        requests.post(url)
            except Exception as e:
                print(f"An error occurred: {e}")

        await asyncio.sleep(2)

async def pod_id(request):
    return web.json_response(POD_ID)

async def receive_answer(request):
    return await request.json()

async def receive_election(request):
    global other_pods, ip_list, POD_ID, WEB_PORT, POD_IP, leader, web_running

    pod_ip = request.remote
    if pod_ip in other_pods:
        pod_id = other_pods[pod_ip]
        print(f"Sender has ID {pod_id}")
        if POD_ID > pod_id:
            endpoint = "/receive_answer"
            url = f"http://{pod_ip}:{WEB_PORT}{endpoint}"
            try:
                async with aiohttp.ClientSession() as session:
                    await session.post(url, timeout=10)
                print(f"Sent answer to {pod_ip}")
            except Exception as e:
                print(f"An error occurred: {e}")
        print(request)
    else:
        print(f"Pod IP {pod_ip} not found in other_pods")

    if POD_ID < max(other_pods.values()):
        for pod_ip in ip_list:
            if other_pods[pod_ip] > POD_ID:
                endpoint = "/receive_election"
                url = f"http://{pod_ip}:{WEB_PORT}{endpoint}"
                requests.post(url)

    return web.Response(status=200)

async def receive_coordinator(request):
    global leader, other_pods, ip_list
    pod_ip = request.remote
    if pod_ip in other_pods:
        leader = other_pods[pod_ip]
    else:
        print(f"Pod IP {pod_ip} not found in other_pods")
    return web.Response(status=200)

async def serve_cookie():
    global web_running, leader, other_pods, ip_list
    if POD_ID > max(other_pods.values()):
        if web_running:
            return  # If the web server is already started, we don't need to start it again
        else:
            print("Running web")

            app = web.Application()

            async def handle_request(request):
                fortune = random.choice(FORTUNE_COOKIES)
                return web.Response(text=f"<html><body><h1>Your Fortune Cookie</h1><p>{fortune}</p></body></html>", content_type='text/html')

            app.router.add_get("/", handle_request)

            runner = web.AppRunner(app)
            await runner.setup()

            site = web.TCPSite(runner, "0.0.0.0", 80)
            await site.start()
            web_running = True
            return web.Response(status=200)

async def background_tasks(app):
    task = asyncio.create_task(run_bully())
    yield
    task.cancel()
    await task

if __name__ == "__main__":
    app = web.Application()
    app.router.add_get('/pod_id', pod_id)
    app.router.add_post('/receive_answer', receive_answer)
    app.router.add_post('/receive_election', receive_election)
    app.router.add_post('/receive_coordinator', receive_coordinator)
    app.cleanup_ctx.append(background_tasks)
    web.run_app(app, host='0.0.0.0', port=WEB_PORT)
