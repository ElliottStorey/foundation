# Foundation

CLI tool for managing Docker services with automatic reverse proxying and SSL termination.

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

```console
$ foundation [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.

**Commands**:

* `init`: Install all dependencies and start the...
* `status`: View the status, uptime, and URLs of all...
* `create`: Add a new service from a Git repo or...
* `delete`: Permanently remove a service and its...
* `deploy`: Build and start services.

## `foundation init`

Install all dependencies and start the reverse proxy.

**Usage**:

```console
$ foundation init [OPTIONS]
```

**Options**:

* `--default-email TEXT`: Default email address used for Let&#x27;s Encrypt SSL registration.  [required]
* `--help`: Show this message and exit.

## `foundation status`

View the status, uptime, and URLs of all services.

**Usage**:

```console
$ foundation status [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

## `foundation create`

Add a new service from a Git repo or Docker image.

**Usage**:

```console
$ foundation create [OPTIONS] NAME
```

**Arguments**:

* `NAME`: Name of the service to create.  [required]

**Options**:

* `--repo, --image TEXT`: Git repository or Docker image.  [required]
* `--domain TEXT`: The public domain name to proxy to this service.
* `--internal-port INTEGER`: The internal container port to be proxied.
* `--email TEXT`: Email address used for Let&#x27;s Encrypt SSL registration.
* `-e, --env KEY=VALUE`: Environment variables to pass into the service container.
* `-v, --volume VOLUME:PATH`: Volume mappings to pass into the service container.
* `--restart [no|always|on-failure|unless-stopped]`: Restart policy for the service.  [default: unless-stopped]
* `--gpu`: Enable NVIDIA GPU access for the service container.
* `--help`: Show this message and exit.

## `foundation delete`

Permanently remove a service and its configuration.

**Usage**:

```console
$ foundation delete [OPTIONS] NAME
```

**Arguments**:

* `NAME`: Name of the service to delete.  [required]

**Options**:

* `--help`: Show this message and exit.

## `foundation deploy`

Build and start services. Use this to apply changes.

**Usage**:

```console
$ foundation deploy [OPTIONS] [NAME]
```

**Arguments**:

* `[NAME]`: Name of the service to deploy.

**Options**:

* `--quiet`: Do not show logs while deploying.
* `--help`: Show this message and exit.

