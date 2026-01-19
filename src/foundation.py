import json
import shutil
import subprocess
from pathlib import Path
from enum import Enum
from typing import Annotated
import typer
from rich.console import Console
from rich.table import Table

APP_NAME = "foundation"

app_dir = typer.get_app_dir(APP_NAME)

foundation_compose_path = Path(app_dir) / "compose.json"
services_path = Path(app_dir) / "services"
services_compose_path = services_path / "compose.json"

console = Console()

app = typer.Typer(name="foundation", help="A lightweight CLI for managing Docker services with automatic reverse proxying and SSL termination.", no_args_is_help=True)

def get_foundation_compose():
    if not foundation_compose_path.is_file(): return

    result = subprocess.run(["docker", "compose", "-f", foundation_compose_path, "config"])
    if result.returncode != 0: return

    foundation_compose = json.loads(foundation_compose_path.read_text())
    return foundation_compose

def get_services_compose():
    if not services_compose_path.is_file(): return

    result = subprocess.run(["docker", "compose", "-f", services_compose_path, "config"])
    if result.returncode != 0: return

    services_compose = json.loads(services_compose_path.read_text())
    return services_compose

def docker_installed():
    return subprocess.run(["docker", "--version"], capture_output=True).returncode == 0

def docker_running():
    return subprocess.run(["docker", "info"], capture_output=True).returncode == 0

def docker_permissions():
    result = subprocess.run(["docker", "info"], capture_output=True, text=True)
    return result.returncode == 0 or "permission denied" in result.stderr

def git_installed():
    return subprocess.run(["git", "--version"], capture_output=True).returncode == 0

def railpack_installed():
    return subprocess.run(["railpack", "--version"], capture_output=True).returncode == 0

def foundation_installed():
    foundation_compose = get_foundation_compose()
    services_compose = get_services_compose()
    return bool(foundation_compose) and bool(services_compose)

def foundation_running():
    foundation_compose = get_foundation_compose()

    if not foundation_compose: return False

    services = foundation_compose.get("services", {}).keys()

    running_services = {s["Service"] for s in map(json.loads, subprocess.run(["docker", "compose", "-f", foundation_compose_path, "ps", "-a", "--format", "json"], capture_output=True, text=True, check=True).stdout.splitlines()) if s.get("State") == "running"}

    return services.issubset(running_services)

def install_docker():
    with console.status("Installing docker..."):
        subprocess.run(["curl", "-fsSL", "https://get.docker.com", "-o", "get-docker.sh"], check=True)
        subprocess.run(["sh", "get-docker.sh"], check=True)
        Path("get-docker.sh").unlink(missing_ok=True)
    print("Docker installed!")

def install_git():
    with console.status("Installing git..."):
        subprocess.run(["curl", "-fsSL", "https://raw.githubusercontent.com/ElliottStorey/git-install/main/install.sh", "-o", "get-git.sh"], check=True)
        subprocess.run(["sh", "get-git.sh"], check=True)
        Path("get-git.sh").unlink(missing_ok=True)
    print("Git installed!")

def install_railpack():
    with console.status("Installing railpack..."):
        subprocess.run(["curl", "-fsSL", "https://railpack.com/install.sh", "-o", "get-railpack.sh"], check=True)
        subprocess.run(["sh", "get-railpack.sh"], check=True)
        Path("get-railpack.sh").unlink(missing_ok=True)
    print("Railpack installed!")

def check_docker():
    if not docker_running():
        print("Error: Docker is not running. Please start the Docker service and try again.")
        raise typer.Exit(code=1)

    if not docker_permissions():
        print("Error: Permission denied while accessing Docker. Please ensure you have permission to run Docker commands and try again.")
        raise typer.Exit(code=1)

def is_repo(source):
    try:
        subprocess.run(["git", "ls-remote", source], check=True, timeout=10)
        return True
    except:
        return False

def is_image(source):
    try:
        subprocess.run(["docker", "manifest", "inspect", source], check=True, timeout=10)
        return True
    except:
        return False

def build_from_dir(service_path):
    name = service_path.name

    service_dockerfile_path = service_path / "Dockerfile"
    if service_dockerfile_path.is_file():
        with console.status(f"Building image for service '{name}'..."):
            subprocess.run(["docker", "build", "-t", f"foundation/{name}", service_path], capture_output=True, check=True)
        print(f"Built image for service '{name}'.")
        return
            
    with console.status(f"Dockerfile not detected for service '{name}'. Building image using railpack..."):
        result = subprocess.run(["docker", "buildx", "use", "railpack-builder"], capture_output=True)
        if result.returncode != 0:
            subprocess.run(["docker", "buildx", "create", "--name", "railpack-builder", "--driver", "docker-container", "--use"], capture_output=True, check=True)
        subprocess.run(["docker", "buildx", "inspect", "--bootstrap"], capture_output=True, check=True)

        service_railpack_plan_path = service_path / f"{name}-railpack-plan.json"

        subprocess.run(["railpack", "plan", service_path, "-o", service_railpack_plan_path], capture_output=True, check=True)

        subprocess.run(["docker", "buildx", "build", "--build-arg", "BUILDKIT_SYNTAX=ghcr.io/railwayapp/railpack-frontend", "-f", service_railpack_plan_path, "--load", "-t", f"foundation/{name}", service_path], capture_output=True, check=True)

        service_railpack_plan_path.unlink(missing_ok=True)
    print(f"Built image for service '{name}'.")

@app.callback()
def main(ctx: typer.Context):
    if ctx.invoked_subcommand == "install":
        return

    if not docker_installed():
        print("Error: Docker is not initialized. Run `foundation install` to install it.")
        raise typer.Exit(code=1)
    
    check_docker()

    if not git_installed():
        print("Error: Git is not installed. Run `foundation install` to install it.")
        raise typer.Exit(code=1)
    
    if not foundation_installed():
        print("Error: Foundation is not initialized. Run `foundation install` to set it up.")
        raise typer.Exit(code=1)
    
    if ctx.invoked_subcommand == "deploy":
        return

    if not foundation_running():
        print("Error: Foundation is not running. Run `foundation deploy` to make sure it is up.")
        raise typer.Exit(code=1)

@app.command(help="Initialize the Foundation environment and install necessary dependencies.")
def install(default_email: Annotated[str, typer.Option(help="The email address to use for Let's Encrypt SSL certificate registration.")] = None):
    services_compose = get_services_compose()

    if not services_compose: services_compose = {}

    services = services_compose.get("services", {})
    volumes = services_compose.get("volumes", {})

    if not docker_installed(): install_docker()
    if not git_installed(): install_git()
    if not railpack_installed(): install_railpack()

    with console.status("Installing foundation..."):
        foundation_compose = {
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
                    "environment": [f"DEFAULT_EMAIL={default_email}"],
                    "volumes": ["acme:/etc/acme.sh"],
                    "volumes_from": ["nginx-proxy"],
                    "networks": ["foundation_network"],
                    "restart": "unless-stopped"
                }
            },
            "volumes": {
                "certs": {},
                "html": {},
                "acme": {}
            },
            "networks": {
                "foundation_network": {}
            }
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

        foundation_compose_path.parent.mkdir(parents=True, exist_ok=True)
        foundation_compose_path.write_text(json.dumps(foundation_compose, indent=2), encoding="utf-8")
        services_compose_path.parent.mkdir(parents=True, exist_ok=True)
        services_compose_path.write_text(json.dumps(services_compose, indent=2), encoding="utf-8")
    print("Installed foundation. Run `foundation create` to create a new service.")
    
    deploy()

@app.command(help="Update services by pulling latest git changes and rebuilding images.", hidden=True)
def update():
    for service_path in services_path.iterdir():
        if not service_path.is_dir(): continue

        service_git_path = service_path / ".git"
        if not service_git_path.is_dir(): continue

        name = service_path.name

        with console.status(f"Checking service '{name}' for changes..."):
            subprocess.run(["git", "fetch"], cwd=service_path, capture_output=True, check=True)
            local_hash = subprocess.run(["git", "rev-parse", "HEAD"], cwd=service_path, capture_output=True, text=True, check=True).stdout.strip()
            upstream_hash = subprocess.run(["git", "rev-parse", "@{u}"], cwd=service_path, capture_output=True, text=True, check=True).stdout.strip()

        if local_hash != upstream_hash:
            with console.status(f"Changes detected for service '{name}'. Pulling changes..."):
                # subprocess.run(["git", "pull"], cwd=service_path, check=True)
                subprocess.run(["git", "reset", "--hard", "@{u}"], cwd=service_path, capture_output=True, check=True)
            print(f"Pulled changes for service '{name}'.")

            build_from_dir(service_path)
    
    with console.status("Pulling registry images..."):
        subprocess.run(["docker", "compose", "-f", services_compose_path, "pull"], capture_output=True, check=True)
    print("Pulled all registry images.")

    with console.status("Building registry images..."):
        subprocess.run(["docker", "compose", "-f", services_compose_path, "build"], capture_output=True, check=True)
    print("Built all registry images.")

    print("All changes have been pulled. Run `foundation deploy` to deploy them.")

@app.command(help="Start the foundation core and all defined services.", hidden=True)
def deploy():
    services_compose = get_services_compose()

    with console.status("Ensuring foundation is running..."):
        subprocess.run(["docker", "compose", "-f", foundation_compose_path, "up", "-d"], capture_output=True, check=True)
    print("Foundation is deployed.")

    if not services_compose.get("services"):
        print("You have no defined services. Run `foundation create` to create a new service.")
        raise typer.Exit()

    with console.status("Deploying all services..."):
        subprocess.run(["docker", "compose", "-f", services_compose_path, "up", "-d", "--remove-orphans"], capture_output=True, check=True)
    print("Deployed all services.")

@app.command(help="List all running services and their status.")
def status():
    services_compose = get_services_compose()

    services = services_compose.get("services", {})
    names = services.keys()

    if not len(services):
        print("You have no defined services. Run `foundation create` to create a service.")
        raise typer.Exit()

    table = Table(title="Services", caption=f"{len(services)} defined services")
    table.add_column("Name")
    table.add_column("Created")
    table.add_column("Status")
    table.add_column("Domain")

    for name in names:
        created_at = "Not Created"
        status = "[red]Down[/red]"
        host = "Not Defined"

        result = subprocess.run(["docker", "compose", "ps", "-a", name, "--format", "json"], capture_output=True, text=True)
        if result.stdout.strip():
            container_info = json.loads(result.stdout.splitlines()[0])
            created_at = container_info.get("CreatedAt", "Unknown")
            status = container_info.get("State", "Unknown")
            if (status.lower() != "running"): status = f"[red]{status}[/red]"
        
        environment_variables = services[name].get("environment", [])
        host_env = next((env for env in environment_variables if env.startswith("VIRTUAL_HOST=")), None)
        if (host_env): host = host_env.split("=", 1)[1]

        table.add_row(name, created_at, status, host)

    console.print(table)

class RestartPolicy(str, Enum):
    no = "no"
    always = "always"
    on_failure = "on-failure"
    unless_stopped = "unless-stopped"

@app.command(help="Create and deploy a new service from a Git repository or Docker image.")
def create(
    name: Annotated[str, typer.Argument(help="The unique name for the new service.")],
    source: Annotated[str, typer.Option("--repo", "--image", help="The source Git repository URL or Docker image name.", prompt=True)],
    host: Annotated[str, typer.Option(help="The hostname/domain where the service will be accessible (VIRTUAL_HOST).")] = None,
    port: Annotated[int, typer.Option(help="The internal port the container listens on.")] = 80,
    letsencrypt_email: Annotated[str, typer.Option(help="Specific email for Let's Encrypt notifications for this service.")] = None,
    environment: Annotated[list[str], typer.Option("--env", "-e", help="Environment variables in KEY=VALUE format.")] = [],
    volumes: Annotated[list[str], typer.Option("--volume", "-v", help="Volume mappings in NAME:PATH format.")] = [],
    restart_policy: Annotated[RestartPolicy, typer.Option("--restart", help="The restart policy for the container.")] = RestartPolicy.unless_stopped,
    gpu: Annotated[bool, typer.Option("--gpu", help="Enable GPU support for this service (requires Nvidia drivers).")] = False
):
    service_path = services_path / name
    services_compose = get_services_compose()

    if name in services_compose.get("services", {}):
        print(f"Error: service '{name}' already exists. Use `foundation delete` to remove it first.")
        raise typer.Exit(1)
    
    for volume in volumes:
        name, path = volume.split(":", 1)

        if name.startswith(("/", ".", "~")):
            print("Error: Volume name must not be a path.")
            raise typer.Exit(1)
        
        services_compose["volumes"][name] = {}

    service_compose = {
        "container_name": name,
        "image": None,
        "environment": environment,
        "volumes": volumes,
        "networks": ["foundation_network"],
        "restart": restart_policy.value
    }

    if host:
        service_compose["environment"].append(f"VIRTUAL_HOST={host}")
        service_compose["environment"].append(f"VIRTUAL_PORT={port}")
        service_compose["environment"].append(f"LETSENCRYPT_HOST={host}")
        if letsencrypt_email: service_compose["environment"].append(f"LETSENCRYPT_EMAIL={letsencrypt_email}")

    if gpu:
        service_compose["deploy"] = {
            "resources": {
                "reservations":{
                    "devices": [
                        {
                            "driver": "nvidia",
                            "count": "all",
                            "capabilities": ["gpu"]
                        }
                    ]
                }
            }
        }

    if is_repo(source):
        service_compose["image"] = f"foundation/{name}"
        with console.status(f"Cloning source '{source}'..."):
            subprocess.run(["git", "clone", source, service_path], capture_output=True, check=True)
        print(f"Cloned source '{source}'.")
        build_from_dir(service_path)
    elif is_image(source):
        service_compose["image"] = source
    else:
        print(f"Error: the given source '{source}' is not a valid git repo or docker image.")
        raise typer.Exit(code=1)

    services_compose["services"][name] = service_compose

    services_compose_path.write_text(json.dumps(services_compose, indent=2), encoding="utf-8")

    deploy()

    print(f"Service '{name}' successfully created.")

@app.command(help="Stop and remove a service, deleting its local files.")
def delete(name: Annotated[str, typer.Argument(help="The name of the service to delete.")]):
    service_path = services_path / name
    services_compose = get_services_compose()

    if not name in services_compose.get("services", {}):
        print(f"Error: service '{name}' not found.")
        raise typer.Exit(code=1)

    with console.status(f"Deleting service '{name}'..."):
        del services_compose.get("services", {})[name]
        services_compose_path.write_text(json.dumps(services_compose, indent=2), encoding="utf-8")
    print(f"Deleted service '{name}'.")

    deploy()

    with console.status(f"Cleaning up files for service '{name}'..."):
        if service_path.exists():
            shutil.rmtree(service_path)
    print(f"Cleaned up files for service '{name}'.")

    print(f"Service '{name}' successfully deleted.")

if __name__ == "__main__":
    app()