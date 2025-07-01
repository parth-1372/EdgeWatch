# EdgeWatch Docker Build and Management Scripts

# Build production image
build-prod:
	docker build -t edgewatch:latest -f deployment/Dockerfile .

# Build development image
build-dev:
	docker build -t edgewatch:dev -f deployment/Dockerfile.dev .

# Build both images
build-all: build-prod build-dev

# Run production container
run-prod:
	docker run -d --name edgewatch-prod -p 5000:5000 -p 8080:8080 edgewatch:latest

# Run development container with volume mounting
run-dev:
	docker run -d --name edgewatch-dev -p 5001:5000 -p 8081:8080 \
		-v $(PWD)/src:/app/src \
		-v $(PWD)/config:/app/config \
		-v $(PWD)/data:/app/data \
		edgewatch:dev

# Stop containers
stop:
	docker stop edgewatch-prod edgewatch-dev || true
	docker rm edgewatch-prod edgewatch-dev || true

# Clean up images
clean:
	docker rmi edgewatch:latest edgewatch:dev || true

# View logs
logs-prod:
	docker logs -f edgewatch-prod

logs-dev:
	docker logs -f edgewatch-dev

# Shell access to running containers
shell-prod:
	docker exec -it edgewatch-prod /bin/bash

shell-dev:
	docker exec -it edgewatch-dev /bin/bash

# Health check
health:
	curl -f http://localhost:5000/health || echo "Production container health check failed"
	curl -f http://localhost:5001/health || echo "Development container health check failed"

# Build and run complete development environment
dev-up: build-dev run-dev
	@echo "Development environment started"
	@echo "Access EdgeWatch at: http://localhost:5001"
	@echo "Access Dashboard at: http://localhost:5001/dashboard"

# Build and run production environment
prod-up: build-prod run-prod
	@echo "Production environment started"
	@echo "Access EdgeWatch at: http://localhost:5000"
	@echo "Access Dashboard at: http://localhost:5000/dashboard"

# Complete cleanup
clean-all: stop clean
	docker system prune -f

.PHONY: build-prod build-dev build-all run-prod run-dev stop clean logs-prod logs-dev shell-prod shell-dev health dev-up prod-up clean-all
