import asyncio
from aiohttp import web
import os
import socket
import random
import aiohttp
import requests
import json
from requests import Session
from urllib.parse import urljoin
import json
from fortune import FortuneCookieJar  # Import the FortuneCookieJar class

POD_IP = str(os.environ["POD_IP"])
WEB_PORT = int(os.environ["WEB_PORT"])
POD_ID = random.randint(0, 100)
current_leader_id = None
current_leader_ip = None
candidates = {}
is_leader = False
halt = False


async def setup_k8s():
    await asyncio.sleep(10)
    print("K8S setup completed")


async def run_bully():
    global other_pods, current_leader_id, current_leader_ip, ip_list
    await setup_k8s()
    while True and current_leader_id != POD_ID:
        if is_leader:
            break
        try:
            # get pods
            ip_list = []
            response = socket.getaddrinfo("bully-service", 0, 0, 0, 0)
            for result in response:
                ip_list.append(result[-1][0])
            ip_list = list(set(ip_list))
            ip_list.remove(POD_IP)
            print(current_leader_ip, " and POD", POD_IP , )
            other_pods = dict()
            async with aiohttp.ClientSession() as session:
                for pod_ip in ip_list:
                    endpoint = "/pod_id"
                    url = f"http://{pod_ip}:{WEB_PORT}{endpoint}"
                    try:
                        async with session.get(url, timeout=2) as response:
                            if response.status == 200:
                                other_pods[str(pod_ip)] = await response.json()
                            else:
                                print(
                                    f"Request to {url} failed with status code {response.status}. Ignoring."
                                )
                    except aiohttp.ClientError as e:
                        print(f"Request to {url} failed with exception: {e}. Ignoring.")

            print(
                "Got %d other pod ip's" % (len(other_pods)),
                "\n",
                other_pods,
                "\n " "My ip: ",
                POD_IP,
                " id: ",
                POD_ID,
            )

            await asyncio.sleep(random.randint(1, 5))

            # Implement bully election

           
            await start_election()

            await asyncio.sleep(2)

            await candidate_selection()

            # Step 2A: Continue with election if you have the highest ID

            if current_leader_id == POD_ID:
                print(POD_IP, ": I'm here")
                # Stop running bul`ly and serve website
                await serve_website()
                break

            # Step 2B: Exit election and try again later
            await asyncio.sleep(5)

        except Exception as e:
            print(f"failed with exception: {e}. Ignoring.")


# GET /pod_id
async def pod_id(request):
    return web.json_response(POD_ID)


async def start_election():
    global other_pods, ip_list, current_leader_id, current_leader_ip, candidates

    if current_leader_id != POD_ID or current_leader_id == None:
        # If not already a leader, initiate the election process
        for pod_ip in ip_list:
            if other_pods.get(str(pod_ip), 0) > POD_ID:
                # Send election message to higher-priority pods
                endpoint = "/receive_election"
                if pod_ip == current_leader_ip:
                    return web.Response(status=200)
                url = f"http://{pod_ip}:{WEB_PORT}{endpoint}"
                try:
                    async with aiohttp.ClientSession() as session:
                        await session.post(url, timeout=10)
                    print(f"Sent election message to {pod_ip} this one ")
                except Exception as e:
                    print(f"An error occurred while sending election message: {e}")

    return web.Response(status=200)


async def candidate_selection():
    global current_leader_id, current_leader_ip
    print("selection ongoing")

    await asyncio.sleep(2)
    if current_leader_ip in candidates:
        return web.Response(status=200)


    if candidates == {}:
        print("The candidates: ", candidates)
        print(POD_IP, "There are no candidates higher than me")
        # Become coordinator, exit bully and start webservice.
        current_leader_ip = POD_IP
        current_leader_id = POD_ID
    else:
        max_ip = max(candidates, key=candidates.get, default=None)
        endpoint = "/become_coordinator"
        print(POD_IP, " with ID: ", POD_ID, "is sending to : ", max_ip)
        if max_ip == current_leader_ip:
            return web.Response(status=200)
        url = f"http://{max_ip}:{WEB_PORT}{endpoint}"
        try:
            print(max_ip)
            if halt == True:
                halt = False
                return web.Response(status=200)

            await aiohttp.ClientSession().post(url, timeout=3)
            print(f"Sent election message to {max_ip} debug twp")
        except Exception as e:
            print(f"An error occurred while sending election message: {e}")
            

        # Call start webservice on the current_leader
        # implement solution here


# pushasdas
# POST /receive_answer
async def receive_answer(request):
    global candidates
    print("creating candidates")
    sender_pod_ip = request.remote
    # Append the sender pod IP along with the sender pod ID to the candidates dictionary
    candidates[sender_pod_ip] = other_pods.get(sender_pod_ip, 0)
    print(candidates)

    return web.Response(status=200)


# POST /receive_election
async def receive_election(request):
    global other_pods, ip_list, POD_ID, WEB_PORT, POD_IP
    if current_leader_ip == POD_IP or current_leader_id == POD_ID:
    
        return web.Response(status=200)
    sender_pod_ip = request.remote

    # Get the pod_id of the sender
    if sender_pod_ip in other_pods:
        sender_pod_id = other_pods[sender_pod_ip]
        print(
            "Received election message from pod %s with ID %d"
            % (sender_pod_ip, sender_pod_id)
        )

        # Check if received election message has a higher ID
        if sender_pod_id < POD_ID:
            # Respond as this pod has a higher ID
            endpoint = "/receive_answer"
            url = f"http://{sender_pod_ip}:{WEB_PORT}{endpoint}"
            try:
                async with aiohttp.ClientSession() as session:
                    await session.post(url, timeout=10)
                    print("posted")
                print("Sent answer to %s" % sender_pod_ip)
            except Exception as e:
                print(f"An error occurred: {e}")

    else:
        print(f"Pod IP {sender_pod_ip} not found in other_pods dictionary.")

    # If we received an election message, we send an election message to all higher IDs
    if POD_ID < max(other_pods.values()):
        for higher_pod_ip in ip_list:
            if (
                other_pods.get(higher_pod_ip, -1) > POD_ID
                and current_leader_ip != higher_pod_ip
            ):
                endpoint = "/receive_election"
                if higher_pod_ip == current_leader_ip:
                    return web.Response(status=200)

                url = f"http://{higher_pod_ip}:{WEB_PORT}{endpoint}"
                try:
                    if current_leader_id == POD_ID:
                        return web.Response(status=200)
                    await aiohttp.ClientSession().post(url, timeout=3)
                    print(f"Sent election message to {higher_pod_ip} fuck")
                except Exception as e:
                    print(f"An error occurred while sending election message: {e}")

    return web.Response(status=200)


async def serve_website():
    global WEB_PORT
    print(POD_IP, ": is serving")
    app = web.Application()

    # Configure the default route for serving index.html
    app.router.add_get("/", lambda _: web.FileResponse("./index.html"))

    # Start the web server
    runner = web.AppRunner(app)
    await runner.setup()

    # Running the web server on port 80 on all interfaces
    site = web.TCPSite(runner, "0.0.0.0", 80)
    await site.start()


# POST /receive_coordinator
async def become_coordinator(request):
    global current_leader_id, current_leader_ip, is_leader
    if current_leader_id == POD_ID:
        return
    if is_leader == True:
        return web.Response(status=200)

    current_leader_ip = POD_IP
    current_leader_id = POD_ID
    for pod_ip in ip_list:
        endpoint = "/declare_leader"
        if pod_ip == current_leader_ip:
            return web.Response(status=200)

        url = f"http://{pod_ip}:{WEB_PORT}{endpoint}"
        try:
            if current_leader_ip == POD_ID:
                return web.Response(status=200)
            async with aiohttp.ClientSession() as session:
                await session.post(url, timeout=10)
                print("current leader ip is ", current_leader_ip, "sending to", pod_ip )
            print(f"Sent election message to {pod_ip}")
        except Exception as e:
            print(f"An error occurred while sending election message: {e}")
    is_leader = True
    return web.Response(status=200)


async def declare_leader(request):
    global current_leader_ip, halt
    current_leader_ip = request.remote
    halt = True
    return web.Response(status=200)


async def background_tasks(app):
    task = asyncio.create_task(run_bully())
    yield
    task.cancel()
    await task


async def check_leader_availability():
    try:
        endpoint = "/pod_id"
        url = f"http://{current_leader_ip}:{WEB_PORT}{endpoint}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=2) as response:
                return response.status == 200
    except aiohttp.ClientError:
        return False
    

fortunes = [
    "You will have a great day!",
    "Good things will come your way.",
    "A pleasant surprise is waiting for you.",
    "You will overcome any challenges with ease.",
    "Happiness is in your future.",
]

\
fortune_cookie_jar = FortuneCookieJar()

async def get_fortune(request):
    # Get a random fortune using FortuneCookieJar
    fortune = fortune_cookie_jar.get_random_fortune()
    return web.json_response({"fortune": fortune})

if __name__ == "__main__":
    app = web.Application()
    app.router.add_get("/pod_id", pod_id)
    app.router.add_get("/get_fortune", get_fortune)
    app.router.add_post("/receive_answer", receive_answer)
    app.router.add_post("/receive_election", receive_election)
    app.router.add_post("/become_coordinator", become_coordinator)
    app.cleanup_ctx.append(background_tasks)
    web.run_app(app, host="0.0.0.0", port=WEB_PORT)
