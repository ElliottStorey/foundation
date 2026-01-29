import json
import shutil
import subprocess
import socket
import time
import sys
import os
from pathlib import Path
from enum import Enum
from typing import Annotated
import typer
from rich.console import Console
from rich.table import Table

app_name = "foundation"
app_dir = typer.get_app_dir(app_name)
proxy_compose_path = Path(app_dir) / "compose.json"
services_path = Path(app_dir) / "services"
services_compose_path = services_path / "compose.json"

app = typer.Typer(
    name="foundation",
    help="CLI tool for managing Docker services with automatic reverse proxying and SSL termination.",
    no_args_is_help=True
)

console = Console()

class Output:
    @staticmethod
    def info(text, exit = False):
        console.print(text)
        if exit: raise typer.Exit()

    @staticmethod
    def success(text, exit = False):
        console.print(f"[bold green]SUCCESS:[/] {text}")
        if exit: raise typer.Exit()

    @staticmethod
    def error(text, exit = True):
        console.print(f"[bold red]ERROR:[/] {text}")
        if exit: raise typer.Exit(code=1)

class Docker:
    @staticmethod
    def installed():
        try:
            subprocess.run(["docker", "--version"], capture_output=True, check=True)
            return True
        except:
            return False
    
    @staticmethod
    def running():
        try:
            subprocess.run(["docker", "info"], capture_output=True, check=True)
            return True
        except Exception as error:
            return "permission denied" in error.stderr.decode().lower()
    
    @staticmethod
    def permissions():
        try:
            subprocess.run(["docker", "info"], capture_output=True, check=True)
            return True
        except:
            return False

    @staticmethod
    def install():
        try:
            subprocess.run(["curl", "-fsSL", "https://get.docker.com", "-o", "get-docker.sh"], capture_output=True, check=True)
            subprocess.run(["sh", "get-docker.sh"], capture_output=True, check=True)
        finally:    
            Path("get-docker.sh").unlink(missing_ok=True)

    @staticmethod
    def is_image(source):
        try:
            subprocess.run(["docker", "manifest", "inspect", source], capture_output=True, check=True, timeout=10)
            return True
        except:
            return False
        
    @staticmethod
    def get_compose(compose_path):
        result = subprocess.run(["docker", "compose", "-f", compose_path, "config", "--format", "json"], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    
    @staticmethod
    def get_compose_status(compose_path):
        names = Docker.get_compose(compose_path).get("services", {}).keys()
        result = subprocess.run(["docker", "compose", "-f", compose_path, "ps", "-a", "--format", "json"], capture_output=True, text=True, check=True)

        try:
            services = json.loads(result.stdout)
        except json.JSONDecodeError:
            services = [json.loads(line) for line in result.stdout.strip().split("\n") if line]
        
        services = {service.get("Service"): service for service in services}

        return {
            name: {
                "state": services.get(name, {}).get("State"),
                "status": services.get(name, {}).get("Status"),
                "created_at": services.get(name, {}).get("CreatedAt")
            } for name in names
        }
    
    @staticmethod
    def update_compose(compose_path, compose):
        old_compose = Docker.get_compose(compose_path)
        compose_path.write_text(json.dumps(compose, indent=2), encoding="utf-8")
        try:
            subprocess.run(["docker", "compose", "-f", compose_path, "config", "--format", "json"], capture_output=True, check=True)
        except:
            compose_path.parent.mkdir(parents=True, exist_ok=True)
            compose_path.write_text(json.dumps(old_compose, indent=2), encoding="utf-8")
    
    @staticmethod
    def build(tag, build_path):
        subprocess.run(["docker", "build", "-t", tag, build_path], capture_output=True, check=True)

    @staticmethod
    def enable_buildkit(name="railpack_builder"):
        if subprocess.run(["docker", "buildx", "inspect", name], capture_output=True).returncode == 0:
            subprocess.run(["docker", "buildx", "use", name], capture_output=True, check=True)
            return
        subprocess.run(["docker", "buildx", "create", "--name", name, "--driver", "docker-container", "--use", "--bootstrap"], capture_output=True, check=True)

    @staticmethod
    def build_from_railpack_plan(tag, railpack_plan_path, service_path):
        subprocess.run([
            "docker", "buildx", "build",
            "--build-arg", "BUILDKIT_SYNTAX=ghcr.io/railwayapp/railpack-frontend",
            "--tag", tag,
            "--file", railpack_plan_path,
            service_path,
            "--load"
        ], capture_output=True, check=True)

class Git:
    @staticmethod
    def installed():
        try:
            subprocess.run(["git", "--version"], capture_output=True, check=True)
            return True
        except:
            return False
    
    @staticmethod
    def install():
        try:
            subprocess.run(["curl", "-fsSL", "https://raw.githubusercontent.com/ElliottStorey/git-install/main/install.sh", "-o", "get-git.sh"], capture_output=True, check=True)
            subprocess.run(["sh", "get-git.sh"], capture_output=True, check=True)
        finally:    
            Path("get-git.sh").unlink(missing_ok=True)

    @staticmethod
    def is_repo(source):
        try:
            subprocess.run(["git", "ls-remote", source], capture_output=True, check=True, timeout=10)
            return True
        except:
            return False
    
    @staticmethod
    def clone(source, path):
        path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", source, "."], cwd=path, capture_output=True, check=True)
        return
    
    @staticmethod
    def has_changes(path):
        subprocess.run(["git", "fetch"], cwd=path, capture_output=True, check=True)
        result = subprocess.run(["git", "rev-list", "--count", "HEAD..@{u}"], cwd=path, capture_output=True, text=True, check=True)
        return int(result.stdout.strip()) > 0 

    @staticmethod
    def reset(path):
        subprocess.run(["git", "reset", "--hard", "@{u}"], cwd=path)

class Railpack:
    @staticmethod
    def installed():
        try:
            subprocess.run(["railpack", "--version"], capture_output=True, check=True)
            return True
        except:
            return False

    @staticmethod
    def install():
        try:
            subprocess.run(["curl", "-fsSL", "https://railpack.com/install.sh", "-o", "get-railpack.sh"], capture_output=True, check=True)
            subprocess.run(["sh", "get-railpack.sh"], capture_output=True, check=True)
        finally:    
            Path("get-railpack.sh").unlink(missing_ok=True)
    
    @staticmethod
    def prepare(path, plan_out):
        subprocess.run(["railpack", "prepare", path, "--plan-out", plan_out], capture_output=True, check=True)

class Systemd:
    SERVICE_PATH = Path("/etc/systemd/system/foundation.service")

    @staticmethod
    def install():
        # Detect how to run the current script
        executable = sys.executable
        script_path = Path(__file__).resolve()
        
        # NOTE: This runs the 'watch' command in a loop
        command = f"{executable} {script_path} watch"

        content = f"""[Unit]
Description=Foundation Infrastructure Watcher
After=docker.service network-online.target
Requires=docker.service

[Service]
ExecStart={command}
Restart=always
RestartSec=30
WorkingDirectory={app_dir}
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
        try:
            Systemd.SERVICE_PATH.write_text(content, encoding="utf-8")
            subprocess.run(["systemctl", "daemon-reload"], check=True)
            subprocess.run(["systemctl", "enable", "--now", "foundation"], check=True)
            return True
        except PermissionError:
            return False
        except subprocess.CalledProcessError:
            return False

def port_available(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("0.0.0.0", port)) != 0

@app.callback()
def main(ctx: typer.Context):
    if ctx.invoked_subcommand in [None, "install"]: return

    if not Docker.installed():
        Output.error("Prerequisite missing: Docker. Run [b]foundation install[/] to attempt automatic installation.")
    
    if not Docker.running():
        Output.error("Docker is installed but the service is not running. Please start the Docker system service.")
    
    if not Docker.permissions():
        Output.error("Permission denied when accessing Docker socket. Run with [b]sudo[/] or add the current user to the 'docker' group.")

    if not Git.installed():
        Output.error("Prerequisite missing: Git. Run [b]foundation install[/] to attempt automatic installation.")
    
    if not Railpack.installed():
        Output.error("Prerequisite missing: Railpack. Run [b]foundation install[/] to attempt automatic installation.")

    if not proxy_compose_path.exists() or not services_compose_path.exists():
        Output.error("Foundation configuration not found. Run [b]foundation install[/] to initialize.")

    try:
        Docker.get_compose(proxy_compose_path)
        Docker.get_compose(services_compose_path)
    except:
        Output.error("Configuration files are corrupted or invalid. Run [b]foundation install[/] to reset configuration.")

    if ctx.invoked_subcommand == "deploy": return

    try:
        proxy_status = Docker.get_compose_status(proxy_compose_path)
        if not all(s["state"] == "running" for s in proxy_status.values()): raise
    except:
        Output.error("The reverse proxy is not active. Run [b]foundation deploy[/] to start the infrastructure.")

@app.command(help="Install dependencies, generate config, and setup auto-updater service.")
def install(
    default_email: Annotated[str, typer.Option(help="Email address used for Let's Encrypt SSL registration.", prompt="Email for SSL")]
):
    # --- Dependencies ---
    Output.info("Checking Docker installation...")
    if not Docker.installed():
        try:
            Docker.install()
        except:
            Output.error("Failed to install Docker automatically. Please install Docker manually.")
    Output.success("Docker is installed.")

    Output.info("Checking Git installation...")
    if not Git.installed():
        try:
            Git.install()
        except:
            Output.error("Failed to install Git automatically. Please install Git manually.")
    Output.success("Git is installed.")

    Output.info("Checking Railpack installation...")
    if not Railpack.installed():
        try:
            Railpack.install()
        except:
            Output.error("Failed to install Railpack automatically. Please install Railpack manually.")
    Output.success("Railpack is installed.")
 
    # --- Configuration ---
    try:
        services_compose = Docker.get_compose(services_compose_path)
        services = services_compose.get("services", {})
        volumes = services_compose.get("volumes", {})
        Output.info("Detected existing configuration. Preserving services and volumes.")
    except:
        services = {}
        volumes = {}

    proxy_compose = {
        "name": "foundation",
        "services": {
            "nginx-proxy": {
                "container_name": "nginx-proxy",
                "image": "nginxproxy/nginx-proxy",
                "volumes": [
                    "certs:/etc/nginx/certs",
                    "html:/usr/share/nginx/html",
                    "/var/run/docker.sock:/tmp/docker.sock:ro"
                ],
                "ports": ["80:80", "443:443"],
                "networks": ["foundation_network"],
                "restart": "unless-stopped"
            },
            "nginx-proxy-acme": {
                "container_name": "nginx-proxy-acme",
                "image": "nginxproxy/acme-companion",
                "environment": {"DEFAULT_EMAIL": default_email},
                "volumes": [
                    "/var/run/docker.sock:/var/run/docker.sock:ro",
                    "acme:/etc/acme.sh"
                ],
                "volumes_from": ["nginx-proxy"],
                "networks": ["foundation_network"],
                "restart": "unless-stopped"
            }
        },
        "volumes": {"certs": {}, "html": {}, "acme": {}},
        "networks": {"foundation_network": {"name": "foundation_network"}}
    }

    services_compose = {
        "name": "foundation services",
        "services": services,
        "volumes": volumes,
        "networks": {
            "foundation_network": {
                "external": True,
                "name": "foundation_network"
            }
        }
    }

    Output.info("Generating configuration files for proxy and services...")
    try:
        Docker.update_compose(proxy_compose_path, proxy_compose)
        Docker.update_compose(services_compose_path, services_compose)
    except:
        Output.error("Failed to write configuration files. Ensure valid JSON structure in existing compose files.")
    Output.success("Configuration files generated.")

    # --- Systemd Service ---
    Output.info("Installing background auto-update service...")
    if Systemd.install():
        Output.success("Foundation background service installed and started.")
    else:
        # We don't exit here, because the tool still works manually without the service
        Output.info("Warning: Could not install systemd service (permission denied). Run with [b]sudo[/] to enable auto-updates.")

    # --- Deploy ---
    deploy()

    Output.success("Foundation installation and deployment complete.")

@app.command(help="Start the reverse proxy and all registered services.")
def deploy():
    Output.info("Starting reverse proxy...")
    try:
        subprocess.run(["docker", "compose", "-f", proxy_compose_path, "up", "-d"], capture_output=True, check=True)
    except:
        if not (port_available(80) and port_available(443)):
            Output.error("Failed to start proxy: Ports 80 and/or 443 are already in use by another application.")
        Output.error("Failed to start proxy container.")
    Output.success("Reverse proxy active.")

    Output.info("Checking service definitions...")
    if not Docker.get_compose(services_compose_path).get("services"):
        Output.info("No services defined. Run [b]foundation create[/] to add your first service.", exit=True)

    Output.info("Starting services...")
    try:
        subprocess.run(["docker", "compose", "-f", services_compose_path, "up", "-d", "--remove-orphans"], check=True)
    except:
        Output.error("Failed to start one or more services. Check Docker logs for details.")
    Output.success("All services started.")

@app.command(help="Display the health, uptime, and configuration of managed services.")
def status():
    services_compose = Docker.get_compose(services_compose_path)
    services_status = Docker.get_compose_status(services_compose_path)

    if not services_status:
        Output.info("No services found. Run [b]foundation create[/] to add a service.", exit=True)

    table = Table(box=None, header_style="bold blue")
    table.add_column("Service Name")
    table.add_column("Status")
    table.add_column("Uptime")
    table.add_column("Public Host")

    for service_name, service_status in services_status.items():
        status = service_status.get("status", "unknown")
        uptime = service_status.get("state", "unknown")
        host = services_compose.get("services", {}).get(service_name, {}).get("environment", {}).get("VIRTUAL_HOST", "-")

        table.add_row(service_name, status, uptime, host)

    console.print(table)

@app.command(help="Fetch latest Git commits, pull images, and rebuild services.")
def update():
    Output.info("Pulling latest Docker images for defined services...")
    try:
        subprocess.run(["docker", "compose", "-f", services_compose_path, "pull"], capture_output=True, check=True)
    except:
        Output.error("Failed to pull some Docker images. Check network connection or image names.")
    Output.success("Images pulled.")

    services_compose = Docker.get_compose(services_compose_path)
    service_names = services_compose.get("services", {}).keys()

    for service_name in service_names:
        service_path = services_path / service_name

        if not service_path.is_dir(): continue

        try:
            if Git.has_changes(service_path):
                Output.info(f"Detected remote changes for [b i]{service_name}[/]. updating repository...")
                try:
                    Git.reset(service_path)
                except:
                    Output.error(f"Failed to reset/pull repo for service [b i]{service_name}[/].")
                Output.success(f"Repository updated for [b i]{service_name}[/].")
        except:
            pass

        dockerfile_path = service_path / "Dockerfile"
        if dockerfile_path.is_file():
            services_compose.setdefault("services", {}).setdefault(service_name, {}).setdefault("build", {})["context"] = service_path
            services_compose.get("services", {}).get(service_name, {}).pop("image", None)
            continue

        Output.info(f"No Dockerfile found for [b i]{service_name}[/]. Generating image using Railpack...")
        try:
            railpack_plan_path = service_path / f"{service_name}-railpack-plan.json"
            Railpack.prepare(service_path, railpack_plan_path)
            Docker.enable_buildkit()
            Docker.build_from_railpack_plan(f"foundation/{service_name}", railpack_plan_path, service_path)
        except:
            Output.error(f"Failed to generate Railpack image for service [b i]{service_name}[/]")
        Output.success(f"Image generated for [b i]{service_name}[/].")

        services_compose.setdefault("services", {}).setdefault(service_name, {})["image"] = f"foundation/{service_name}"
        services_compose.get("services", {}).get(service_name, {}).pop("build", None)

    Output.info("Building images for services with Dockerfiles...")
    try:
        subprocess.run(["docker", "compose", "-f", services_compose_path, "build"], capture_output=True, check=True)
    except:
        Output.error("Build failed for one or more services.")
    Output.success("Services built.")

    Output.success("Update complete. Run 'foundation deploy' to apply changes.")

class RestartPolicy(str, Enum):
    no = "no"
    always = "always"
    on_failure = "on-failure"
    unless_stopped = "unless-stopped"

@app.command(help="Register and configure a new service from a Git repo or Docker image.")
def create(
    service_name: Annotated[str, typer.Argument(help="Unique identifier for the service.")],
    source: Annotated[str, typer.Option("--repo", "--image", help="Git repository URL or Docker image name.", prompt="Source (Repo URL or Image)")],
    host: Annotated[str, typer.Option(help="Public domain name (VIRTUAL_HOST).")] = None,
    port: Annotated[int, typer.Option(help="Internal container port to expose.")] = 80,
    letsencrypt_email: Annotated[str, typer.Option(help="Email for SSL certificate generation.")] = None,
    environment: Annotated[list[str], typer.Option("--env", "-e", help="Environment variables in KEY=VALUE format.")] = [],
    volumes: Annotated[list[str], typer.Option("--volume", "-v", help="Volume mappings in NAME:PATH format.")] = [],
    restart_policy: Annotated[RestartPolicy, typer.Option("--restart", help="Container restart policy.")] = RestartPolicy.unless_stopped,
    gpu: Annotated[bool, typer.Option("--gpu", help="Enable NVIDIA GPU access.")] = False
):
    services_compose = Docker.get_compose(services_compose_path)

    if service_name in services_compose.get("services", {}):
        Output.error(f"Service [b i]{service_name}[/] already exists.")

    service_path = services_path / service_name
    dockerfile_path = service_path / "Dockerfile"

    if Git.is_repo(source):
        Output.info(f"Cloning repository {source}...")
        try:
            Git.clone(source, service_path)
        except:
            Output.error("Failed to clone repository. Check URL and permissions.")
        Output.success("Repository cloned.")
    elif not Docker.is_image(source):
        Output.error("Invalid source. Must be a valid Docker image name or Git repository URL.")

    if any("=" not in env for env in environment): Output.error("Invalid format for --env. Expected [i]KEY=VALUE[/].")
    if any(":" not in volume for volume in volumes): Output.error("Invalid format for --volume. Expected [i]NAME:PATH[/].")
    if any(volume.startswith(("/", ".", "~")) for volume in volumes): Output.error("Host paths are not allowed. Please use named volumes.")

    service_compose = {
        "container_name": service_name,
        **({
            "build": service_path
        } if dockerfile_path.is_file() else {
            "image": f"foundation/{source}" if service_path else source
        }),
        "environment": {
            **dict(env.split("=", 1) for env in environment),
            **({
                "VIRTUAL_HOST": host,
                "VIRTUAL_PORT": port,
                "LETSENCRYPT_HOST": host,
                "LETSENCRYPT_EMAIL": letsencrypt_email
            } if host else {})
        },
        "volumes": volumes,
        "networks": ["foundation_network"],
        "restart": restart_policy.value,
        "deploy": {"resources":{"reservations":{"devices":[{"driver": "nvidia", "count": "all", "capabilities": ["gpu"]}]}}} if gpu else None
    }

    services_compose.setdefault("services", {})[service_name] = service_compose
    services_compose.setdefault("volumes", {}).update({volume.split(":")[0]: {} for volume in volumes})

    Output.info("Saving service configuration...")
    try:
        Docker.update_compose(services_compose_path, services_compose)
    except:
        Output.error("Failed to write to configuration file.")
    Output.success("Configuration saved.")

    update()

    deploy()

    Output.success(f"Service [b i]{service_name}[/] created and deployed.")

@app.command(help="Stop, remove, and delete configuration for a service.")
def delete(name: Annotated[str, typer.Argument(help="Name of the service to delete.")]):
    services_compose = Docker.get_compose(services_compose_path)
    services_compose.get("services", {}).pop(name, None)

    Output.info("Removing service from configuration...")
    try:
        Docker.update_compose(services_compose_path, services_compose)
    except:
        Output.error("Failed to update configuration file.")
    Output.success("Configuration updated.")

    service_path = services_path / name
    shutil.rmtree(service_path, ignore_errors=True)

    update()

    deploy()

    Output.success(f"Service [b i]{name}[/] has been deleted.")

@app.command(help="Run foundation in a continuous loop to check for updates.")
def watch(interval: int = 300):
    Output.info(f"Starting Foundation Watcher. Checking for updates every {interval} seconds...")
    while True:
        try:
            # We use console.log to ensure timestamps in systemd logs
            console.log("Checking for updates...")
            update()
            deploy()
        except typer.Exit:
            pass
        except Exception as e:
            console.log(f"[bold red]Error in watch cycle:[/] {e}")
        
        time.sleep(interval)

if __name__ == "__main__":
    app()