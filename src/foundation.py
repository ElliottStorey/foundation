import json
import shutil
import subprocess
import socket
from pathlib import Path
from enum import Enum
from typing import Annotated
import typer
from rich.console import Console
from rich.table import Table

APP_NAME = "foundation"
APP_DIR = typer.get_app_dir(APP_NAME)
PROXY_PATH = Path(APP_DIR) / "compose.json"
SERVICES_DIR = Path(APP_DIR) / "services"
SERVICES_PATH = SERVICES_DIR / "compose.json"

class Docker:
    @staticmethod
    def installed():
        try:
            subprocess.run(["docker", "--version"], capture_output=True, check=True)
            return True
        except Exception:
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
        except Exception:
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
            subprocess.run(["docker", "manifest", "inspect", source], capture_output=True, check=True, timeout=20)
            return True
        except Exception as e:
            return False
        
    @staticmethod
    def get_compose(compose_path):
        result = subprocess.run(["docker", "compose", "--file", compose_path, "config", "--format", "json"], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    
    @staticmethod
    def get_compose_status(compose_path):
        compose = Docker.get_compose(compose_path)
        services = compose.get("services", {})

        result = subprocess.run(["docker", "compose", "--file", compose_path, "ps", "--all", "--format", "{{json .}}"], capture_output=True, text=True, check=True)

        services_status = [json.loads(line) for line in result.stdout.strip().split("\n") if line]
        
        services_status = {service_status.get("Service"): service_status for service_status in services_status}

        return {
            service_name: {
                "state": services_status.get(service_name, {}).get("State"),
                "status": services_status.get(service_name, {}).get("Status"),
                "created_at": services_status.get(service_name, {}).get("CreatedAt")
            } for service_name in services
        }
    
    @staticmethod
    def write_compose(compose_path, compose):
        compose = json.dumps(compose, indent=2)
        subprocess.run(["docker", "compose", "--file", "-", "config"], input=compose, capture_output=True, text=True, check=True)
        compose_path.parent.mkdir(parents=True, exist_ok=True)
        compose_path.write_text(compose, encoding="utf-8")

    @staticmethod
    def build(tag, service_dir):
        subprocess.run(["docker", "build", "--tag", tag, service_dir], capture_output=True, check=True)

    @staticmethod
    def build_from_railpack_plan(tag, service_dir, railpack_plan_path):
        if subprocess.run(["docker", "buildx", "inspect", "railpack-builder"], capture_output=True).returncode == 0:
            subprocess.run(["docker", "buildx", "use", "railpack-builder"], capture_output=True, check=True)
        else:
            subprocess.run(["docker", "buildx", "create", "--name", "railpack-builder", "--driver", "docker-container", "--use", "--bootstrap"], capture_output=True, check=True)

        subprocess.run([
            "docker", "buildx", "build",
            "--build-arg", "BUILDKIT_SYNTAX=ghcr.io/railwayapp/railpack-frontend",
            "--tag", tag,
            "--file", railpack_plan_path,
            service_dir,
            "--load"
        ], capture_output=True, check=True)

    def compose_build(compose_path, service_name=None):
        subprocess.run(list(filter(None, ["docker", "compose", "-f", compose_path, "build", service_name])), capture_output=True, check=True)
    
    def compose_pull(compose_path, service_name=None):
        subprocess.run(list(filter(None, ["docker", "compose", "-f", compose_path, "pull", service_name])), capture_output=True, check=True)

    def compose_up(compose_path, service_name=None):
        subprocess.run(list(filter(None, ["docker", "compose", "-f", compose_path, "up", service_name, "--detach", "--remove-orphans"])), capture_output=True, check=True)

class Git:
    @staticmethod
    def installed():
        try:
            subprocess.run(["git", "--version"], capture_output=True, check=True)
            return True
        except Exception:
            return False
    
    @staticmethod
    def install():
        try:
            subprocess.run(["curl", "-fsSL", "https://raw.githubusercontent.com/ElliottStorey/git-install/main/install.sh", "-o", "get-git.sh"], capture_output=True, check=True)
            subprocess.run(["sh", "get-git.sh"], capture_output=True, check=True)
        finally:    
            Path("get-git.sh").unlink(missing_ok=True)

    @staticmethod
    def is_url(source):
        return source.startswith(("http://", "https://", "git@", "ssh://"))

    @staticmethod
    def is_repo(source):
        try:
            subprocess.run(["git", "ls-remote", source], capture_output=True, check=True, timeout=10)
            return True
        except Exception:
            return False

    @staticmethod
    def clone(source, service_dir):
        service_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", source, "."], cwd=service_dir, capture_output=True, check=True)

    @staticmethod
    def reset(service_dir):
        subprocess.run(["git", "fetch"], cwd=service_dir, capture_output=True, check=True)
        result = subprocess.run(["git", "rev-list", "--count", "HEAD..@{u}"], cwd=service_dir, capture_output=True, text=True, check=True)
        if int(result.stdout.strip()) > 0:
            subprocess.run(["git", "reset", "--hard", "@{u}"], cwd=service_dir)

class Railpack:
    @staticmethod
    def installed():
        try:
            subprocess.run(["railpack", "--version"], capture_output=True, check=True)
            return True
        except Exception:
            return False

    @staticmethod
    def install():
        try:
            subprocess.run(["curl", "-fsSL", "https://railpack.com/install.sh", "-o", "get-railpack.sh"], capture_output=True, check=True)
            subprocess.run(["sh", "get-railpack.sh"], capture_output=True, check=True)
        finally:    
            Path("get-railpack.sh").unlink(missing_ok=True)
    
    @staticmethod
    def prepare(service_dir, plan_out):
        subprocess.run(["railpack", "prepare", service_dir, "--plan-out", plan_out], capture_output=True, check=True)

app = typer.Typer(
    name="foundation",
    help="CLI tool for managing Docker services with automatic reverse proxying and SSL termination.",
    no_args_is_help=True
)

console = Console()

class Output:
    @staticmethod
    def info(message, next_message=None, next_command=None, exit=False):
        console.print(f"{message}.")
        if next_command and next_message:
            console.print(f"Try running [bold cyan]{APP_NAME} {next_command}[/] to {next_message}.")
        elif next_message:
            console.print(f"Try to {next_message}.")
        if exit: raise typer.Exit()

    @staticmethod
    def success(message, next_message=None, next_command=None, exit=False):
        console.print(f"[bold green]Success:[/] {message}.")
        if next_command and next_message:
            console.print(f"Try running [bold cyan]{APP_NAME} {next_command}[/] to {next_message}.")
        elif next_message:
            console.print(f"Try to {next_message}.")
        if exit: raise typer.Exit()

    @staticmethod
    def error(message, next_message=None, next_command=None, exception=None, exit=True):
        console.quiet = False

        if isinstance(exception, subprocess.CalledProcessError):
            if exception.stderr:
                console.print(f"[red]{exception.stderr.decode().strip()}[/]")
            elif exception.stdout:
                console.print(f"[red]{exception.stdout.decode().strip()}[/]")
        elif exception:
            console.print_exception(show_locals=True)

        console.print(f"[bold red]Error:[/] {message}.")
        if next_command and next_message:
            console.print(f"Try running [bold cyan]{APP_NAME} {next_command}[/] to {next_message}.")
        elif next_message:
            console.print(f"Try to {next_message}.")\

        if exit:
            raise typer.Exit(code=1)

def port_available(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("0.0.0.0", port)) != 0

@app.callback()
def main(ctx: typer.Context):
    if ctx.invoked_subcommand in [None, "init"]: return

    if not Docker.installed():
        Output.error("Docker is not installed", "install all dependencies", "init")
    
    if not Docker.running():
        Output.error("Docker is not running", "start Docker")
    
    if not Docker.permissions():
        Output.error("Docker permission denied", "re-running with sudo")

    if not Git.installed():
        Output.error("Git is not installed", "install all dependencies", "init")
    
    if not Railpack.installed():
        Output.error("Railpack is not installed", "install all dependencies", "init")

    if not PROXY_PATH.is_file() or not SERVICES_PATH.is_file():
        Output.error("Foundation is not initialised", "setup the environment", "init")

    try:
        Docker.get_compose(PROXY_PATH)
        Docker.get_compose(SERVICES_PATH)
    except Exception:
        Output.error("Configuration files are corrupted", "restore the environment", "init")

    if ctx.invoked_subcommand == "deploy": return

    try:
        proxy_status = Docker.get_compose_status(PROXY_PATH)
        if not all(s["state"] == "running" for s in proxy_status.values()): raise
    except Exception:
        Output.error("Reverse proxy is not running", "restart it", "deploy")

@app.command(help="Install all dependencies and start the reverse proxy.")
def init(
    default_email: Annotated[str, typer.Option(help="Default email address used for Let's Encrypt SSL registration.", prompt="Default email address for Let's Encrypt SSL registration")]
):
    if not Docker.installed():
        with console.status("Installing Docker..."):
            try:
                Docker.install()
                Output.success("Docker installed!")
            except Exception as e:
                Output.error("Could not install Docker", "re-run or try again", exception=e)

    if not Git.installed():
        with console.status("Installing Git..."):
            try:
                Git.install()
                Output.success("Git installed!")
            except Exception as e:
                Output.error("Could not install Git", "re-run or try again", exception=e)
    
    if not Railpack.installed():
        with console.status("Installing Railpack..."):
            try:
                Railpack.install()
                Output.success("Railpack installed!")
            except Exception as e:
                Output.error("Could not install Railpack", "re-run or try again", exception=e)
 
    try:
        services_compose = Docker.get_compose(SERVICES_PATH)
        services = services_compose.get("services", {})
        volumes = services_compose.get("volumes", {})
        Output.info("Using existing configuration files")
    except Exception:
        services = {}
        volumes = {}

    proxy_compose = {
        "name": "foundation-proxy",
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
        "name": "foundation-services",
        "services": services,
        "volumes": volumes,
        "networks": {
            "foundation_network": {
                "external": True,
                "name": "foundation_network"
            }
        }
    }

    with console.status("Updating configuration files..."):
        try:
            Docker.write_compose(PROXY_PATH, proxy_compose)
            Docker.write_compose(SERVICES_PATH, services_compose)
            Output.success("Updated configuration files!")
        except Exception as e:
            Output.error("Could not update configuration files", exception=e)

    with console.status("Deploying changes..."):
        try:
            deploy(quiet=True)
            Output.success("foundation initialised", "create your first service", "create")
        except Exception as e:
            Output.error("Could not deploy proxy", "check the logs", "deploy", exception=e)

@app.command(help="View the status, uptime, and URLs of all services.")
def status():
    services_compose = Docker.get_compose(SERVICES_PATH)
    services_status = Docker.get_compose_status(SERVICES_PATH)

    if not services_status:
        Output.info("No services defined", "add a service", "create", exit=True)

    table = Table(title="Services")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Uptime")
    table.add_column("Domain")

    for service_name, service_status in services_status.items():
        status = service_status.get("status", "-")
        uptime = service_status.get("state", "-")
        host = services_compose.get("services", {}).get(service_name, {}).get("environment", {}).get("VIRTUAL_HOST", "-")
        table.add_row(service_name, status, uptime, host)

    console.print(table)

def environment_callback(value):
    if any("=" not in env for env in value):
        raise typer.BadParameter("Must be in KEY=VALUE format")
    return value

def volumes_callback(value):
    if any(":" not in volume for volume in value):
        raise typer.BadParameter("Must be in VOLUME:PATH format")
    if any(volume.startswith(("/", ".", "~")) for volume in value):
        raise typer.BadParameter("Must use named volumes")
    return value

class RestartPolicy(str, Enum):
    no = "no"
    always = "always"
    on_failure = "on-failure"
    unless_stopped = "unless-stopped"

@app.command(help="Add a new service from a Git repo or Docker image.")
def create(
    name: Annotated[str, typer.Argument(help="Name of the service to create.")],
    source: Annotated[str, typer.Option("--repo", "--image", help="Git repository or Docker image.", prompt="Git repository or Docker image")],
    virtual_host: Annotated[str, typer.Option("--domain", help="The public domain name to proxy to this service.")] = None,
    virtual_port: Annotated[int, typer.Option("--internal-port", help="The internal container port to be proxied.")] = None,
    letsencrypt_email: Annotated[str, typer.Option("--email", help="Email address used for Let's Encrypt SSL registration.")] = None,
    environment: Annotated[list[str], typer.Option("--env", "-e", metavar="KEY=VALUE", help="Environment variables to pass into the service container.", callback=environment_callback)] = [],
    volumes: Annotated[list[str], typer.Option("--volume", "-v", metavar="VOLUME:PATH", help="Volume mappings to pass into the service container.", callback=volumes_callback)] = [],
    restart_policy: Annotated[RestartPolicy, typer.Option("--restart", help="Restart policy for the service.")] = RestartPolicy.unless_stopped,
    gpu: Annotated[bool, typer.Option("--gpu", help="Enable NVIDIA GPU access for the service container.")] = False
):
    service_name = name
    services_compose = Docker.get_compose(SERVICES_PATH)
    services = services_compose.get("services", {})

    if service_name in services:
        Output.error(f"Service [bold italic]{service_name}[/] already exists", "delete it first", f"delete {service_name}")

    service_dir = SERVICES_DIR / service_name
    dockerfile_path = service_dir / "Dockerfile"

    if Git.is_url(source):
        with console.status("Cloning repository..."):
            try:
                Git.clone(source, service_dir)
                Output.success("Repository cloned")
            except Exception as e:
                Output.error("Could not clone repository", "Check URL, network, and permissions", exception=e)

    service_compose = {
        "container_name": service_name,
        **({
            "build": service_dir
        } if dockerfile_path.is_file() else {
            "image": f"foundation/{service_name}" if service_dir.is_dir() else source
        }),
        "environment": {
            **dict(env.split("=", 1) for env in environment),
            **({
                **({ "VIRTUAL_HOST": virtual_host } if virtual_host else {}),
                **({ "VIRTUAL_PORT": virtual_port } if virtual_host else {}),
                **({ "LETSENCRYPT_HOST": virtual_host } if virtual_host else {}),
                **({ "LETSENCRYPT_EMAIL": letsencrypt_email } if letsencrypt_email else {})
            } if virtual_host else {})
        },
        "volumes": volumes,
        "networks": ["foundation_network"],
        "restart": restart_policy.value,
        **({
            "deploy": {"resources":{"reservations":{"devices":[{"driver": "nvidia", "count": "all", "capabilities": ["gpu"]}]}}}
        } if gpu else {})
    }

    services_compose.setdefault("services", {})[service_name] = service_compose
    services_compose.setdefault("volumes", {}).update({ volume.split(":")[0]: {} for volume in volumes })

    with console.status("Updating configuration files..."):
        try:
            Docker.write_compose(SERVICES_PATH, services_compose)
            Output.success("Updated configuration files!")
        except Exception as e:
            Output.error("Could not update configuration files", exception=e)

    with console.status("Deploying changes..."):
        try:
            deploy(quiet=True)
            Output.success(f"Service [bold italic]{service_name}[/] created", "view its status", "status")
        except Exception as e:
            Output.error("Could not deploy changes", "check the logs", f"deploy {service_name}", exception=e)

@app.command(help="Permanently remove a service and its configuration.")
def delete(
    name: Annotated[str, typer.Argument(help="Name of the service to delete.")]
):
    service_name = name
    services_compose = Docker.get_compose(SERVICES_PATH)
    services = services_compose.get("services", {})
    service_dir = SERVICES_DIR / service_name

    if service_name not in services:
        Output.success(f"Service [bold italic]{service_name}[/] is not defined", "create it first", f"create {service_name}", exit=True)

    services.pop(service_name, None)

    services_compose["services"] = services

    with console.status("Updating configuration files..."):
        try:
            Docker.write_compose(SERVICES_PATH, services_compose)
            Output.success("Updated configuration files!")
        except Exception as e:
            Output.error("Could not update configuration files", exception=e)

    with console.status("Cleaning up files..."):
        try:
            shutil.rmtree(service_dir, ignore_errors=True)
            Output.success("Cleaned up files")
        except Exception as e:
            Output.error("Could not clean up files", exception=e)

    with console.status("Deploying changes..."):
        try:
            deploy(quiet=True)
            Output.success(f"Service [bold italic]{service_name}[/] deleted", "view remaining services", "status")
        except Exception as e:
            Output.error("Could not deploy changes", "check the logs", "deploy", exception=e)

@app.command(help="Build and start services. Use this to apply changes.")
def deploy(
    name: Annotated[str, typer.Argument(help="Name of the service to deploy.")] = None,
    quiet: Annotated[bool, typer.Option("--quiet", help="Do not show logs while deploying.")] = False
):
    services_compose = Docker.get_compose(SERVICES_PATH)
    services = services_compose.get("services", {})

    if name:
        if name not in services:
            Output.error(f"Service [bold italic]{name}[/] is not defined", "create it first", f"create {name}")
        services = { name: services[name] }

    original_quiet = console.quiet
    console.quiet = quiet

    try:
        for service_name, service in services.items():
            if name and service_name != name: continue

            service_dir = SERVICES_DIR / service_name
            build = service.get("build")
            image = service.get("image", "")

            if build or image == f"foundation/{service_name}":
                with console.status(f"Updating repository for service [bold italic]{service_name}[/]..."):
                    try:
                        Git.reset(service_dir)
                        Output.success(f"Updated repository for service [bold italic]{service_name}[/]")
                    except Exception as e:
                        Output.error(f"Could not update repository for service [bold italic]{service_name}[/]", "check remote access and permissions", exception=e)

            if build:
                with console.status(f"Building service [bold italic]{service_name}[/] from Dockerfile..."):
                    try:
                        Docker.compose_build(SERVICES_PATH, service_name)
                        Output.success(f"Built service [bold italic]{service_name}[/]")
                    except Exception as e:
                        Output.error(f"Could not build service [bold italic]{service_name}[/]", "make sure that the Dockerfile is valid", exception=e)
            elif image == f"foundation/{service_name}":
                with console.status(f"Building service [bold italic]{service_name}[/] from source..."):
                    try:
                        railpack_plan_path = service_dir / "railpack-plan.json"
                        Railpack.prepare(service_dir, railpack_plan_path)
                        Docker.build_from_railpack_plan(f"foundation/{service_name}", service_dir, railpack_plan_path)
                        Output.success(f"Built service [bold italic]{service_name}[/]")
                    except Exception as e:
                        Output.error(f"Could not build service [bold italic]{service_name}[/]", exception=e)
            else:
                with console.status(f"Pulling service [bold italic]{service_name}[/]..."):
                    try:
                        Docker.compose_pull(SERVICES_PATH, service_name)
                        Output.success(f"Pulled service [bold italic]{service_name}[/]")
                    except Exception as e:
                        Output.error(f"Could not pull service [bold italic]{service_name}[/]", "make sure that the image is valid", exception=e)

        with console.status("Starting reverse proxy..."):
            try:
                Docker.compose_up(PROXY_PATH)
                Output.success("Started the reverse proxy")
            except Exception as e:
                Output.error("Could not start reverse proxy", exception=e)
        
        if services:
            with console.status("Starting services..."):
                try:
                    Docker.compose_up(SERVICES_PATH)
                    Output.success("Deployment complete", "view running services", "status")
                except Exception as e:
                    Output.error("Could not start services", exception=e)
    finally:
        console.quiet = original_quiet

if __name__ == "__main__":
    app()