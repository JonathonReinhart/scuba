import os
import yaml
import shlex
try:
    basestring
except NameError:
    basestring = str    # Python 3

from .constants import *

class ConfigError(Exception):
    pass

def shlex_split(s):
    # shlex.split doesn't properly handle unicode input in Python 2.6.
    # First try to encode it as an ASCII string. which
    # may raise a UnicodeEncodeError.
    s = str(s)
    return shlex.split(s)

# http://stackoverflow.com/a/9577670
class Loader(yaml.Loader):
    def __init__(self, stream):
        self._root = os.path.split(stream.name)[0]
        super(Loader, self).__init__(stream)

    def from_yaml(self, node):
        '''
        Implementes a !from_yaml constructor with the following syntax:
            !from_yaml filename key

        Arguments:
            filename:   Filename of external YAML document from which to load,
                        relative to the current YAML file.
            key:        Key from external YAML document to return,
                        using a dot-separated syntax for nested keys.

        Examples:
            !from_yaml external.yml pop
            !from_yaml external.yml foo.bar.pop
            !from_yaml "another file.yml" "foo bar.snap crackle.pop"
        '''

        # Load the content from the node, as a scalar
        content = self.construct_scalar(node)

        # Split on unquoted spaces
        try:
            parts = shlex_split(content)
        except UnicodeEncodeError:
            raise yaml.YAMLError('Non-ASCII arguments to !from_yaml are unsupported')

        if len(parts) != 2:
            raise yaml.YAMLError('Two arguments expected to !from_yaml')
        filename, key = parts

        # path is relative to the current YAML document
        path = os.path.join(self._root, filename)

        # Load the other YAML document
        with open(path, 'r') as f:
            doc = yaml.load(f, self.__class__)

        # Retrieve the key
        try:
            cur = doc
            for k in key.split('.'):
                cur = cur[k]
        except KeyError:
            raise yaml.YAMLError('Key "{0}" not found in {1}'.format(key, filename))
        return cur

Loader.add_constructor('!from_yaml', Loader.from_yaml)


def find_config():
    '''Search up the diretcory hierarchy for .scuba.yml

    Returns: path, rel on success, or None if not found
        path    The absolute path of the directory where .scuba.yml was found
        rel     The relative path from the directory where .scuba.yml was found
                to the current directory
    '''
    cross_fs = 'SCUBA_DISCOVERY_ACROSS_FILESYSTEM' in os.environ
    path = os.getcwd()

    rel = ''
    while True:
        if os.path.exists(os.path.join(path, SCUBA_YML)):
            return path, rel

        if not cross_fs and os.path.ismount(path):
            msg = '{0} not found here or any parent up to mount point {1}'.format(SCUBA_YML, path) \
                   + '\nStopping at filesystem boundary (SCUBA_DISCOVERY_ACROSS_FILESYSTEM not set).'
            raise ConfigError(msg)

        # Traverse up directory hierarchy
        path, rest = os.path.split(path)
        if not rest:
            raise ConfigError('{0} not found here or any parent directories'.format(SCUBA_YML))

        # Accumulate the relative path back to where we started
        rel = os.path.join(rest, rel)


class ScubaConfig(object):
    def __init__(self, **data):
        required_nodes = ('image',)
        optional_nodes = ('aliases','hooks',)

        # Check for missing required nodes
        missing = [n for n in required_nodes if not n in data]
        if missing:
            raise ConfigError('{0}: Required node{1} missing: {2}'.format(SCUBA_YML,
                    's' if len(missing) > 1 else '', ', '.join(missing)))

        # Check for unrecognized nodes
        extra = [n for n in data if not n in required_nodes + optional_nodes]
        if extra:
            raise ConfigError('{0}: Unrecognized node{1}: {2}'.format(SCUBA_YML,
                    's' if len(extra) > 1 else '', ', '.join(extra)))

        self._image = data['image']

        self._aliases = {}
        for alias, cmdstr in data.get('aliases', {}).items():
            self._aliases[alias] = shlex_split(cmdstr)

        self._load_hooks(data)


    def _process_script(self, node, name):
        '''Process a script-type node

        This can handle yaml of either a simple form:

            node: this is my script

        Or a more complex form (which allows for other sub-nodes):

            node:
              script:
                - this is my script
                - it has multiple parts

        Other forms are disallowed:

            node:
              - this
              - is
              - forbidden
        '''
        if isinstance(node, basestring):
            # The script is just the text itself
            return [node]


        if isinstance(node, dict):
            # There must be a "script" key, which must be a list of strings
            script = node.get('script')
            if not script:
                raise ConfigError("{0}: must have a 'script' subkey".format(name))

            if not isinstance(script, list):
                raise ConfigError("{0}.script: must be a list".format(name))

            return script

        raise ConfigError("{0}: must be string or dict".format(name))


    def _load_hooks(self, data):
        self._hooks = {}

        for name in ('user', 'root',):
            node = data.get('hooks', {}).get(name)
            if node:
                hook = self._process_script(node, name)
                self._hooks[name] = hook


    @property
    def image(self):
        return self._image

    @property
    def aliases(self):
        return self._aliases

    @property
    def hooks(self):
        return self._hooks


    def process_command(self, command):
        if command:
            rep = self.aliases.get(command[0])
            if rep:
                command.pop(0)
                command = rep + command

        return command


def load_config(path):
    try:
        with open(path) as f:
            data = yaml.load(f, Loader)
    except IOError as e:
        raise ConfigError('Error opening {0}: {1}'.format(SCUBA_YML, e))
    except yaml.YAMLError as e:
        raise ConfigError('Error loading {0}: {1}'.format(SCUBA_YML, e))

    return ScubaConfig(**(data or {}))
