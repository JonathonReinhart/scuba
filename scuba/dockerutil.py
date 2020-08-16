import subprocess
import errno
import json

class DockerError(Exception):
    pass

class DockerExecuteError(DockerError):
    pass

class NoSuchImageError(DockerError):
    def __init__(self, image):
        self.image = image

    def __str__(self):
        return 'No such image: {}'.format(self.image)


def __wrap_docker_exec(func):
    '''Wrap a function to raise DockerExecuteError on ENOENT'''
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except FileNotFoundError:
            raise DockerExecuteError('Failed to execute docker. Is it installed?')
    return wrapper

call = __wrap_docker_exec(subprocess.call)


def _run_docker(*args, capture=False):
    '''Run docker and raise DockerExecuteError on ENOENT'''
    args = ['docker'] + list(args)
    kw = dict(
            universal_newlines=True,    # TODO: Use 'text' in Python 3.7+
            )
    if capture:
        kw.update(
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                )

    return __wrap_docker_exec(subprocess.run)(args, **kw)


def docker_inspect(image):
    '''Inspects a docker image

    Returns: Parsed JSON data
    '''
    cp = _run_docker('inspect', '--type', 'image', image, capture=True)

    if not cp.returncode == 0:
        if 'no such image' in cp.stderr.lower():
            raise NoSuchImageError(image)
        raise DockerError('Failed to inspect image: {}'.format(cp.stderr.strip()))

    return json.loads(cp.stdout)[0]

def docker_pull(image):
    '''Pulls an image'''
    # If this fails, the default docker stdout/stderr looks good to the user.
    cp = _run_docker('pull', image)
    if cp.returncode != 0:
        raise DockerError('Failed to pull image "{}"'.format(image))

def docker_inspect_or_pull(image):
    '''Inspects a docker image, pulling it if it doesn't exist'''
    try:
        return docker_inspect(image)
    except NoSuchImageError:
        # If it doesn't exist yet, try to pull it now (#79)
        docker_pull(image)
        return docker_inspect(image)


def get_images():
    '''Get the current list of docker images

    Returns: List of image names
    '''
    cp = _run_docker('images',
        # This format ouputs the same thing as '__docker_images --repo --tag'
        '--format', (
            # Always show the bare repository name
            r'{{.Repository}}'
            # And if there is a tag, show that too
            r'{{if ne .Tag "<none>"}}\n{{.Repository}}:{{.Tag}}{{end}}'
        ),
        capture=True,
    )

    if not cp.returncode == 0:
        raise DockerError('Failed to retrieve images: {}'.format(cp.stderr.strip()))

    return cp.stdout.splitlines()


def get_image_command(image):
    '''Gets the default command for an image'''
    info = docker_inspect_or_pull(image)
    try:
        return info['Config']['Cmd']
    except KeyError as ke:
        raise DockerError('Failed to inspect image: JSON result missing key {}'.format(ke))

def get_image_entrypoint(image):
    '''Gets the image entrypoint'''
    info = docker_inspect_or_pull(image)
    try:
        return info['Config']['Entrypoint']
    except KeyError as ke:
        raise DockerError('Failed to inspect image: JSON result missing key {}'.format(ke))


def make_vol_opt(hostdir, contdir, options=None):
    '''Generate a docker volume option'''
    vol = '--volume={}:{}'.format(hostdir, contdir)
    if options != None:
        if isinstance(options, str):
            options = (options,)
        vol += ':' + ','.join(options)
    return vol

