# Constants used throughout the test suite

# Main Docker image
# This image is used for nearly all tests where a "real" docker image is
# necessary (becuase we're going to actually invoke some docker command).
#
# Requirements:
# - Must contain /bin/bash (TestMain::test_*shell_override*)
#
DOCKER_IMAGE = 'debian:8.2'

# Alternate Docker image
# This image is used for alternate tests (e.g. pulling) and should be small.
ALT_DOCKER_IMAGE = 'busybox:latest'


# Act as an executable for consumption by non-Python things
if __name__ == '__main__':
    for name, val in dict(vars()).items():
        if name.startswith('_'):
            continue
        print('{}="{}"'.format(name, val))
