# Foundation

A lightweight CLI for managing Docker services with automatic reverse proxying and SSL termination.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/elliottstorey/foundation/main/install.sh | bash
```

Or build from source:

```bash
uv sync
uv run pyinstaller --onefile src/foundation.py
```

## Usage

**Usage**:

```console
$ foundation [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.

**Commands**:

* `install`: Initialize the Foundation environment and...
* `update`: Update services by pulling latest git...
* `deploy`: Start the foundation core and all defined...
* `status`: List all running services and their status.
* `create`: Create and deploy a new service from a Git...
* `delete`: Stop and remove a service, deleting its...

## `foundation install`

Initialize the Foundation environment and install necessary dependencies.

**Usage**:

```console
$ foundation install [OPTIONS]
```

**Options**:

* `--default-email TEXT`: The email address to use for Let&#x27;s Encrypt SSL certificate registration.
* `--help`: Show this message and exit.

## `foundation update`

Update services by pulling latest git changes and rebuilding images.

**Usage**:

```console
$ foundation update [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

## `foundation deploy`

Start the foundation core and all defined services.

**Usage**:

```console
$ foundation deploy [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

## `foundation status`

List all running services and their status.

**Usage**:

```console
$ foundation status [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

## `foundation create`

Create and deploy a new service from a Git repository or Docker image.

**Usage**:

```console
$ foundation create [OPTIONS] NAME
```

**Arguments**:

* `NAME`: The unique name for the new service.  [required]

**Options**:

* `--repo, --image TEXT`: The source Git repository URL or Docker image name.  [required]
* `--host TEXT`: The hostname/domain where the service will be accessible (VIRTUAL_HOST).
* `--port INTEGER`: The internal port the container listens on.  [default: 80]
* `--letsencrypt-email TEXT`: Specific email for Let&#x27;s Encrypt notifications for this service.
* `-e, --env TEXT`: Environment variables in KEY=VALUE format.
* `-v, --volume TEXT`: Volume mappings in NAME:PATH format.
* `--restart [no|always|on-failure|unless-stopped]`: The restart policy for the container.  [default: unless-stopped]
* `--gpu`: Enable GPU support for this service (requires Nvidia drivers).
* `--help`: Show this message and exit.

## `foundation delete`

Stop and remove a service, deleting its local files.

**Usage**:

```console
$ foundation delete [OPTIONS] NAME
```

**Arguments**:

* `NAME`: The name of the service to delete.  [required]

**Options**:

* `--help`: Show this message and exit.

