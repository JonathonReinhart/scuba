# `dev/`

This directory exists to facilitate scuba development, particularly on machines
where scuba may already be installed. The idea is taken from virtualenv.

To use it, simply *source* the `activate` script:
```
$ source dev/activate
```

Now the `dev/` directory is in `PATH`, and this `scuba` will be used. It is
special in that it forces this project directory to be first in the Python
path, ensuring that the project scuba package will be used.
