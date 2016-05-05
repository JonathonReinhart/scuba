#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>
#include <limits.h>
#include <grp.h>        /* setgroups(2) */
#include <sys/stat.h>   /* umask(2) */

/**
 * SYNOPSIS
 *      scubainit argument...
 */

#define APPNAME             "scubainit"

#define errmsg(fmt, ...)     fprintf(stderr, APPNAME ": " fmt, ##__VA_ARGS__)
#define verbose(fmt, ...)    errmsg(fmt, ##__VA_ARGS__)


#define SCUBAINIT_UID   "SCUBAINIT_UID"
#define SCUBAINIT_GID   "SCUBAINIT_GID"
#define SCUBAINIT_UMASK "SCUBAINIT_UMASK"
#define SCUBAINIT_HOOK  "SCUBAINIT_HOOK"

static unsigned int m_uid;
static unsigned int m_gid;
static unsigned int m_umask;

static void
print_argv(int argc, char **argv)
{
    int i;

    /* <= is intentional; include NULL terminator */
    for (i = 0; i <= argc; i++) {
        printf("   [%d] = \"%s\"\n", i, argv[i]);
    }
}

static int
change_user(void)
{
    /* TODO: Would we ever want to get this list from scuba, too? */
    if (setgroups(0, NULL) != 0) {
        errmsg("Failed to setgroups(): %m\n");
        return -1;
    }
    verbose("Cleared supplementary group list\n");

    if (setgid(m_gid) != 0) {
        errmsg("Failed to setgid(%u): %m\n", m_gid);
        return -1;
    }

    if (setuid(m_uid) != 0) {
        errmsg("Failed to setuid(%u): %m\n", m_uid);
        return -1;
    }

    verbose("Changed to uid=%u euid=%u  gid=%u egid=%u\n",
            getuid(), geteuid(), getgid(), getegid());

    return 0;
}

static int
getenv_uint(const char *name, unsigned int *result)
{
    char *val;
    char *end;
    unsigned long int temp;

    if ((val = getenv(name)) == NULL)
        return -1;

    if (*val == '\0')
        return -1;

    temp = strtoul(val, &end, 0);

    /* "if *nptr is not '\0' but **endptr is '\0' on return,
     * the entire string is valid."
     */
    if (*end != '\0')
        return -1;

    if (temp > UINT_MAX)
        return -1;

    *result = temp;
    return 0;
}

static int
process_envvars(void)
{
    /* Get the env. vars from scuba */
    if (getenv_uint(SCUBAINIT_UID, &m_uid)) {
        errmsg("SCUBAINIT_UID not set or invalid\n");
        return -1;
    }
    unsetenv(SCUBAINIT_UID);
    verbose("SCUBAINIT_UID = %u\n", m_uid);

    if (getenv_uint(SCUBAINIT_GID, &m_gid)) {
        errmsg("SCUBAINIT_GID not set or invalid\n");
        return -1;
    }
    unsetenv(SCUBAINIT_GID);
    verbose("SCUBAINIT_GID = %u\n", m_gid);

    if (getenv_uint(SCUBAINIT_UMASK, &m_umask)) {
        errmsg("SCUBAINIT_UMASK not set or invalid\n");
        return -1;
    }
    unsetenv(SCUBAINIT_UMASK);
    verbose("SCUBAINIT_UMASK= 0%o\n", m_umask);

    /* Clear out other env. vars */
    unsetenv("USER");
    unsetenv("HOME");
    unsetenv("LOGNAME");
    unsetenv("PWD");
    unsetenv("OLDPWD");
    unsetenv("XAUTHORITY");

    return 0;
}

int
main(int argc, char **argv)
{
    char **new_argv;
    int new_argc;

    /**
     * This is the assumption that execv() makes.
     * This appears to be true on every system I've tried, although I cannot
     * find anything that guarantees this. So make sure the element after the
     * last is a NULL terminator. If we find that this faults on a system, we
     * can do the annoying and expensive duplication.
     */
    argv[argc] = NULL;

    if (process_envvars() < 0)
        exit(99);

    printf("Program args:\n");
    print_argv(argc, argv);

    new_argc = argc - 1;
    new_argv = argv + 1;

    if (new_argc == 0) {
        errmsg("Missing command\n");
        exit(99);
    }

    printf("To-be executed args:\n");
    print_argv(new_argc, new_argv);

    if (change_user() < 0)
        exit(99);

    verbose("Setting umask to 0%o\n", m_umask);
    umask(m_umask);

    verbose("execvp(\"%s\", ...)\n", new_argv[0]);
    execvp(new_argv[0], new_argv);

    errmsg("execv() failed: %m\n");
    exit(99);
}
