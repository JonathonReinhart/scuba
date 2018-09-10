# Scuba YAML File Reference

`.scuba.yml` is a [YAML] file which defines project-specific settings, allowing
a project to use Scuba as part of manual command-line interaction. As with many
other YAML file schemas, most options are controlled by top-level keys.



## Top-level keys

### `image`

The `image` node *is required* and defines the Docker image from which Scuba
containers are created.

Example:
```yaml
image: debian:8.2
```

### `environment`

The optional `environment` node allows environment variables to be specified.
This can be either a mapping (dictionary), or a list of `KEY=VALUE` pairs.
If a value is not specified, the value is taken from the external environment.

Examples:
```yaml
environment:
  FOO: "This is foo"
  SECRET:
```
```yaml
environment:
  - FOO=This is foo
  - SECRET
```


### `aliases`

The optional `aliases` node is a mapping (dictionary) of bash-like aliases,
where each key is an alias, and each value is the command that will be run when
that alias is specified as the *user command* during scuba invocation. The
command is parsed like a shell command-line, and additional user arguments from
the command line are appended to the alias arguments. Aliases follow the
[*common script schema*](#common-script-schema).

Example:
```yaml
aliases:
  build: make -j4
```
In this example, `$ scuba build foo` would execute `make -j4 foo` in the
container.

Aliases can also override the global `image`, allowing aliases to use different
images. Example:

```yaml
image: default_image
aliases:

  # This one inherits the default, top-level 'image' and specifies "script" as a string
  default:
    script: cat /etc/os-release

  # This one specifies a different image to use and specifies "script" as a list
  different:
    image: alpine
    script:
      - cat /etc/os-release
```

Aliases can add to the top-level `environment` and override its values using
the same syntax:
```yaml
environment:
  FOO: "Top-level"
aliases:
  example:
    environment:
      FOO: "Override"
      BAR: "New"
    script:
      - echo $FOO $BAR
```


### `hooks`

The optional `hooks` node is a mapping (dictionary) of "hook" scripts that run
as part of `scubainit` before running the user command. They use the
[*common script schema*](#common-script-schema). The following hooks exist:
- `root` - Runs just before `scubainit` switches from `root` to `scubauser`
- `user` - Runs just before `scubainit` executes the user command

Example:
```yaml
hooks:
  root:
    script:
      - 'echo "HOOK: This runs before we switch users"'
      - id
  user: 'echo "HOOK: After switching users, uid=$(id -u) gid=$(id -g)"'
```

## Common script schema
Several parts of `.scuba.yml` which define "scripts" use a common schema.
The *common script schema* can define a "script" in one of several forms:

The *simple* form is simply a single string value:
```yaml
hooks:
  user: echo hello
```

The *complex* form is a mapping, which must contain a `script` subkey, whose
value is either single string value
```yaml
hooks:
  root:
    script: echo hello
```

... or a list of strings making up the script:
```yaml
hooks:
  root:
    script:
      - 'echo hello!'
      - touch foo
      - 'echo goodbye :-('
```

Note that in any case, YAML strings do not need to be enclosed in quotes,
unless there are "confusing" characters (like a colon). In any case, it is
always safer to include quotes.


## Accessing external YAML content
In addition to normal [YAML] synax, an additional constructor, `!from_yaml`, is
available for use in `.scuba.yml` which allows a value to be retrieved from an
external YAML file. It has the following syntax:
```yaml
!from_yaml filename key
```
Arguments:
- **`filename`** - The path of an external YAML file (relative to `.scuba.yaml`)
- **`key`** - A dot-separated locator of the key to retrieve

This is useful for projects where a Docker image in which to build is already
specified in another YAML file, for example in [`.gitlab-ci.yml`]. This
eliminates the redundancy between the configuration files. An example which
uses this:

**`.gitlab-ci.yml`**
```yaml
image: gcc:5.1
# ...
```

**`.scuba.yml`**
```yaml
image: !from_yaml .gitlab-ci.yml image
```


[YAML]: http://yaml.org/
[`.gitlab-ci.yml`]: http://doc.gitlab.com/ce/ci/yaml/README.html


