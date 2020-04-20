import subprocess
import errno
import json
import re

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
        raise DockerError('Failed to inspect image: {}'.format(stderr.strip()))

    return json.loads(stdout)[0]

def docker_pull(image):
    '''Pulls an image'''
    args = ['docker', 'pull', image]

    # If this fails, the default docker stdout/stderr looks good to the user.
    ret = call(args)
    if ret != 0:
        raise DockerError('Failed to pull image "{}"'.format(image))

def docker_inspect_or_pull(image):
    '''Inspects a docker image, pulling it if it doesn't exist'''
    try:
        return docker_inspect(image)
    except NoSuchImageError:
        # If it doesn't exist yet, try to pull it now (#79)
        docker_pull(image)
        return docker_inspect(image)


def get_images(get_all=False):
    '''Get the current list of docker images

    Returns: List of image names
    '''

    args = ['docker', 'images']
    if get_all:
        args.append('-a')
    p = Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    stdout, stderr = p.communicate()
    stdout = stdout.decode('utf-8')
    stderr = stderr.decode('utf-8')

    if not p.returncode == 0:
        raise DockerError('Failed to retrieve images: {}'.format(stderr.strip()))

    images = []
    skip_header = True
    pat = re.compile('^(?P<image>[^\s]+)\s+(?P<tag>[^\s]+)\s+(?P<id>[0-9a-f]+)\s+')
    for line in stdout.split('\n'):
        if skip_header:
            skip_header = False
            continue

        if not line:
            continue

        m = pat.search(line)
        if not m:
            # What happened?
            raise DockerError('Failed to parse "docker images" output line: {}'.format(line))

        if m.group('image') == '<none>' and m.group('tag') == '<none>':
            images.append(m.group('id'))
        elif m.group('tag') == 'latest':
            images.append(m.group('image'))
        else:
            images.append('{image}:{tag}'.format(image=m.group('image'), tag=m.group('tag')))

    return images


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

