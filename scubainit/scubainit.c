#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <assert.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <limits.h>
#include <pwd.h>
#include <grp.h>
#include <shadow.h>
#include <sys/stat.h>   /* umask(2) */

/**
 * SYNOPSIS
 *      scubainit argument...
 */

#define APPNAME             "scubainit"

#define errmsg(fmt, ...)     fprintf(stderr, APPNAME ": " fmt, ##__VA_ARGS__)
#define verbose(fmt, ...)    (void)(m_verbose && errmsg(fmt, ##__VA_ARGS__))

#define ETC_PASSWD          "/etc/passwd"
#define ETC_GROUP           "/etc/group"
#define ETC_SHADOW          "/etc/shadow"
#define INVALID_PASSWORD    "x"

#define SCUBA_USER          "scubauser"
#define SCUBA_GROUP         "scubauser"
#define SCUBA_HOME          "/home/scubauser"
#define SCUBA_USER_FULLNAME "Scuba User"

#define SCUBAINIT_UID       "SCUBAINIT_UID"
#define SCUBAINIT_GID       "SCUBAINIT_GID"
#define SCUBAINIT_UMASK     "SCUBAINIT_UMASK"
#define SCUBAINIT_HOOK_USER "SCUBAINIT_HOOK_USER"
#define SCUBAINIT_HOOK_ROOT "SCUBAINIT_HOOK_ROOT"
#define SCUBAINIT_VERBOSE   "SCUBAINIT_VERBOSE"

static bool m_verbose = false;
static int m_uid = -1;
static int m_gid = -1;
static int m_umask = -1;

static const char *m_user_hook;
static const char *m_root_hook;


/* Returns true if the scuba user should be used */
static bool
use_scuba_user(void)
{
    if (m_uid >= 0) {
        assert(m_gid >= 0);
        return true;
    }

    assert(m_gid == -1);
    return false;
}


/**
 * Add a group to a group file
 *
 * Arguments:
 * - path       Path to /etc/group
 * - name       Group name to add
 * - gid        Group ID
 *
 * Returns 0 on success, or -1 otherwise.
 */
static int
add_group(const char *path, const char *name, unsigned int gid)
{
    int result = -1;
    FILE *f = NULL;

    /* Open for reading and appending (writing at end of file).  The file is
     * created if it does not exist.  The initial file position for reading is
     * at the beginning of the file, but output is always appended to the end
     * of the file.
     */
    if ((f = fopen(path, "a+")) == NULL) {
        errmsg("Failed to open %s: %m\n", path);
        goto out;
    }

    /**
     * Try to find a conflicting group (one matching name or gid).
     */
    for (;;) {
        struct group *gr = fgetgrent(f);

        if (gr == NULL)
            break;

        if (strcmp(gr->gr_name, name) == 0) {
            errmsg("Group \"%s\" already exists in %s\n", name, path);
            goto out;
        }

        if (gr->gr_gid == gid) {
            errmsg("GID %u already exists in %s\n", gid, path);
            goto out;
        }
    }

    /* Okay, add scuba group */
    struct group gr = {
        .gr_name    = (char*)name,      /* putgrent will not modify */
        .gr_passwd  = INVALID_PASSWORD,
        .gr_gid     = gid,
        .gr_mem     = NULL,
    };

    if (putgrent(&gr, f) != 0) {
        errmsg("Failed to add group \"%s\" to %s: %m\n", name, path);
        goto out;
    }

    verbose("Added group \"%s\" to %s\n", name, path);
    result = 0;

out:
    if (f != NULL)
        fclose(f);

    return result;
}

/**
 * Add a user to a passwd file
 *
 * Arguments:
 * - path       Path to /etc/passwd
 * - name       User name to add
 * - uid        User ID
 * - gid        User primary group ID
 * - gecos      Full name
 *
 * Returns 0 on success, or -1 otherwise.
 */
static int
add_user(const char *path, const char *name, unsigned int uid, unsigned int gid,
         const char *gecos, const char *homedir)
{
    int result = -1;
    FILE *f = NULL;

    /* Open for reading and appending (writing at end of file).  The file is
     * created if it does not exist.  The initial file position for reading is
     * at the beginning of the file, but output is always appended to the end
     * of the file.
     */
    if ((f = fopen(path, "a+")) == NULL) {
        errmsg("Failed to open %s: %m\n", path);
        goto out;
    }

    /**
     * Try to find a conflicting user (one matching name or uid).
     */
    for (;;) {
        struct passwd *pw = fgetpwent(f);

        if (pw == NULL)
            break;

        if (strcmp(pw->pw_name, name) == 0) {
            errmsg("User \"%s\" already exists in %s\n", name, path);
            goto out;
        }

        if (pw->pw_uid == uid) {
            errmsg("UID %u already exists in %s\n", uid, path);
            goto out;
        }
    }

    /* Okay, add user */
    struct passwd pw = {
        .pw_name    = (char*)name,      /* putpwent will not modify */
        .pw_passwd  = INVALID_PASSWORD,
        .pw_uid     = uid,
        .pw_gid     = gid,
        .pw_gecos   = (char*)gecos,     /* putpwent will not modify */
        .pw_dir     = (char*)homedir,   /* putpwent will not modify */
        .pw_shell   = "/bin/sh",
    };

    if (putpwent(&pw, f) != 0) {
        errmsg("Failed to add user \"%s\" to %s: %m\n", name, path);
        goto out;
    }

    verbose("Added user \"%s\" to %s\n", name, path);
    result = 0;

out:
    if (f != NULL)
        fclose(f);

    return result;
}

/**
 * Add an entry to a shadow password file
 *
 * Arguments:
 * - path       Path to /etc/shadow
 * - name       User name to add
 *
 * TODO: Add remaining shadow fields, which we don't care about today.
 *
 * Returns 0 on success, or -1 otherwise.
 */
static int
add_shadow(const char *path, const char *name)
{
    int result = -1;
    FILE *f = NULL;

    /* Open for reading and appending (writing at end of file).  The file is
     * created if it does not exist.  The initial file position for reading is
     * at the beginning of the file, but output is always appended to the end
     * of the file.
     */
    if ((f = fopen(path, "a+")) == NULL) {
        errmsg("Failed to open %s: %m\n", path);
        goto out;
    }

    /**
     * Try to find a conflicting user (one matching name).
     */
    for (;;) {
        struct spwd *sp = fgetspent(f);

        if (sp == NULL)
            break;

        if (strcmp(sp->sp_namp, name) == 0) {
            errmsg("User \"%s\" already exists in %s\n", name, path);
            goto out;
        }
    }

    /* Okay, add shadow password */
    struct spwd sp = {
        .sp_namp    = (char*) name,     /* putspent will not modify */
        .sp_pwdp    = INVALID_PASSWORD,
        .sp_lstchg  = (long) -1,
        .sp_min     = (long) -1,
        .sp_max     = (long) -1,
        .sp_warn    = (long) -1,
        .sp_inact   = (long) -1,
        .sp_expire  = (long) -1,
        .sp_flag    = (long) -1,
    };

    if (putspent(&sp, f) != 0) {
        errmsg("Failed to add user \"%s\" to %s: %m\n", name, path);
        goto out;
    }

    verbose("Added user \"%s\" to %s\n", name, path);
    result = 0;

out:
    if (f != NULL)
        fclose(f);

    return result;
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

    /* Set expected environment variables */
    setenv("USER", SCUBA_USER, 1);
    setenv("LOGNAME", SCUBA_USER, 1);
    setenv("HOME", SCUBA_HOME, 1);

    verbose("Changed to uid=%u euid=%u  gid=%u egid=%u\n",
            getuid(), geteuid(), getgid(), getegid());

    return 0;
}

static int
mkdir_p(const char *path)
{
    /* Adapted from http://stackoverflow.com/a/2336245/119527 */
    const size_t len = strlen(path);
    char _path[PATH_MAX];
    char *p;

    errno = 0;

    /* Copy string so its mutable */
    if (len > sizeof(_path)-1) {
        errno = ENAMETOOLONG;
        return -1;
    }
    strcpy(_path, path);

    /* Iterate the string */
    for (p = _path + 1; *p; p++) {
        if (*p == '/') {
            /* Temporarily truncate */
            *p = '\0';

            if (mkdir(_path, S_IRWXU) != 0) {
                if (errno != EEXIST)
                    return -1;
            }

            *p = '/';
        }
    }

    if (mkdir(_path, S_IRWXU) != 0) {
        if (errno != EEXIST)
            return -1;
    }

    return 0;
}

static int
make_homedir(const char *path, unsigned int uid, unsigned int gid)
{
    if (mkdir_p(path) != 0) {
        errmsg("Failed to create %s: %m\n", path);
        return -1;
    }
    if (chmod(path, 0700) != 0) {
        errmsg("Failed to chmod %s: %m\n", path);
        return -1;
    }
    if (chown(path, uid, gid) != 0) {
        errmsg("Failed to chown %s: %m\n", path);
        return -1;
    }
    return 0;
}

static int
make_executable(const char *path)
{
    int ret = -1;
    struct stat st;
    mode_t mode;

    if (stat(path, &st) != 0)
        goto out;

    mode = st.st_mode;

    /* Copy R bits to X */
    mode |= (mode & 0444) >> 2;

    if (chmod(path, mode) != 0)
        goto out;

    ret = 0;

out:
    return ret;
}

static int
call_hook(const char *hook_path)
{
    int rc;

    /* Nothing to do? */
    if (hook_path == NULL)
        return 0;

    if (make_executable(hook_path) != 0) {
        errmsg("Failed to make executable %s: %m\n", hook_path);
        exit(99);
    }

    verbose("About to execute %s\n", hook_path);
    rc = system(hook_path);

    if (rc < 0) {
        errmsg("Failed to execute %s: %m\n", hook_path);
        exit(99);
    }
    if (rc > 0) {
        errmsg("%s exited with status %d\n", hook_path, rc);
        exit(rc);
    }

    return 0;
}

static int
str2uint(const char *val, unsigned int *result)
{
    char *end;
    unsigned long int temp;

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

/**
 * Gets an optional uint environment variable, unsetting it
 * from the environment.
 *
 * Returns:
 * -1   Variable was set but invalid
 *  0   Variable was set to a valid value, assigned to *result
 *  1   Varibale was not set
 */
static int
getenv_uint_opt_unset(const char *name, int *result)
{
    char *var;
    unsigned int uval;

    var = getenv(name);
    if (!var)
        return 1;

    if (str2uint(var, &uval) != 0) {
        errmsg("%s invalid: \"%s\"\n", name, var);
        return -1;
    }

    verbose("%s = %u\n", name, uval);
    unsetenv(name);
    *result = uval;

    return 0;
}

/**
 * Gets an environment variable string, and unsets it
 */
static char *
getenv_str_unset(const char *name)
{
    char *var;

    if (!(var = getenv(name)))
        return NULL;

    /* Duplicate the string then unset the var */
    var = strdup(var);
    unsetenv(name);

    return var;
}


static int
process_envvars(void)
{
    int ids_set = 0;

    /* Get the env. vars from scuba */

    /**
     * SCUBAINIT_UID and SCUBAINIT_GID are optional,
     * but if either is set, both must be set.
     */
    switch (getenv_uint_opt_unset(SCUBAINIT_UID, &m_uid)) {
        case -1:
            return -1;
        case 0:
            ids_set++;
            break;
    }
    switch (getenv_uint_opt_unset(SCUBAINIT_GID, &m_gid)) {
        case -1:
            return -1;
        case 0:
            ids_set++;
            break;
    }
    switch (ids_set) {
        case 0:
        case 2:
            break;
        default:
            errmsg("If SCUBAINIT_UID or SCUBAINIT_GID are set, both must be set.\n");
            return -1;
    }


    /**
     * SCUBAINIT_UMASK is optional.
     */
    switch (getenv_uint_opt_unset(SCUBAINIT_UMASK, &m_umask)) {
        case -1:
            return -1;
    }


    if (getenv(SCUBAINIT_VERBOSE)) {
        unsetenv(SCUBAINIT_VERBOSE);
        m_verbose = true;
    }

    /* Hook scripts */
    m_user_hook = getenv_str_unset(SCUBAINIT_HOOK_USER);
    m_root_hook = getenv_str_unset(SCUBAINIT_HOOK_ROOT);


    /* Clear out other env. vars */
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

    if (use_scuba_user()) {
        /* Create scuba user home directory */
        if (make_homedir(SCUBA_HOME, m_uid, m_gid) != 0)
            exit(99);

        /* Add scuba user and group */
        if (add_group(ETC_GROUP, SCUBA_GROUP, m_gid) != 0)
            exit(99);
        if (add_user(ETC_PASSWD, SCUBA_USER, m_uid, m_gid,
                    SCUBA_USER_FULLNAME, SCUBA_HOME) != 0)
            exit(99);
        if (add_shadow(ETC_SHADOW, SCUBA_USER) != 0)
            exit(99);
    }

    /* Call pre-su hook */
    call_hook(m_root_hook);

    /* Handle the scuba user */
    if (use_scuba_user()) {
        if (change_user() < 0)
            exit(99);
    }

    if (m_umask >= 0) {
        verbose("Setting umask to 0%o\n", m_umask);
        umask(m_umask);
    }

    /* Call post-su hook, only if we switch users */
    if (use_scuba_user()) {
        call_hook(m_user_hook);
    }


    /* Prepare for execution of user command */
    new_argc = argc - 1;
    new_argv = argv + 1;

    if (new_argc == 0) {
        errmsg("Missing command\n");
        exit(99);
    }

    verbose("execvp(\"%s\", ...)\n", new_argv[0]);
    execvp(new_argv[0], new_argv);

    errmsg("execv() failed: %m\n");
    exit(99);
}
