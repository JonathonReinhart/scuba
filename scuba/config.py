import collections
import os
import yaml
import re
import shlex

from .constants import *
from .utils import *
from .dockerutil import make_vol_opt

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

def _get_typed_val(data, key, type_):
    v = data.get(key)
    if v is not None and not isinstance(v, type_):
        raise ConfigError("'{}' must be a {}, not {}".format(
                key, type_.__name__, type(v).__name__))
    return v

def _get_dict(data, key):
    return _get_typed_val(data, key, dict)

def _get_delimited_str_list(data, key, sep):
    s = _get_typed_val(data, key, str)
    return s.split(sep) if s else []

def _get_volumes(data):
    voldata = _get_dict(data, 'volumes')
    if voldata is None:
        return None

    vols = {}
    for cpath, v in voldata.items():
        cpath = _expand_path(cpath)
        vols[cpath] = ScubaVolume.from_dict(cpath, v)
    return vols

def _expand_path(in_str):
    try:
        output = expand_env_vars(in_str)
    except KeyError as ke:
        # pylint: disable=raise-missing-from
        raise ConfigError("Unset environment variable '{}' used in '{}'".format(ke.args[0], in_str))
    except ValueError as ve:
        raise ConfigError("Unable to expand string '{}' due to parsing "
                "errors".format(in_str)) from ve

    return output

class ScubaVolume:
    def __init__(self, container_path, host_path=None, options=None):
        self.container_path = container_path
        self.host_path = host_path
        self.options = options or []

    @classmethod
    def from_dict(cls, cpath, node):
        # Treat a null node as an empty dict
        if node is None:
            node = {}

        # Simple form:
        # volumes:
        #   /foo: /host/foo
        if isinstance(node, str):
            return cls(
                container_path = cpath,
                host_path = _expand_path(node),
                )

        # Complex form
        # volumes:
        #   /foo:
        #     hostpath: /host/foo
        #     options: ro,z
        if isinstance(node, dict):
            hpath = node.get('hostpath')
            if hpath is None:
                raise ConfigError("Volume {} must have a 'hostpath' subkey".format(cpath))
            return cls(
                container_path = cpath,
                host_path = _expand_path(hpath),
                options = _get_delimited_str_list(node, 'options', ','),
                )

        raise ConfigError("{}: must be string or dict".format(cpath))

    def get_vol_opt(self):
        if not self.host_path:
            raise NotImplementedError("No anonymous volumes for now")
        return make_vol_opt(self.host_path, self.container_path, self.options)


class ScubaAlias:
    def __init__(self, name, script, image=None, entrypoint=None,
            environment=None, shell=None, as_root=None, docker_args=None,
            volumes=None):
        self.name = name
        self.script = script
        self.image = image
        self.entrypoint = entrypoint
        self.environment = environment
        self.shell = shell
        self.as_root = bool(as_root)
        self.docker_args = docker_args
        self.volumes = volumes

    @classmethod
    def from_dict(cls, name, node):
        script = _process_script_node(node, name)

        if isinstance(node, dict):  # Rich alias
            return cls(
                name = name,
                script = script,
                image = node.get('image'),
                entrypoint = _get_entrypoint(node),
                environment = _process_environment(
                        node.get('environment'),
                        '{}.{}'.format(name, 'environment')),
                shell = node.get('shell'),
                as_root = node.get('root'),
                docker_args = _get_docker_args(node),
                volumes = _get_volumes(node),
                )

        return cls(name=name, script=script)


class ScubaConfig:
    def __init__(self, **data):
        optional_nodes = (
            'image', 'aliases', 'hooks', 'entrypoint', 'environment', 'shell',
            'docker_args', 'volumes',
        )

        # Check for unrecognized nodes
        extra = [n for n in data if not n in optional_nodes]
        if extra:
            raise ConfigError('{}: Unrecognized node{}: {}'.format(SCUBA_YML,
                    's' if len(extra) > 1 else '', ', '.join(extra)))

        self._image = data.get('image')
        self.shell = data.get('shell', DEFAULT_SHELL)
        self.entrypoint = _get_entrypoint(data)
        self.docker_args = _get_docker_args(data)
        self.volumes = _get_volumes(data)
        self._load_aliases(data)
        self._load_hooks(data)
        self._load_environment(data)


    def _load_aliases(self, data):
        self.aliases = {}

        for name, node in data.get('aliases', {}).items():
            if ' ' in name:
                raise ConfigError('Alias names cannot contain spaces')
            self.aliases[name] = ScubaAlias.from_dict(name, node)

    def _load_hooks(self, data):
        self.hooks = {}

        for name in ('user', 'root',):
            node = data.get('hooks', {}).get(name)
            if node:
                hook = _process_script_node(node, name)
                self.hooks[name] = hook

    def _load_environment(self, data):
        self.environment = _process_environment(data.get('environment'), 'environment')


    @property
    def image(self):
        if not self._image:
            raise ConfigError("Top-level 'image' not set")
        return self._image



def load_config(path):
    try:
        with open(path, 'r') as f:
            data = yaml.load(f, Loader)
    except IOError as e:
        raise ConfigError('Error opening {}: {}'.format(SCUBA_YML, e))
    except yaml.YAMLError as e:
        raise ConfigError('Error loading {}: {}'.format(SCUBA_YML, e))

    return ScubaConfig(**(data or {}))
