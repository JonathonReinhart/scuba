use anyhow::{Context as _, Result};
use std::env;
use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::path::Path;

/// Opens a file for reading and appeneding.
///
/// The file is created if it does not exist.
pub fn open_read_append<P: AsRef<Path>>(path: P) -> std::io::Result<fs::File> {
    fs::File::options()
        .append(true)
        .read(true)
        .create(true)
        .open(path)
}

pub fn short_write() -> std::io::Error {
    std::io::Error::new(std::io::ErrorKind::Other, "Short write")
}

/// Parses a string, or return None if empty.
/// Arguments:
///   input: The string to be parsed.
/// Returns:
///   Err if there was an error parsing the int.
///   Ok(None) if the string was empty.
///   Ok(Some(value)) if the string was a valid int.
pub fn maybe_parse<T: std::str::FromStr>(
    input: &str,
) -> Result<Option<T>, <T as std::str::FromStr>::Err> {
    if input.is_empty() {
        Ok(None)
    } else {
        Ok(Some(input.parse()?))
    }
}

/// Splits a comma-separated string into a vector of strings.
/// Note that an emump input string results in an empty vector
/// (as opposed to a vector with a single empty string element).
pub fn split_csv_str(input: &str) -> Vec<String> {
    if input.len() > 0 {
        input.split(",").map(|x| x.to_string()).collect()
    } else {
        Vec::new()
    }
}

/// Converts an `Option<T>` to a string or empty string
pub fn to_string_or_empty<T: std::fmt::Display>(value: Option<T>) -> String {
    value.map(|x| x.to_string()).unwrap_or_default()
}

/// Converts a libc return value to a Result
pub fn libc_result(rc: libc::c_int) -> std::io::Result<libc::c_int> {
    if rc == -1 {
        Err(std::io::Error::last_os_error())
    } else {
        Ok(rc)
    }
}

/// Gets and unsets an environment variable `name`, or None if it is not set.
pub fn pop_env_str(name: &str) -> Option<String> {
    let result = env::var(name).ok()?;
    env::remove_var(name);
    Some(result)
}

/// Gets and unsets a boolean environment variable `name`.
/// Returns true if the variable is set (to anything), or false otherwise.
pub fn pop_env_bool(name: &str) -> bool {
    let result = env::var(name).is_ok();
    env::remove_var(name);
    result
}

/// Gets and unsets a uint environment variable `name`, or Ok(None) if it is not set.
///
/// # Errors
///
/// This function will return an error if the variable is set, but is not a valid integer string.
pub fn pop_env_uint(name: &str) -> Result<Option<u32>> {
    let value_str = match pop_env_str(name) {
        None => return Ok(None),
        Some(s) => s,
    };
    let value: u32 = value_str
        .parse()
        .context(format!("Parsing integer variable {name}=\"{value_str}\""))?;
    Ok(Some(value))
}

pub fn make_executable(path: &str) -> std::io::Result<()> {
    let mut perms = fs::metadata(path)?.permissions();
    let mut mode = perms.mode();

    // Copy R bits to X
    mode |= (mode & 0o444) >> 2;

    perms.set_mode(mode);
    fs::set_permissions(path, perms)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::string_vec;

    fn not_set(name: &str) -> bool {
        env::var(name).is_err()
    }

    #[test]
    fn maybe_parse_works() {
        assert!(maybe_parse::<u32>("zzz").is_err());
        assert_eq!(maybe_parse::<u32>(""), Ok(None));
        assert_eq!(maybe_parse::<u32>("1234"), Ok(Some(1234)));
    }

    #[test]
    fn split_csv_str_works() {
        assert_eq!(split_csv_str(""), string_vec![]);
        assert_eq!(split_csv_str("abc"), string_vec!["abc"]);
        assert_eq!(
            split_csv_str("abc,def,ghi"),
            string_vec!["abc", "def", "ghi"]
        );
        assert_eq!(
            split_csv_str(",abc,def,ghi"),
            string_vec!["", "abc", "def", "ghi"]
        );
        assert_eq!(
            split_csv_str("abc,def,ghi,"),
            string_vec!["abc", "def", "ghi", ""]
        );
    }

    #[test]
    fn to_string_or_empty_works() {
        assert_eq!(to_string_or_empty::<u32>(None), "");
        assert_eq!(to_string_or_empty(Some(1234)), "1234");
    }

    const VAR_NAME: &str = "TESTVAR";

    #[test]
    fn pop_env_str_works() {
        env::set_var(VAR_NAME, "My string");
        assert_eq!(pop_env_str(VAR_NAME).unwrap(), "My string");
        assert!(not_set(VAR_NAME));
    }

    #[test]
    fn pop_env_str_handles_unset() {
        assert!(not_set(VAR_NAME));
        assert_eq!(pop_env_str(VAR_NAME), None);
    }

    #[test]
    fn pop_env_bool_works() {
        env::set_var(VAR_NAME, "1");
        assert!(pop_env_bool(VAR_NAME));
        assert!(not_set(VAR_NAME));
    }

    #[test]
    fn pop_env_bool_handles_unset() {
        assert!(not_set(VAR_NAME));
        assert!(!pop_env_bool(VAR_NAME));
    }

    #[test]
    fn pop_env_uint_works() {
        env::set_var(VAR_NAME, "1234");
        assert_eq!(pop_env_uint(VAR_NAME).unwrap(), Some(1234));
        assert!(not_set(VAR_NAME));
    }

    #[test]
    fn pop_env_uint_handles_unset() {
        assert!(not_set(VAR_NAME));
        assert_eq!(pop_env_uint(VAR_NAME).unwrap(), None);
    }

    #[test]
    fn pop_env_uint_handles_invalid() {
        env::set_var(VAR_NAME, "zzz");
        assert!(pop_env_uint(VAR_NAME).is_err());
        assert!(not_set(VAR_NAME));
    }
}
