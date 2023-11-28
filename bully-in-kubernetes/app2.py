import asyncio
from aiohttp import web, ClientSession
import os
import socket
import random

POD_IP = str(os.environ['POD_IP'])
WEB_PORT = int(os.environ['WEB_PORT'])
POD_ID = random.randint(0, 100)
leader_id = None

async def setup_k8s():
    print("K8S setup completed")

async def send_message(pod_ip, endpoint, data):
    async with ClientSession() as session:
        url = f'http://{pod_ip}:{WEB_PORT}{endpoint}'
        try:
            await session.post(url, json=data)
        except Exception as e:
            print(f"Error sending message to {pod_ip}: {e}")

async def run_bully():
    global leader_id
    while True:
        print("Running bully")
        await asyncio.sleep(5) # wait for everything to be up

        # Get all pods doing bully
        ip_list = []
        print("Making a DNS lookup to service")
        response = socket.getaddrinfo("bully-service", 0, 0, 0, 0)
        print("Get response from DNS")
        for result in response:
            ip_list.append(result[-1][0])
        ip_list = list(set(ip_list))

        # Remove own POD ip from the list of pods
        ip_list.remove(POD_IP)
        print(f"Got {len(ip_list)} other pod ip's")

        # Get IDs of other pods by sending a GET request to them
        await asyncio.sleep(random.randint(1, 5))
        other_pods = dict()
        async with ClientSession() as session:
            for pod_ip in ip_list:
                url = f'http://{pod_ip}:{WEB_PORT}/pod_id'
                try:
                    async with session.get(url) as response:
                        other_pods[pod_ip] = await response.json()
                except Exception as e:
                    print(f"Error getting pod ID from {pod_ip}: {e}")

        # Check if there's need to initiate an election
        if leader_id is None or leader_id not in other_pods.values():
            higher_ids = [ip for ip, id in other_pods.items() if id > POD_ID]
            if not higher_ids:  # No higher IDs, declare self as leader
                leader_id = POD_ID
                for pod_ip in ip_list:
                    await send_message(pod_ip, '/receive_coordinator', {"leader_id": POD_ID})
            else:
                for pod_ip in higher_ids:
                    await send_message(pod_ip, '/receive_election', {"origin_id": POD_ID})
                    await asyncio.sleep(1)  # Wait for responses

        await asyncio.sleep(2)

# GET /pod_id
async def pod_id(request):
    return web.json_response({"id": POD_ID})
    
# POST /receive_answer
async def receive_answer(request):
    global leader_id
    data = await request.json()
    responder_id = data.get("responder_id")
    if responder_id > POD_ID:
        leader_id = responder_id
    return web.Response(text="Received answer")

# POST /receive_election
async def receive_election(request):
    data = await request.json()
    origin_id = data.get("origin_id")
    if POD_ID > origin_id:
        # Send answer back to originator
        await send_message(origin_id, '/receive_answer', {"responder_id": POD_ID})
    # Start own election process
    return web.Response(text="Election received")

# POST /receive_coordinator
async def receive_coordinator(request):
    global leader_id
    data = await request.json()
    leader_id = data.get("leader_id")
    return web.Response(text="New Coordinator Acknowledged")

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
