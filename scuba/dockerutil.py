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

    info = json.loads(stdout.decode('utf-8'))[0]
    return info['Config']['Cmd']


def make_vol_opt(hostdir, contdir, options=None):
    '''Generate a docker volume option'''
    vol = '--volume={0}:{1}'.format(hostdir, contdir)
    if options != None:
        if isinstance(options, str):
            options = (options,)
        vol += ':' + ','.join(options)
    return vol

