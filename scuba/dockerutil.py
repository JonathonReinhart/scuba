import subprocess
import errno
import json

class DockerError(Exception):
    pass

def get_image_command(image):
    '''Gets the default command for an image'''
    args = ['docker', 'inspect', image]
    try:
        p = subprocess.Popen(args, stdout = subprocess.PIPE)
    except OSError as e:
        if e.errno == errno.ENOENT:
            raise DockerError('Failed to execute docker. Is it installed?')
        raise

    stdout, _ = p.communicate()
    if not p.returncode == 0:
        raise DockerError('Failed to inspect image')

    info = json.loads(stdout)[0]
    return info['Config']['Cmd']

