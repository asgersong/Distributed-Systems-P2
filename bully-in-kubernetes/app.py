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


async def setup_k8s():
    # If you need to do setup of Kubernetes, i.e. if using Kubernetes Python client
	print("K8S setup completed")
 
async def run_bully():

    global leader, other_pods, ip_list, web_running, error

    while True:
        error = False

        print("Running bully")
        await asyncio.sleep(5) # wait for everything to be up
        
        # Get all pods doing bully
        print("Making a DNS lookup to service")
        try:
            response = socket.getaddrinfo("bully-service",0,0,0,0)
            print("Get response from DNS")
            for result in response:
                ip_list.append(result[-1][0])
            ip_list = list(set(ip_list))
        except Exception as e:
            print("DNS lookup failed")
            print("error: %s" % (e))
            error = True
        
        # Remove own POD ip from the list of pods
        ip_list.remove(POD_IP)
        
        print("Got %d other pod ip's" % (len(ip_list)))
        
        # Get ID's of other pods by sending a GET request to them
        await asyncio.sleep(random.randint(1, 5))
        for pod_ip in ip_list:
            endpoint = '/pod_id'
            url = 'http://' + str(pod_ip) + ':' + str(WEB_PORT) + endpoint
            response = requests.get(url)
            other_pods[str(pod_ip)] = response.json()
            
        # Other pods in network
        print(other_pods)

        # If own ID is the highest, send coordinator message to all other pods
        if not error and POD_ID > max(other_pods.values()):
            print("I am the coordinator")
            leader = True
            try:
                for pod_ip in ip_list:
                    endpoint = '/receive_coordinator'
                    url = 'http://' + str(pod_ip) + ':' + str(WEB_PORT) + endpoint
                    response = requests.post(url)
            except Exception as e:
                print(f"An error occurred: {e}")

            if leader and not web_running:
                await serve_cookie()
                web_running = True
                break  # Break the loop as coordinator has started the web server
        else:
            # If own ID is not the highest, send election message to all other pods with higher ID
            print("I am not the coordinator")
            try:
                for pod_ip in ip_list:
                    if other_pods[pod_ip] > POD_ID:
                        endpoint = '/receive_election'
                        url = 'http://' + str(pod_ip) + ':' + str(WEB_PORT) + endpoint
                        response = requests.post(url)
                        print(response)
            except Exception as e:
                print(f"An error occurred: {e}")
                # if the request fails, we do nothing and wait for the next round

        error = False
        
        # Sleep a bit, then repeat
        await asyncio.sleep(2)
    
#GET /pod_id
async def pod_id(request):
    return web.json_response(POD_ID)
    
#POST /receive_answer
async def receive_answer(request):
    return await request.json()

#POST /receive_election
async def receive_election(request):
    global other_pods, ip_list, POD_ID, WEB_PORT, POD_IP, leader, web_running

    pod_ip = request.remote 

    if str(pod_ip) in other_pods:
        # Get the pod_id of the sender
        pod_id = other_pods[str(pod_ip)]
        print("Sender has ID %d" % (pod_id))
        # if we receive an election message, we send an answer back because we have a higher ID
        print("My ID is %d" % (POD_ID))
        if POD_ID > pod_id:
            # send answer back
            endpoint = "/receive_answer"
            url = "http://" + str(pod_ip) + ":" + str(WEB_PORT) + endpoint
            print("sending answer...")
            print(f"URL: {url}")
            try:
                async with aiohttp.ClientSession() as session:
                    await session.post(url, timeout=10)
                print("Sent answer to %s" % (pod_ip))
            except Exception as e:
                print(f"An error occurred: {e}")
        # print what the request was
        print(request)
    else:
        print(f"Pod IP {pod_ip} not found in other_pods dictionary.")

    # if we receive an election message, we send an election message to all higher ID's
    if POD_ID < max(other_pods.values()):
        for pod_ip in ip_list:
            if other_pods[str(pod_ip)] > POD_ID:
                endpoint = "/receive_election"
                url = "http://" + str(pod_ip) + ":" + str(WEB_PORT) + endpoint
                requests.post(url)

    return web.Response(status=200)

#POST /receive_coordinator
async def receive_coordinator(request):
    global leader, other_pods, ip_list
    # lets get the pod_id of the sender
    print("Received coordinator message")
    pod_ip = request.remote  # this is the ip of the sender
    # now we have the id of the coordinator
    if str(pod_ip) in other_pods:
        leader = other_pods[str(pod_ip)]
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

            # Configure serving static files
            # app.router.add_static('/assets/', path='./web/assets', name='assets')

            # Configure the default route for serving index.html
            app.router.add_get(
                "/", lambda _: web.FileResponse("./website/cookie.html")
            )

            # Start the web server
            runner = web.AppRunner(app)
            await runner.setup()

            # Running the webserver on port 80 on all interfaces
            site = web.TCPSite(runner, "0.0.0.0", 80)
            await site.start()
            web_running = True
            return web.Response(status=200)

async def cookie(request):
    # Load and serve the HTML file
    with open('index.html', 'r') as f:
        html_content = f.read()
    return web.Response(text=html_content, content_type='text/html')

async def serve_cookie_old():
    app = web.Application()
    app.router.add_get('/', cookie)
    app.cleanup_ctx.append(background_tasks)
    web.run_app(app, host='0.0.0.0', port=WEB_PORT)

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
