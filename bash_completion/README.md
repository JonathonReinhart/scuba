# Bash command-line completion for Scuba

This script enables command-line completion for `scuba` in Bash.
Curently it completes the following:

- Options (after starting an argument with a dash)
- Aliases (as defined in your `.scuba.yml`)

You must first install the `bash-completion` package for your system, and then
manually install this into the appropriate location for your bash installation.

### Linux (Debian, RedHat)
- Install (via apt or yum) the `bash-completion` package
- Copy the `scuba` completion script to `/etc/bash_completion.d/`
