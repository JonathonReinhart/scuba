use anyhow::{bail, Result};
use std::env;
use std::fs;
use std::path::{Path, PathBuf};


const SCUBAINIT_UID: &str = "SCUBAINIT_UID";
const SCUBAINIT_GID: &str = "SCUBAINIT_GID";
const SCUBAINIT_UMASK: &str = "SCUBAINIT_UMASK";
const SCUBAINIT_USER: &str = "SCUBAINIT_USER";
const SCUBAINIT_GROUP: &str = "SCUBAINIT_GROUP";
const SCUBAINIT_HOOK_USER: &str = "SCUBAINIT_HOOK_USER";
const SCUBAINIT_HOOK_ROOT: &str = "SCUBAINIT_HOOK_ROOT";
const SCUBAINIT_VERBOSE: &str = "SCUBAINIT_VERBOSE";

const USER_HOME: &str = "/home";

fn main() -> Result<()> {
    println!("Hello from scubainit-rs");
    let ctx = process_envvars()?;

    if ctx.should_change_user() {
        ctx.make_homedir()?;
        // TODO: Add group to /etc/group
        // TODO: Add user to /etc/user
        // TODO: Add entry to /etc/shadow
    }

    // Call pre-su hook
    //ctx.call_root_hook()

    // Switch to the requested user
    if ctx.should_change_user() {
        //ctx.change_user();
    }

    if let Some(umask) = ctx.umask {
        // TODO: set umask
    }

    // Call post-su hook, only if we switch users
    if ctx.should_change_user() {
        //ctx.call_user_hook();
    }

    // Exec argv[1] with args argv[1:]

    Ok(())
}

struct Context {
    uid: Option<u32>,
    gid: Option<u32>,
    user: Option<String>,
    group: Option<String>,
    umask: Option<u32>,
    verbose: bool,
    user_hook: Option<String>,
    root_hook: Option<String>,
}

impl Context {
    pub fn should_change_user(&self) -> bool {
        match self.uid {
            Some(_) => {
                assert!(self.gid.is_some());
                assert!(self.user.is_some());
                assert!(self.group.is_some());
                true
            }
            None => {
                assert!(self.gid.is_none());
                assert!(self.user.is_none());
                assert!(self.group.is_none());
                false
            }
        }
    }

    // Should only be called if user is known to be Some
    pub fn home_dir(&self) -> PathBuf {
        let home = Path::new(USER_HOME);
        let user_home = home.join(self.user.as_ref().unwrap());
        user_home
    }

    pub fn make_homedir(&self) -> Result<()> {
        let home = self.home_dir();
        fs::create_dir_all(home)?;

        // TODO

        Ok(())
    }


}

fn process_envvars() -> Result<Context> {
    let mut ids_set = 0;

    // Get the environment variables from scuba.

    // The following variables are optional, but if any is set,
    // all must be set:
    // - SCUBAINIT_UID
    // - SCUBAINIT_GID
    // - SCUBAINIT_USER
    // - SCUBAINIT_GROUP
    let uid = getenv_uint_opt_unset(SCUBAINIT_UID);
    let gid = getenv_uint_opt_unset(SCUBAINIT_GID);
    let user = getenv_str_unset(SCUBAINIT_USER);
    let group = getenv_str_unset(SCUBAINIT_GROUP);

    // TODO: This throws away int parsing errors and treats those vars as unset.

    // TODO: Is there a more idiomatic way to count these?
    ids_set += uid.is_ok() as u32;
    ids_set += gid.is_ok() as u32;
    ids_set += user.is_ok() as u32;
    ids_set += group.is_ok() as u32;

    match ids_set {
        0 => (),
        4 => (),
        _ => {
            bail!("If any of SCUBAINIT_(UID,GID,USER,GROUP) are set, all must be set.");
        },
    }

    // Clear out other env. vars
    env::remove_var("PWD");
    env::remove_var("OLDPWD");
    env::remove_var("XAUTHORITY");

    Ok(Context {
        uid: uid.ok(),
        gid: gid.ok(),
        user: user.ok(),
        group: group.ok(),

        // Optional vars
        umask: getenv_uint_opt_unset(SCUBAINIT_UMASK).ok(),
        verbose: getenv_bool_unset(SCUBAINIT_VERBOSE),

        // Hook scripts
        user_hook: getenv_str_unset(SCUBAINIT_HOOK_USER).ok(),
        root_hook: getenv_str_unset(SCUBAINIT_HOOK_ROOT).ok(),
    })
}

fn getenv_str_unset(name: &str) -> Result<String> {
    let result = env::var(name)?;
    env::remove_var(name);
    Ok(result)
}

fn getenv_bool_unset(name: &str) -> bool {
    let result = env::var(name).is_ok();
    env::remove_var(name);
    result
}

/// Gets an optional uint environment variable, unsetting it.
///
/// # Arguments
///
/// * `name` - A string slice that holds the name of the variable.
///
fn getenv_uint_opt_unset(name: &str) -> Result<u32> {
    let value_str = getenv_str_unset(name)?;
    let value: u32 = value_str.parse()?;
    Ok(value)
}
