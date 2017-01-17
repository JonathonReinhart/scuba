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
        return 'No such image: {0}'.format(self.image)


def __wrap_docker_exec(func):
    '''Wrap a function to raise DockerExecuteError on ENOENT'''
    def call(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except OSError as e:
            if e.errno == errno.ENOENT:
                raise DockerExecuteError('Failed to execute docker. Is it installed?')
            raise
    return call

Popen = __wrap_docker_exec(subprocess.Popen)
call  = __wrap_docker_exec(subprocess.call)


def docker_inspect(image):
    '''Inspects a docker image

    Returns: Parsed JSON data
    '''
    args = ['docker', 'inspect', '--type', 'image', image]
    p = Popen(args, stdout = subprocess.PIPE, stderr = subprocess.PIPE)

    stdout, stderr = p.communicate()
    stdout = stdout.decode('utf-8')
    stderr = stderr.decode('utf-8')

    if not p.returncode == 0:
        if 'no such image' in stderr.lower():
            raise NoSuchImageError(image)
        raise DockerError('Failed to inspect image: {0}'.format(stderr.strip()))

    return json.loads(stdout)[0]

def docker_pull(image):
    '''Pulls an image'''
    args = ['docker', 'pull', image]

    # If this fails, the default docker stdout/stderr looks good to the user.
    ret = call(args)
    if ret != 0:
        raise DockerError('Failed to pull image "{0}"'.format(image))

def docker_inspect_or_pull(image):
    '''Inspects a docker image, pulling it if it doesn't exist'''
    try:
        return docker_inspect(image)
    except NoSuchImageError:
        # If it doesn't exist yet, try to pull it now (#79)
        docker_pull(image)
        return docker_inspect(image)

def get_image_command(image):
    '''Gets the default command for an image'''
    info = docker_inspect_or_pull(image)
    try:
        return info['Config']['Cmd']
    except KeyError as ke:
        raise DockerError('Failed to inspect image: JSON result missing key {0}'.format(ke))

def get_image_entrypoint(image):
    '''Gets the image entrypoint'''
    info = docker_inspect_or_pull(image)
    try:
        return info['Config']['Entrypoint']
    except KeyError as ke:
        raise DockerError('Failed to inspect image: JSON result missing key {0}'.format(ke))


def make_vol_opt(hostdir, contdir, options=None):
    '''Generate a docker volume option'''
    vol = '--volume={0}:{1}'.format(hostdir, contdir)
    if options != None:
        if isinstance(options, str):
            options = (options,)
        vol += ':' + ','.join(options)
    return vol

