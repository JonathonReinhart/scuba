#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
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
#define verbose(fmt, ...)    errmsg(fmt, ##__VA_ARGS__)

#define ETC_PASSWD          "/etc/passwd"
#define ETC_GROUP           "/etc/group"
#define ETC_SHADOW          "/etc/shadow"
#define INVALID_PASSWORD    "x"

#define SCUBA_USER          "scubauser"
#define SCUBA_GROUP         "scubauser"
#define SCUBA_USER_FULLNAME "Scuba User"

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
         const char *gecos)
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
        .pw_dir     = "/",          /* Docker sets $HOME=/ */
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

    /* Add scuba user and group */
    if (add_group(ETC_GROUP, SCUBA_GROUP, m_gid) != 0)
        exit(99);
    if (add_user(ETC_PASSWD, SCUBA_USER, m_uid, m_gid, SCUBA_USER_FULLNAME) != 0)
        exit(99);
    if (add_shadow(ETC_SHADOW, SCUBA_USER) != 0)
        exit(99);


    /* Prepare for execution of user command */
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
