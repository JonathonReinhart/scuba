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

#define USER_HOME           "/home"

#define SCUBAINIT_UID       "SCUBAINIT_UID"
#define SCUBAINIT_GID       "SCUBAINIT_GID"
#define SCUBAINIT_UMASK     "SCUBAINIT_UMASK"
#define SCUBAINIT_USER      "SCUBAINIT_USER"
#define SCUBAINIT_GROUP     "SCUBAINIT_GROUP"
#define SCUBAINIT_HOOK_USER "SCUBAINIT_HOOK_USER"
#define SCUBAINIT_HOOK_ROOT "SCUBAINIT_HOOK_ROOT"
#define SCUBAINIT_VERBOSE   "SCUBAINIT_VERBOSE"

static bool m_verbose = false;

#define NO_VALUE    -1
#define HAS_VALUE(x)    ((x) != NO_VALUE)

static int m_uid = NO_VALUE;
static int m_gid = NO_VALUE;
static int m_umask = NO_VALUE;

static const char *m_user;
static const char *m_group;
static const char *m_full_name;

static const char *m_user_hook;
static const char *m_root_hook;


static char *
path_join(const char *p1, const char *p2)
{
    char *result;
    if (asprintf(&result, "%s/%s", p1, p2) < 0) {
        errmsg("Failed to allocate path string: %m\n");
        exit(99);
    }
    return result;
}


/* Returns true if scubainit will be changing users */
static bool
should_change_user(void)
{
    if (HAS_VALUE(m_uid)) {
        assert(HAS_VALUE(m_gid));
        return true;
    }

    assert(!HAS_VALUE(m_gid));
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

        bool name_matches = (strcmp(gr->gr_name, name) == 0);
        bool gid_matches = (gr->gr_gid == gid);

        if (name_matches) {
            if (gid_matches) {
                /* Identical name+gid exists; surprising, but no problem */
                result = 0;
                goto out;
            }
            errmsg("Group \"%s\" already exists with different gid in %s\n",
                    name, path);
            goto out;
        }

        if (gid_matches) {
            errmsg("Warning: GID %u already exists in %s\n", gid, path);
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

        bool name_matches = (strcmp(pw->pw_name, name) == 0);
        bool uid_matches = (pw->pw_uid == uid);

        if (name_matches) {
            if (uid_matches) {
                /* Identical name+uid exists; surprising, but no problem */
                result = 0;
                goto out;
            }
            errmsg("User \"%s\" already exists with different uid in %s\n",
                    name, path);
            goto out;
        }

        if (uid_matches) {
            errmsg("Warning: UID %u already exists in %s\n", uid, path);
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
            /* Already exists; we don't really care about its values */
            result = 0;
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
change_user(const char *home)
{
    assert(HAS_VALUE(m_uid));
    assert(HAS_VALUE(m_gid));
    assert(m_user != NULL);

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
    setenv("USER", m_user, 1);
    setenv("LOGNAME", m_user, 1);
    setenv("HOME", home, 1);

    verbose("Changed to uid=%u euid=%u  gid=%u egid=%u\n",
            getuid(), geteuid(), getgid(), getegid());

    return 0;
}

static int
mkdir_p(const char *path, mode_t mode)
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

            if (mkdir(_path, mode) != 0) {
                if (errno != EEXIST)
                    return -1;
            }

            *p = '/';
        }
    }

    if (mkdir(_path, mode) != 0) {
        if (errno != EEXIST)
            return -1;
    }

    return 0;
}

static int
make_homedir(const char *path, unsigned int uid, unsigned int gid)
{
    /* Create the home directory */
    if (mkdir_p(path, 0755) != 0) {
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

    verbose("Created homedir %s\n", path);
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


static void
handle_wait_status(const char *cmd, int wstatus)
{
    if (wstatus < 0) {
        errmsg("Failed to execute %s: %m\n", cmd);
        exit(99);
    }
    else if (WIFEXITED(wstatus)) {
        int es = WEXITSTATUS(wstatus);
        if (es != 0) {
            errmsg("%s exited with status %d\n", cmd, es);
            exit(99);
        }
        // Success
    }
    else if (WIFSIGNALED(wstatus)) {
        int sig = WTERMSIG(wstatus);
        errmsg("%s terminated by signal %d\n", cmd, sig);
        exit(99);
    }
    else {
        errmsg("%s exited for an unknown reason! (wstatus=0x%X)\n", cmd, wstatus);
        exit(99);
    }
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
    handle_wait_status(hook_path, rc);
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
    verbose("%s = %s\n", name, var);
    unsetenv(name);

    return var;
}


static int
process_envvars(void)
{
    int ids_set = 0;

    /* Get the env. vars from scuba */

    /**
     * The following variables are optional, but if any is set,
     * all must be set:
     * - SCUBAINIT_UID
     * - SCUBAINIT_GID
     * - SCUBAINIT_USER
     * - SCUBAINIT_GROUP
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
    if ((m_user = getenv_str_unset(SCUBAINIT_USER)) != NULL) {
        ids_set++;
        m_full_name = m_user;
    }
    if ((m_group = getenv_str_unset(SCUBAINIT_GROUP)) != NULL) {
        ids_set++;
    }
    switch (ids_set) {
        case 0:
        case 4:
            break;
        default:
            errmsg("If any of SCUBAINIT_(UID,GID,USER,GROUP) are set, all must be set.\n");
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
    char *home = NULL;

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

    if (should_change_user()) {
        /* Create user home directory */
        home = path_join(USER_HOME, m_user);
        if (make_homedir(home, m_uid, m_gid) != 0)
            goto fail;

        /* Add scuba user and group */
        if (add_group(ETC_GROUP, m_group, m_gid) != 0)
            goto fail;
        if (add_user(ETC_PASSWD, m_user, m_uid, m_gid,
                    m_full_name, home) != 0)
            goto fail;
        if (add_shadow(ETC_SHADOW, m_user) != 0)
            goto fail;
    }

    /* Call pre-su hook */
    call_hook(m_root_hook);

    /* Handle the scuba user */
    if (should_change_user()) {
        if (change_user(home) < 0)
            goto fail;

        free(home);
        home = NULL;
    }

    if (m_umask >= 0) {
        verbose("Setting umask to 0%o\n", m_umask);
        umask(m_umask);
    }

    /* Call post-su hook, only if we switch users */
    if (should_change_user()) {
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

    errmsg("execvp(\"%s\", ...) failed: %m\n", new_argv[0]);

fail:
    if (home)
        free(home);
    exit(99);
}
