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
candidate_ip = None
is_leader = False
candidate_id = None
candidate_list = {}
ELECTION_IN_PROGRESS = False
leader_encountered = False


async def setup_k8s():
    print("setting p k8s")
    await asyncio.sleep(15)
    print("K8S setup completed")


async def run_bully():
    global other_pods, current_leader_id, current_leader_ip, ip_list, leader_encountered
    await setup_k8s()
    while True:
        try:
            if is_leader:
                serve_website()
                break
            # get pods
            ip_list = []
            response = socket.getaddrinfo("bully-service", 0, 0, 0, 0)
            for result in response:
                ip_list.append(result[-1][0])
            ip_list = list(set(ip_list))
            ip_list.remove(POD_IP)
            print(
                current_leader_ip,
                " and POD",
                POD_IP,
            )
            await asyncio.sleep(random.randint(1, 5))

            other_pods = dict()
            async with aiohttp.ClientSession() as session:
                for pod_ip in ip_list:
                    endpoint = "/pod_id"
                    url = f"http://{pod_ip}:{WEB_PORT}{endpoint}"
                    try:
                        async with session.get(url, timeout=2) as response:
                            if response.status == 200:
                                other_pods[str(pod_ip)] = await response.json()
                                if response.json() == current_leader_id:
                                    leader_encountered = True
                            else:
                                print(
                                    f"Request to {url} failed with status code {response.status}. Ignoring."
                                )
                    except aiohttp.ClientError as e:
                        print(f"Request to {url} failed with exception: {e}. Ignoring.")
            if leader_encountered:
                leader_encountered = False
                print(
                    "current leader encountered: ",
                    current_leader_ip,
                    " ",
                    current_leader_id,
                )
                continue
            print(
                "Got %d other pod ip's" % (len(other_pods)),
                "\n",
                other_pods,
                "\n " "My ip: ",
                POD_IP,
                " id: ",
                POD_ID,
            )
            print("ip list: ", ip_list)
            if pod_ip == current_leader_ip:
                continue
            await asyncio.sleep(random.randint(1, 2))

            # Implement bully election

            if not ELECTION_IN_PROGRESS:
                await change_election_status()

                await start_election()
                await candidate_selection()

                # Step 2A: Continue with election if you have the highest ID

            if current_leader_id == POD_ID or ip_list == []:
                print(POD_IP, ": I'm here")
                # Stop running bully and serve website

                await serve_website()
                await change_election_status()
                break

            # Step 2B: Exit election and try again later
            await asyncio.sleep(5)

        except Exception as e:
            print(f"failed with exception: {e}. Ignoring.")


async def pod_id(request):
    return web.json_response(POD_ID)


async def start_election():
    global other_pods, ip_list, current_leader_id, current_leader_ip, candidate_ip, candidate_id

    if current_leader_id != POD_ID or current_leader_id == None:
        # If not already a leader, initiate the election process
        for pod_ip in ip_list:
            if other_pods.get(str(pod_ip), 0) > POD_ID:
                # Send election message to higher-priority pods
                endpoint = "/receive_election"

                url = f"http://{pod_ip}:{WEB_PORT}{endpoint}"
                try:
                    async with aiohttp.ClientSession() as session:
                        await session.post(url, timeout=10)
                    print(f"Sent election message to {pod_ip} this one ")
                except Exception as e:
                    print(f"An error occurred while sending election message: {e}")

    return web.Response(status=200)


async def candidate_selection():
    global current_leader_id, current_leader_ip, candidate_ip, candidate_id, is_leader, candidate_list
    print("selection ongoing")
    await asyncio.sleep(10)
    print("my id: ", POD_ID, "cand id:", candidate_id)
    print("candidates so far: ", candidate_list)
    if candidate_list == {}:
        print(POD_IP, "There are no candidates higher than me", candidate_id)
        # Become coordinator, exit bully and start webservice.
        current_leader_ip = POD_IP
        current_leader_id = POD_ID
        is_leader = True
        for pod_ip in ip_list:
            endpoint = "/declare_leader"
            url = f"http://{pod_ip}:{WEB_PORT}{endpoint}"
            try:
                async with aiohttp.ClientSession() as session:
                    await session.post(url, timeout=10)
            except Exception as e:
                print(f"An error occurred while sending election message: {e}")

    else:
        endpoint = "/become_coordinator"
        url = f"http://{candidate_ip}:{WEB_PORT}{endpoint}"
        try:
            await aiohttp.ClientSession().post(url, timeout=3)
            print(f"Sent coordinator message to {candidate_id}")
        except Exception as e:
            print(f"An error occurred while sending election message: {e}")
        # Call start webservice on the current_leader
        # implement solution here
        candidate_id = None
        candidate_ip = None
        candidate_list = {}
        return


async def receive_answer(request):
    global candidate_ip, candidate_id, candidate_list
    print("creating candidates")
    sender_pod_ip = request.remote
    candidate_list[candidate_ip] = candidate_id
    # Append the sender pod IP along with the sender pod ID to the candidates dictionary
    temp = other_pods.get(sender_pod_ip, 0)
    if candidate_ip is None:
        candidate_ip = sender_pod_ip
        candidate_id = temp
        print("current highest candidate is: ", candidate_ip, ":", candidate_id)

        return web.Response(status=200)

    if candidate_id < temp:
        candidate_ip = sender_pod_ip
        candidate_id = temp

    # Add this part to await the response before returning a web.Response
    try:
        async with aiohttp.ClientSession() as session:
            # Do something with the response if needed
            pass
    except Exception as e:
        print(f"An error occurred in receive_answer: {e}")

    return web.Response(status=200)


# POST /receive_election
async def receive_election(request):
    global other_pods, ip_list, POD_ID, WEB_PORT, POD_IP
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
                    # Wait for the response before proceeding
                    async with session.post(url, timeout=10) as response:
                        if response.status == 200:
                            print("Sent answer to %s" % sender_pod_ip)
                        else:
                            print("Failed to send answer to %s" % sender_pod_ip)
            except Exception as e:
                print(f"An error occurred in receive_election: {e}")

    else:
        print(f"Pod IP {sender_pod_ip} not found in other_pods dictionary.")

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



async def become_coordinator(request):
    global current_leader_id, current_leader_ip, is_leader, ip_list
    if current_leader_id == POD_ID:
        return web.Response(status=200)

    print("I am becoming coordinator")
    current_leader_ip = POD_IP
    current_leader_id = POD_ID
    is_leader = True
    for pod_ip in ip_list:
        endpoint = "/declare_leader"
        if pod_ip == current_leader_ip:
            return web.Response(status=200)

        url = f"http://{pod_ip}:{WEB_PORT}{endpoint}"
        try:
            if current_leader_ip == pod_ip:
                return web.Response(status=200)
            async with aiohttp.ClientSession() as session:
                await session.post(url, timeout=10)
            print(f"Sent declare leader message to {pod_ip}")
        except Exception as e:
            print(f"An error occurred while sending election message: {e}")
    return web.Response(status=200)


async def declare_leader(request):
    global current_leader_ip, current_leader_id
    current_leader_ip = request.remote
    current_leader_id = other_pods[current_leader_ip]

    return web.Response(status=200)


async def change_election_status():
    global ip_list
    for pod in ip_list:
        endpoint = "/election_ongoing"
        url = f"http://{pod}:{WEB_PORT}{endpoint}"
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(url, timeout=10)
            print("changing status for %s" % pod)
        except Exception as e:
            print(f"An error occurred: {e}")


async def election_ongoing():
    global ELECTION_IN_PROGRESS
    ELECTION_IN_PROGRESS = not ELECTION_IN_PROGRESS
    asyncio.sleep(0.2)


async def check_leader_availability(current_leader_ip):
    try:
        if current_leader_ip is None:
            # If current_leader_ip is None, consider leader available
            return False
        else:
            # If current_leader_ip is not None, try sending a POST request to the leader
            endpoint = "/pod_id"
            url = f"http://{current_leader_ip}:{WEB_PORT}{endpoint}"

            async with aiohttp.ClientSession() as session:
                async with session.post(url, timeout=2) as response:
                    # Check if there is a response from the leader
                    if response.status == 200:
                        print("leader alive")
                        return True  # Leader is available
    except Exception as e:
        # Handle exceptions (e.g., timeout or connection error)
        print(f"Error checking leader availability: {e}")

    return False  # Leader is not available


async def background_tasks(app):
    task = asyncio.create_task(run_bully())
    yield
    task.cancel()
    await task


if __name__ == "__main__":
    app = web.Application()
    app.router.add_get("/pod_id", pod_id)
    app.router.add_post("/receive_answer", receive_answer)
    app.router.add_post("/receive_election", receive_election)
    app.router.add_post("/become_coordinator", become_coordinator)
    app.cleanup_ctx.append(background_tasks)
    web.run_app(app, host="0.0.0.0", port=WEB_PORT)
