use anyhow::{bail, Context as _, Result};
use exec::execvp;
use log::{debug, error, info, warn};
use std::env;
use std::fs;
use std::os::unix::fs::{chown, PermissionsExt};
use std::os::unix::process::ExitStatusExt;
use std::path::{Path, PathBuf};
use std::process::{Command, ExitCode};
use stderrlog::{self, LogLevelNum};

use scubainit::util::{libc_result, make_executable, open_read_append};
use scubainit::util::{pop_env_bool, pop_env_str, pop_env_uint};
use scubainit::{groups, passwd, shadow};

const SCUBAINIT_EXIT_FAIL: u8 = 99;

const ETC_PASSWD: &str = "/etc/passwd";
const ETC_GROUP: &str = "/etc/group";
const ETC_SHADOW: &str = "/etc/shadow";
const INVALID_PASSWORD: &str = "x";
const DEFAULT_SHELL: &str = "/bin/bash";

const SCUBAINIT_UID: &str = "SCUBAINIT_UID";
const SCUBAINIT_GID: &str = "SCUBAINIT_GID";
const SCUBAINIT_UMASK: &str = "SCUBAINIT_UMASK";
const SCUBAINIT_USER: &str = "SCUBAINIT_USER";
const SCUBAINIT_GROUP: &str = "SCUBAINIT_GROUP";
const SCUBAINIT_HOOK_USER: &str = "SCUBAINIT_HOOK_USER";
const SCUBAINIT_HOOK_ROOT: &str = "SCUBAINIT_HOOK_ROOT";
const SCUBAINIT_VERBOSE: &str = "SCUBAINIT_VERBOSE";

const USER_HOME: &str = "/home";

fn main() -> ExitCode {
    if let Err(err) = run_scubainit() {
        error!("{err:#}");
        ExitCode::from(SCUBAINIT_EXIT_FAIL)
    } else {
        ExitCode::SUCCESS
    }
}

fn run_scubainit() -> Result<()> {
    setup_logging()?;
    info!("Looking Rusty!");

    let ctx = process_envvars()?;

    if let Some(ref user_info) = ctx.user_info {
        debug!("Setting up user...");
        user_info.make_homedir()?;
        user_info.add_group()?;
        user_info.add_user()?;
        user_info.add_shadow()?;
    };

    // Call pre-su hook
    ctx.call_root_hook()?;

    // Switch to the requested user
    if let Some(ref user_info) = ctx.user_info {
        user_info.change_user()?;
    }
    ctx.set_umask();

    // Call post-su hook, only if we switch users
    if ctx.user_info.is_some() {
        ctx.call_user_hook()?;
    }

    let argv = &env::args_os().skip(1).collect::<Vec<_>>();
    if argv.is_empty() {
        bail!("Missing command");
    }
    let program = &argv[0];
    debug!("Executing program={program:?} with argv={argv:?}");
    // TODO: Use std::os::unix::process::CommandExt::exec() instead?
    // We would want to use the same options to invoke the user hook above, too.
    let result: Result<()> = Err(execvp(program, argv).into());
    result.context(format!("Failed to execute {program:?}"))
}

struct UserInfo {
    uid: u32,
    gid: u32,
    user: String,
    group: String,
}

impl UserInfo {
    pub fn home_dir(&self) -> PathBuf {
        Path::new(USER_HOME).join(&self.user)
    }

    pub fn make_homedir(&self) -> Result<()> {
        let home = self.home_dir();
        debug!("Creating home dir: {home:?}");
        fs::create_dir_all(&home)?;
        fs::set_permissions(&home, fs::Permissions::from_mode(0o700))?;
        chown(&home, Some(self.uid), Some(self.gid))?;
        Ok(())
    }

    pub fn add_group(&self) -> Result<()> {
        let group_name = &self.group;
        let gid = self.gid;

        debug!("Adding group '{group_name}' (gid={gid})");

        let file = open_read_append(ETC_GROUP)?;

        // Try to find a conflicting group (one matching name or gid).
        let mut reader = groups::GroupFileReader::new(file);
        for grp in &mut reader {
            let grp = grp?;
            let name_matches = grp.name.as_str() == group_name;
            let gid_matches = grp.gid == gid;

            if name_matches {
                if gid_matches {
                    // Identical name+gid exists; surprising, but no problem
                    return Ok(());
                }
                bail!("Group {group_name} already exists with different gid in {ETC_GROUP}");
            }

            if gid_matches {
                warn!("Warning: GID {gid} already exists in {ETC_GROUP}");
            }
        }

        let file = reader.into_inner();

        // Okay, add group
        let grp = groups::GroupEntry {
            name: group_name.to_owned(),
            passwd: INVALID_PASSWORD.to_owned(),
            gid,
            members: Vec::new(),
        };
        let mut writer = groups::GroupFileWriter::new(file);
        Ok(writer.write(&grp)?)
    }

    pub fn add_user(&self) -> Result<()> {
        let user_name = &self.user;
        let uid = self.uid;
        debug!("Adding user '{user_name}' (uid={uid})");

        let file = open_read_append(ETC_PASSWD)?;

        // Try to find a conflicting user (one matching name or uid).
        let mut reader = passwd::PasswdFileReader::new(file);
        for pwd in &mut reader {
            let pwd = pwd?;
            let name_matches = pwd.name.as_str() == user_name;
            let uid_matches = pwd.uid == uid;

            if name_matches {
                if uid_matches {
                    // Identical name+uid exists; surprising, but no problem
                    return Ok(());
                }
                bail!("User {user_name} already exists with different uid in {ETC_PASSWD}");
            }

            if uid_matches {
                warn!("Warning: UID {uid} already exists in {ETC_PASSWD}");
            }
        }

        let file = reader.into_inner();

        // Okay, add user
        let home_dir_path = self.home_dir();
        let home_dir_str = home_dir_path.to_str().context("Invalid home_dir")?;
        let user = passwd::PasswdEntry {
            name: user_name.to_owned(),
            passwd: INVALID_PASSWORD.to_owned(),
            uid,
            gid: self.gid,
            gecos: user_name.to_owned(),
            home_dir: home_dir_str.to_owned(),
            shell: DEFAULT_SHELL.to_owned(),
        };
        let mut writer = passwd::PasswdFileWriter::new(file);
        Ok(writer.write(&user)?)
    }

    pub fn add_shadow(&self) -> Result<()> {
        let user_name = &self.user;
        debug!("Adding shadow entry for '{user_name}'");

        let file = open_read_append(ETC_SHADOW)?;

        // Try to find a conflicting user (one matching name).
        let mut reader = shadow::ShadowFileReader::new(file);
        for sp in &mut reader {
            let sp = sp?;
            if sp.name.as_str() == user_name {
                // Already exists; we don't really care about its values
                return Ok(());
            }
        }

        let file = reader.into_inner();

        // Okay, add shadow entry
        let entry = shadow::ShadowEntry {
            name: user_name.to_owned(),
            passwd: INVALID_PASSWORD.to_owned(),
            last_change_date: None,
            min_password_age: None,
            max_password_age: None,
            warn_period: None,
            inact_period: None,
            expire_date: None,
        };
        let mut writer = shadow::ShadowFileWriter::new(file);
        Ok(writer.write(&entry)?)
    }

    pub fn change_user(&self) -> Result<()> {
        let uid = self.uid;
        let gid = self.gid;
        let user = &self.user;
        debug!("Changing to user={user}, uid={uid}, gid={gid}");

        // Drop all supplementary groups. Must be called before setuid().
        // SAFETY: The setgroups() syscall accesses no memory when size is 0.
        //         Calling setgroups(0, NULL) is explicitly supported.
        unsafe {
            libc_result(libc::setgroups(0, std::ptr::null()))?;
        };

        // Change group id. Must be called before setguid().
        // SAFETY: The setgid() syscall uses only its single integer argument.
        unsafe {
            libc_result(libc::setgid(gid))?;
        }

        // Change user id. Must be called last.
        // SAFETY: The setuid() syscall uses only its single integer argument.
        unsafe {
            libc_result(libc::setuid(uid))?;
        }

        // Set other environment variables related to the new user.
        let home_dir_path = self.home_dir();
        let home_dir_str = home_dir_path.to_str().context("Invalid home_dir")?;
        env::set_var("USER", user);
        env::set_var("LOGNAME", user);
        env::set_var("HOME", home_dir_str);

        Ok(())
    }
}

struct Context {
    user_info: Option<UserInfo>,
    umask: Option<u32>,
    user_hook: Option<String>,
    root_hook: Option<String>,
}

impl Context {
    pub fn set_umask(&self) {
        if let Some(umask) = self.umask {
            //  SAFETY: The umask() syscall uses only its single integer argument.
            unsafe {
                libc::umask(umask);
            }
        }
    }

    pub fn call_root_hook(&self) -> Result<()> {
        self.call_hook(&self.root_hook)
    }

    pub fn call_user_hook(&self) -> Result<()> {
        self.call_hook(&self.user_hook)
    }

    fn call_hook(&self, path_str: &Option<String>) -> Result<()> {
        let Some(path) = path_str else {
            return Ok(());
        };

        make_executable(path)?;

        debug!("Executing hook {path}");
        let status = Command::new(path).status()?;
        if !status.success() {
            if let Some(code) = status.code() {
                bail!("{path} exited with status {code}")
            }
            if let Some(signal) = status.signal() {
                bail!("{path} terminated by signal {signal}")
            }
            bail!("{path} exited for an unknown reason! ({status})")
        }
        Ok(())
    }
}

fn process_envvars_user_info() -> Result<Option<UserInfo>> {
    // The following variables are optional, but if any is set, all must be set:
    let uid = pop_env_uint(SCUBAINIT_UID)?;
    let gid = pop_env_uint(SCUBAINIT_GID)?;
    let user = pop_env_str(SCUBAINIT_USER);
    let group = pop_env_str(SCUBAINIT_GROUP);

    let vars_some = [
        uid.is_some(),
        gid.is_some(),
        user.is_some(),
        group.is_some(),
    ];
    match vars_some.into_iter().filter(|b| *b).count() {
        0 => Ok(None),
        n if n == vars_some.len() => Ok(Some(UserInfo {
            // unwrap() won't fail due to is_some() checks above
            uid: uid.unwrap(),
            gid: gid.unwrap(),
            user: user.unwrap(),
            group: group.unwrap(),
        })),
        _ => {
            bail!("If any of SCUBAINIT_{{UID,GID,USER,GROUP}} are set, all must be set.");
        }
    }
}

fn process_envvars() -> Result<Context> {
    // Get the environment variables from scuba.

    // Clear out other env. vars
    env::remove_var("PWD");
    env::remove_var("OLDPWD");
    env::remove_var("XAUTHORITY");

    Ok(Context {
        user_info: process_envvars_user_info()?,

        // Optional vars
        umask: pop_env_uint(SCUBAINIT_UMASK)?,

        // SCUBAINIT_VERBOSE is popped in setup_logging().

        // Hook scripts
        user_hook: pop_env_str(SCUBAINIT_HOOK_USER),
        root_hook: pop_env_str(SCUBAINIT_HOOK_ROOT),
    })
}

fn setup_logging() -> Result<()> {
    let verbose = pop_env_bool(SCUBAINIT_VERBOSE);
    let verbosity = if verbose {
        LogLevelNum::Debug
    } else {
        LogLevelNum::Error
    };

    Ok(stderrlog::new()
        .module(module_path!())
        .show_module_names(true)
        .verbosity(verbosity)
        .init()?)
}
