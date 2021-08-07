import collections
import os
import yaml
import re
import shlex

from .constants import *
from .utils import *

class ConfigError(Exception):
    pass

class ConfigNotFoundError(ConfigError):
    pass

class OverrideMixin:
    '''
    A mixin class that indicates an instance's value should override something

    This class is mixed into objects loaded from YAML with an !override tag,
    and any object can be checked if it is an OverrideMixin using isinstance().
    '''
    pass

class OverrideNone(OverrideMixin):
    '''
    Represents a None value that also has Override behavior
    '''
    def __bool__(self):
        return False

class OverrideList(collections.UserList, OverrideMixin):
    pass

class OverrideStr(str, OverrideMixin):
    pass

# http://stackoverflow.com/a/9577670
class Loader(yaml.SafeLoader):
    def __init__(self, stream, root=None):
        if root is None:
            self._root = os.path.split(stream.name)[0]
        else:
            self._root = root
        self._cache = dict()
        super().__init__(stream)

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
        parts = shlex.split(content)
        if len(parts) != 2:
            raise yaml.YAMLError('Two arguments expected to !from_yaml')
        filename, key = parts

        # path is relative to the current YAML document
        path = os.path.join(self._root, filename)

        # Load the other YAML document
        doc = self._cache.get(path)
        if not doc:
            with open(path, 'r') as f:
                doc = yaml.load(f, self.__class__)
                self._cache[path] = doc

        # Retrieve the key
        try:
            cur = doc
            # Use a negative look-behind to split the key on non-escaped '.' characters
            for k in re.split(r'(?<!\\)\.', key):
                cur = cur[k.replace('\\.', '.')]  # Be sure to replace any escaped '.' characters with *just* the '.'
        except KeyError:
            raise yaml.YAMLError('Key "{}" not found in {}'.format(key, filename))
        return cur

    def override(self, node):
        '''
        Implements !override constructor
        '''
        # Load the content from the node, as a scalar
        content = self.construct_scalar(node)

        # Dynamically add an OverrideMixin to the resulting object's type
        obj = yaml.load(content, lambda s: Loader(s, root=self._root))
        if obj is None:
            obj = OverrideNone()
        else:
            objtype = type(obj)
            mixin_type = type('Override' + objtype.__name__, (objtype, OverrideMixin), dict())

            try:
                obj.__class__ = mixin_type
            except TypeError:
                # Primitive classes (e.g., int, str) don't support __class__ assignment
                obj = mixin_type(obj)

        return obj

Loader.add_constructor('!from_yaml', Loader.from_yaml)
Loader.add_constructor('!override', Loader.override)


def find_config():
    '''Search up the directory hierarchy for .scuba.yml

    Returns: path, rel, config on success, or None if not found
        path    The absolute path of the directory where .scuba.yml was found
        rel     The relative path from the directory where .scuba.yml was found
                to the current directory
        config  The loaded configuration
    '''
    cross_fs = 'SCUBA_DISCOVERY_ACROSS_FILESYSTEM' in os.environ
    path = os.getcwd()

    rel = ''
    while True:
        cfg_path = os.path.join(path, SCUBA_YML)
        if os.path.exists(cfg_path):
            return path, rel, load_config(cfg_path)

        if not cross_fs and os.path.ismount(path):
            msg = '{} not found here or any parent up to mount point {}'.format(SCUBA_YML, path) \
                   + '\nStopping at filesystem boundary (SCUBA_DISCOVERY_ACROSS_FILESYSTEM not set).'
            raise ConfigNotFoundError(msg)

        # Traverse up directory hierarchy
        path, rest = os.path.split(path)
        if not rest:
            raise ConfigNotFoundError('{} not found here or any parent directories'.format(SCUBA_YML))

        # Accumulate the relative path back to where we started
        rel = os.path.join(rest, rel)


def _process_script_node(node, name):
    '''Process a script-type node

    This handles nodes that follow the *Common script schema*,
    as outlined in doc/yaml-reference.md.
    '''
    if isinstance(node, str):
        # The script is just the text itself
        return [node]


    if isinstance(node, dict):
        # There must be a "script" key, which must be a list of strings
        script = node.get('script')
        if not script:
            raise ConfigError("{}: must have a 'script' subkey".format(name))

        if isinstance(script, list):
            return script

        if isinstance(script, str):
            return [script]

        raise ConfigError("{}.script: must be a string or list".format(name))

    raise ConfigError("{}: must be string or dict".format(name))


def _process_environment(node, name):
    # Environment can be either a list of strings ("KEY=VALUE") or a mapping
    # Environment keys and values are always strings
    result = {}

    if not node:
        pass
    elif isinstance(node, dict):
        for k, v in node.items():
            if v is None:
                v = os.getenv(k, '')
            result[k] = str(v)
    elif isinstance(node, list):
        for e in node:
            k, v = parse_env_var(e)
            result[k] = v
    else:
        raise ConfigError("'{}' must be list or mapping, not {}".format(
                name, type(node).__name__))

    return result

def _get_nullable_str(data, key):
    # N.B. We can't use data.get() here, because that might return
    # None, leading to ambiguity between the key being absent or set
    # to a null value.
    #
    # "Note that a null is different from an empty string and that a
    # mapping entry with some key and a null value is valid and
    # different from not having that key in the mapping."
    #   - http://yaml.org/type/null.html
    if not key in data:
        return None

    ep = data[key]

    # We represent a null value as an empty string.
    if isinstance(ep, OverrideNone):
        ep = OverrideStr('')
    elif ep is None:
        ep = ''

    if not isinstance(ep, str):
        raise ConfigError("'{}' must be a string, not {}".format(
                key, type(ep).__name__))
    return ep

def _get_entrypoint(data):
    return _get_nullable_str(data, 'entrypoint')

def _get_docker_args(data):
    args = _get_nullable_str(data, 'docker_args')

    if args is not None:
        override = isinstance(args, OverrideMixin)
        args = shlex.split(args)
        if override:
            args = OverrideList(args)

    return args

class ScubaAlias:
    def __init__(self, name, script, image, entrypoint, environment, shell, as_root, docker_args):
        self.name = name
        self.script = script
        self.image = image
        self.entrypoint = entrypoint
        self.environment = environment
        self.shell = shell
        self.as_root = as_root
        self.docker_args = docker_args

    @classmethod
    def from_dict(cls, name, node):
        script = _process_script_node(node, name)
        image = None
        entrypoint = None
        environment = None
        shell = None
        as_root = False
        docker_args = None

        if isinstance(node, dict):  # Rich alias
            image = node.get('image')
            docker_args = _get_docker_args(node)
            entrypoint = _get_entrypoint(node)
            environment = _process_environment(
                    node.get('environment'),
                    '{}.{}'.format(name, 'environment'))
            shell = node.get('shell')
            as_root = node.get('root', as_root)

        return cls(name, script, image, entrypoint, environment, shell, as_root, docker_args)

class ScubaContext:
    pass

class ScubaConfig:
    def __init__(self, **data):
        optional_nodes = ('image','aliases','hooks','entrypoint','environment','shell','docker_args')

        # Check for unrecognized nodes
        extra = [n for n in data if not n in optional_nodes]
        if extra:
            raise ConfigError('{}: Unrecognized node{}: {}'.format(SCUBA_YML,
                    's' if len(extra) > 1 else '', ', '.join(extra)))

        self._image = data.get('image')
        self._shell = data.get('shell', DEFAULT_SHELL)
        self._entrypoint = _get_entrypoint(data)
        self._docker_args = _get_docker_args(data)
        self._load_aliases(data)
        self._load_hooks(data)
        self._environment = self._load_environment(data)




    def _load_aliases(self, data):
        self._aliases = {}

        for name, node in data.get('aliases', {}).items():
            if ' ' in name:
                raise ConfigError('Alias names cannot contain spaces')
            self._aliases[name] = ScubaAlias.from_dict(name, node)


    def _load_hooks(self, data):
        self._hooks = {}

        for name in ('user', 'root',):
            node = data.get('hooks', {}).get(name)
            if node:
                hook = _process_script_node(node, name)
                self._hooks[name] = hook

    def _load_environment(self, data):
         return _process_environment(data.get('environment'), 'environment')


    @property
    def image(self):
        if not self._image:
            raise ConfigError("Top-level 'image' not set")
        return self._image

    @property
    def entrypoint(self):
        return self._entrypoint

    @property
    def aliases(self):
        return self._aliases

    @property
    def hooks(self):
        return self._hooks

    @property
    def environment(self):
        return self._environment

    @property
    def shell(self):
        return self._shell

    @property
    def docker_args(self):
        return self._docker_args


    def process_command(self, command, image=None, shell=None):
        '''Processes a user command using aliases

        Arguments:
            command     A user command list (e.g. argv)
            image       Override the image from .scuba.yml
            shell       Override the shell from .scuba.yml

        Returns: A ScubaContext object with the following attributes:
            script: a list of command line strings
            image: the docker image name to use
        '''
        result = ScubaContext()
        result.script = None
        result.image = None
        result.entrypoint = self.entrypoint
        result.environment = self.environment.copy()
        result.shell = self.shell
        result.as_root = False
        result.docker_args = self.docker_args

        if command:
            alias = self.aliases.get(command[0])
            if not alias:
                # Command is not an alias; use it as-is.
                result.script = [shell_quote_cmd(command)]
            else:
                # Using an alias
                # Does this alias override the image and/or entrypoint?
                if alias.image:
                    result.image = alias.image
                if alias.entrypoint is not None:
                    result.entrypoint = alias.entrypoint
                if alias.shell is not None:
                    result.shell = alias.shell
                if alias.as_root:
                    result.as_root = True

                if isinstance(alias.docker_args, OverrideMixin) or result.docker_args is None:
                    result.docker_args = alias.docker_args
                elif alias.docker_args is not None:
                    result.docker_args.extend(alias.docker_args)

                # Merge/override the environment
                if alias.environment:
                    result.environment.update(alias.environment)

                if len(alias.script) > 1:
                    # Alias is a multiline script; no additional
                    # arguments are allowed in the scuba invocation.
                    if len(command) > 1:
                        raise ConfigError('Additional arguments not allowed with multi-line aliases')
                    result.script = alias.script

                else:
                    # Alias is a single-line script; perform substituion
                    # and add user arguments.
                    command.pop(0)
                    result.script = [alias.script[0] + ' ' + shell_quote_cmd(command)]

            result.script = flatten_list(result.script)

        # If a shell was given on the CLI, it should override the shell set by
        # the alias or top-level config
        if shell:
            result.shell = shell

        # If an image was given, it overrides what might have been set by an alias
        if image:
            result.image = image

        # If the image was still not set, then try to get it from the confg,
        # which will raise a ConfigError if it is not set
        if not result.image:
            result.image = self.image

        return result


def load_config(path):
    try:
        with open(path, 'r') as f:
            data = yaml.load(f, Loader)
    except IOError as e:
        raise ConfigError('Error opening {}: {}'.format(SCUBA_YML, e))
    except yaml.YAMLError as e:
        raise ConfigError('Error loading {}: {}'.format(SCUBA_YML, e))

    return ScubaConfig(**(data or {}))
