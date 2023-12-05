make:
	docker build -t bully-app .
	docker tag bully-app asgersong/bully-app:latest
	docker push asgersong/bully-app:latest

start: 
	minikube start 
	minikube dashboard

scale:
	kubectl scale deployment bully-app --replicas=$(filter-out $@,$(MAKECMDGOALS))

delete:
	kubectl delete deployment bully-app

deploy:
	kubectl apply -f ./k8s/headless-service.yaml
	kubectl apply -f ./k8s/deployment.yaml

port:
	kubectl port-forward service/bully-service 8080:80

debug:
	kubectl delete deployment bully-app
	docker build -t bully-app .
	docker tag bully-app asgersong/bully-app:latest
	docker push asgersong/bully-app:latest
	kubectl apply -f ./k8s/headless-service.yaml
	kubectl apply -f ./k8s/deployment.yaml