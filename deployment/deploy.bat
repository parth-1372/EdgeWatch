@echo off
REM EdgeWatch Deployment Script for Windows
REM Automated deployment for production environments

setlocal enabledelayedexpansion

REM Configuration
set DEPLOYMENT_ENV=%DEPLOYMENT_ENV%
if "%DEPLOYMENT_ENV%"=="" set DEPLOYMENT_ENV=production
set EDGEWATCH_VERSION=%EDGEWATCH_VERSION%
if "%EDGEWATCH_VERSION%"=="" set EDGEWATCH_VERSION=latest

REM Colors (limited on Windows)
set GREEN=[32m
set BLUE=[34m
set YELLOW=[33m
set RED=[31m
set NC=[0m

REM Print banner
echo %GREEN%
echo ================================================================================
echo                          EdgeWatch Deployment Script
echo                     Automated Container Deployment (Windows)
echo ================================================================================
echo %NC%

REM Check prerequisites
echo %BLUE%[INFO] Checking prerequisites...%NC%

docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo %RED%[ERROR] Docker is not installed. Please install Docker Desktop first.%NC%
    exit /b 1
)

docker-compose --version >nul 2>&1
if %errorlevel% neq 0 (
    echo %RED%[ERROR] Docker Compose is not installed. Please install Docker Compose first.%NC%
    exit /b 1
)

REM Check Docker daemon is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo %RED%[ERROR] Docker daemon is not running. Please start Docker Desktop first.%NC%
    exit /b 1
)

echo %GREEN%[SUCCESS] Prerequisites check passed%NC%

REM Main deployment function
if "%1"=="deploy" goto deploy
if "%1"=="update" goto update
if "%1"=="status" goto status
if "%1"=="cleanup" goto cleanup
if "%1"=="health" goto health
if "%1"=="" goto deploy
goto help

:deploy
echo %BLUE%[INFO] Starting EdgeWatch deployment...%NC%

REM Create directories
if not exist "..\data" mkdir "..\data"
if not exist "..\logs" mkdir "..\logs"
if not exist "..\config" mkdir "..\config"
if not exist "monitoring\grafana\dashboards" mkdir "monitoring\grafana\dashboards"
if not exist "monitoring\grafana\provisioning" mkdir "monitoring\grafana\provisioning"
if not exist "nginx\ssl" mkdir "nginx\ssl"
if not exist "sql" mkdir "sql"

REM Copy configuration if it doesn't exist
if not exist "..\config\production.ini" (
    echo %BLUE%[INFO] Creating production configuration...%NC%
    copy "..\config\default.ini" "..\config\production.ini"
)

REM Build images
echo %BLUE%[INFO] Building EdgeWatch Docker images...%NC%
cd ..
docker build -t edgewatch:%EDGEWATCH_VERSION% -f deployment\Dockerfile .
if "%EDGEWATCH_VERSION%" neq "latest" (
    docker tag edgewatch:%EDGEWATCH_VERSION% edgewatch:latest
)
cd deployment

REM Deploy services
echo %BLUE%[INFO] Deploying EdgeWatch services...%NC%
docker-compose -f docker-compose.yml up -d

echo %GREEN%[SUCCESS] EdgeWatch deployed successfully%NC%
goto status

:update
echo %BLUE%[INFO] Updating EdgeWatch deployment...%NC%
cd ..
docker build -t edgewatch:%EDGEWATCH_VERSION% -f deployment\Dockerfile .
cd deployment
docker-compose -f docker-compose.yml up -d --force-recreate
echo %GREEN%[SUCCESS] Deployment updated successfully%NC%
goto status

:status
echo %BLUE%[INFO] Deployment Status:%NC%
echo.
docker-compose -f docker-compose.yml ps
echo.
echo %GREEN%EdgeWatch Services:%NC%
echo   Primary Node:    http://localhost:5000
echo   Secondary Node:  http://localhost:5001
echo   Dashboard:       http://localhost:8080
echo   Grafana:         http://localhost:3000 (admin/edgewatch_admin_2025)
echo   Prometheus:      http://localhost:9000
echo   Nginx:           http://localhost:80
echo.
goto end

:cleanup
echo %BLUE%[INFO] Cleaning up deployment resources...%NC%
docker-compose -f docker-compose.yml down
if "%2"=="--remove-images" (
    echo %BLUE%[INFO] Removing EdgeWatch images...%NC%
    docker rmi edgewatch:latest edgewatch:%EDGEWATCH_VERSION% 2>nul
)
if "%2"=="--remove-volumes" (
    echo %BLUE%[INFO] Removing volumes...%NC%
    docker-compose -f docker-compose.yml down -v
)
echo %GREEN%[SUCCESS] Cleanup completed%NC%
goto end

:health
echo %BLUE%[INFO] Performing health checks...%NC%
set /a attempt=0
set /a max_attempts=30

:health_loop
curl -f http://localhost:5000/health >nul 2>&1
if %errorlevel% equ 0 (
    echo %GREEN%[SUCCESS] Primary node health check passed%NC%
    goto health_secondary
)

set /a attempt+=1
if %attempt% geq %max_attempts% (
    echo %RED%[ERROR] Health check failed after %max_attempts% attempts%NC%
    goto end
)

echo %BLUE%[INFO] Health check attempt %attempt%/%max_attempts%...%NC%
timeout /t 5 /nobreak >nul
goto health_loop

:health_secondary
curl -f http://localhost:5001/health >nul 2>&1
if %errorlevel% equ 0 (
    echo %GREEN%[SUCCESS] Secondary node health check passed%NC%
) else (
    echo %YELLOW%[WARNING] Secondary node health check failed%NC%
)

echo %GREEN%[SUCCESS] Health checks completed%NC%
goto end

:help
echo Usage: %0 {deploy^|update^|status^|cleanup^|health}
echo.
echo Commands:
echo   deploy   - Full deployment (default)
echo   update   - Update existing deployment
echo   status   - Show deployment status
echo   cleanup  - Stop and cleanup resources
echo   health   - Run health checks
echo.
echo Cleanup options:
echo   --remove-images   - Also remove Docker images
echo   --remove-volumes  - Also remove data volumes
echo.
echo Environment variables:
echo   DEPLOYMENT_ENV     - production^|development (default: production)
echo   EDGEWATCH_VERSION  - Image version tag (default: latest)
echo.
goto end

:end
endlocal
