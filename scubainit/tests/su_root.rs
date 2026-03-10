// Unit tests for scubainit su-root behavior
//
// Tests for:
// - set_root_passwordless() on shadow files with/without root entry
// - set_root_passwordless() on empty shadow files
// - process_envvars() SCUBAINIT_SU_ROOT env var consumption (via pop_env_bool)
// - Shadow round-trip: non-root entries preserved after modification

use anyhow::Result;
use std::fs;
use std::io::Write;

use scubainit::shadow::{ShadowEntry, ShadowFileReader, ShadowFileWriter};
use scubainit::util::pop_env_bool;

/// Replicates the logic of `set_root_passwordless()` from main.rs,
/// but operates on a given file path instead of the hardcoded `/etc/shadow`.
fn set_root_passwordless_at(path: &std::path::Path) -> Result<()> {
    let file = fs::File::options()
        .append(true)
        .read(true)
        .create(true)
        .open(path)?;
    let reader = ShadowFileReader::new(file);

    let mut entries: Vec<ShadowEntry> = Vec::new();
    let mut found_root = false;

    for entry in reader {
        let mut entry = entry?;
        if entry.name == "root" {
            entry.passwd = String::new();
            found_root = true;
        }
        entries.push(entry);
    }

    if !found_root {
        entries.push(ShadowEntry {
            name: "root".to_string(),
            passwd: String::new(),
            last_change_date: None,
            min_password_age: None,
            max_password_age: None,
            warn_period: None,
            inact_period: None,
            expire_date: None,
        });
    }

    // Rewrite with restrictive permissions
    use std::os::unix::fs::OpenOptionsExt;
    let file = fs::OpenOptions::new()
        .write(true)
        .truncate(true)
        .create(true)
        .mode(0o640)
        .open(path)?;
    let mut writer = ShadowFileWriter::new(file);
    for entry in &entries {
        writer.write(entry)?;
    }
    Ok(())
}

/// Helper: write shadow entries to a temp file.
fn write_shadow_file(path: &std::path::Path, entries: &[ShadowEntry]) -> Result<()> {
    let file = fs::File::create(path)?;
    let mut writer = ShadowFileWriter::new(file);
    for entry in entries {
        writer.write(entry)?;
    }
    Ok(())
}

/// Helper: read all shadow entries from a file.
fn read_shadow_file(path: &std::path::Path) -> Result<Vec<ShadowEntry>> {
    let file = fs::File::open(path)?;
    let reader = ShadowFileReader::new(file);
    reader
        .collect::<std::result::Result<Vec<_>, _>>()
        .map_err(Into::into)
}

// ---------------------------------------------------------------------------
// Tests for set_root_passwordless() with existing root entry
// ---------------------------------------------------------------------------

#[test]
fn test_set_root_passwordless_existing_root_locked() -> Result<()> {
    let dir = tempfile::tempdir()?;
    let shadow_path = dir.path().join("shadow");

    // Shadow file with a locked root entry
    let entries = vec![ShadowEntry {
        name: "root".to_string(),
        passwd: "*".to_string(),
        last_change_date: Some(18881),
        min_password_age: Some(0),
        max_password_age: Some(99999),
        warn_period: Some(7),
        inact_period: None,
        expire_date: None,
    }];
    write_shadow_file(&shadow_path, &entries)?;

    set_root_passwordless_at(&shadow_path)?;

    let result = read_shadow_file(&shadow_path)?;
    assert_eq!(result.len(), 1);
    assert_eq!(result[0].name, "root");
    assert_eq!(result[0].passwd, "");
    // Other fields preserved
    assert_eq!(result[0].last_change_date, Some(18881));
    assert_eq!(result[0].min_password_age, Some(0));
    assert_eq!(result[0].max_password_age, Some(99999));
    assert_eq!(result[0].warn_period, Some(7));
    Ok(())
}

#[test]
fn test_set_root_passwordless_existing_root_hashed() -> Result<()> {
    let dir = tempfile::tempdir()?;
    let shadow_path = dir.path().join("shadow");

    // Shadow file with a hashed root password
    let entries = vec![ShadowEntry {
        name: "root".to_string(),
        passwd: "$y$j9T$zzzzzzzzzzzzzzz".to_string(),
        last_change_date: Some(18881),
        min_password_age: Some(0),
        max_password_age: Some(99999),
        warn_period: Some(7),
        inact_period: None,
        expire_date: None,
    }];
    write_shadow_file(&shadow_path, &entries)?;

    set_root_passwordless_at(&shadow_path)?;

    let result = read_shadow_file(&shadow_path)?;
    assert_eq!(result.len(), 1);
    assert_eq!(result[0].name, "root");
    assert_eq!(result[0].passwd, "");
    Ok(())
}

// ---------------------------------------------------------------------------
// Tests for set_root_passwordless() without root entry
// ---------------------------------------------------------------------------

#[test]
fn test_set_root_passwordless_no_root_entry() -> Result<()> {
    let dir = tempfile::tempdir()?;
    let shadow_path = dir.path().join("shadow");

    // Shadow file with only non-root entries
    let entries = vec![
        ShadowEntry {
            name: "daemon".to_string(),
            passwd: "*".to_string(),
            last_change_date: Some(18881),
            min_password_age: Some(0),
            max_password_age: Some(99999),
            warn_period: Some(7),
            inact_period: None,
            expire_date: None,
        },
        ShadowEntry {
            name: "nobody".to_string(),
            passwd: "!".to_string(),
            last_change_date: Some(18881),
            min_password_age: None,
            max_password_age: None,
            warn_period: None,
            inact_period: None,
            expire_date: None,
        },
    ];
    write_shadow_file(&shadow_path, &entries)?;

    set_root_passwordless_at(&shadow_path)?;

    let result = read_shadow_file(&shadow_path)?;
    assert_eq!(result.len(), 3);

    // Original entries preserved
    assert_eq!(result[0].name, "daemon");
    assert_eq!(result[0].passwd, "*");
    assert_eq!(result[1].name, "nobody");
    assert_eq!(result[1].passwd, "!");

    // New root entry appended with empty password
    assert_eq!(result[2].name, "root");
    assert_eq!(result[2].passwd, "");
    assert_eq!(result[2].last_change_date, None);
    assert_eq!(result[2].min_password_age, None);
    assert_eq!(result[2].max_password_age, None);
    assert_eq!(result[2].warn_period, None);
    assert_eq!(result[2].inact_period, None);
    assert_eq!(result[2].expire_date, None);
    Ok(())
}

// ---------------------------------------------------------------------------
// Tests for set_root_passwordless() on empty shadow file
// ---------------------------------------------------------------------------

#[test]
fn test_set_root_passwordless_empty_file() -> Result<()> {
    let dir = tempfile::tempdir()?;
    let shadow_path = dir.path().join("shadow");

    // Create an empty shadow file
    fs::File::create(&shadow_path)?;

    set_root_passwordless_at(&shadow_path)?;

    let result = read_shadow_file(&shadow_path)?;
    assert_eq!(result.len(), 1);
    assert_eq!(result[0].name, "root");
    assert_eq!(result[0].passwd, "");
    assert_eq!(result[0].last_change_date, None);
    Ok(())
}

// ---------------------------------------------------------------------------
// Tests for process_envvars() SCUBAINIT_SU_ROOT via pop_env_bool
// ---------------------------------------------------------------------------

const SCUBAINIT_SU_ROOT: &str = "SCUBAINIT_SU_ROOT";

#[test]
fn test_pop_env_bool_su_root_set() {
    // When SCUBAINIT_SU_ROOT is set, pop_env_bool returns true and removes it
    temp_env::with_var(SCUBAINIT_SU_ROOT, Some("1"), || {
        assert!(pop_env_bool(SCUBAINIT_SU_ROOT));
        // Env var should be removed after pop
        assert!(std::env::var(SCUBAINIT_SU_ROOT).is_err());
    });
}

#[test]
fn test_pop_env_bool_su_root_unset() {
    // When SCUBAINIT_SU_ROOT is not set, pop_env_bool returns false
    temp_env::with_var_unset(SCUBAINIT_SU_ROOT, || {
        assert!(!pop_env_bool(SCUBAINIT_SU_ROOT));
    });
}

#[test]
fn test_pop_env_bool_su_root_any_value() {
    // pop_env_bool returns true for any value, not just "1"
    temp_env::with_var(SCUBAINIT_SU_ROOT, Some("yes"), || {
        assert!(pop_env_bool(SCUBAINIT_SU_ROOT));
    });
}

#[test]
fn test_pop_env_bool_su_root_empty_value() {
    // pop_env_bool returns true even for empty string (var is set)
    temp_env::with_var(SCUBAINIT_SU_ROOT, Some(""), || {
        assert!(pop_env_bool(SCUBAINIT_SU_ROOT));
    });
}

// ---------------------------------------------------------------------------
// Shadow round-trip: non-root entries preserved after modification
// ---------------------------------------------------------------------------

#[test]
fn test_shadow_round_trip_non_root_preserved() -> Result<()> {
    let dir = tempfile::tempdir()?;
    let shadow_path = dir.path().join("shadow");

    let original_entries = vec![
        ShadowEntry {
            name: "root".to_string(),
            passwd: "!".to_string(),
            last_change_date: Some(18881),
            min_password_age: Some(0),
            max_password_age: Some(99999),
            warn_period: Some(7),
            inact_period: None,
            expire_date: None,
        },
        ShadowEntry {
            name: "systemd-timesync".to_string(),
            passwd: "*".to_string(),
            last_change_date: Some(18881),
            min_password_age: Some(0),
            max_password_age: Some(99999),
            warn_period: Some(7),
            inact_period: None,
            expire_date: None,
        },
        ShadowEntry {
            name: "nobody".to_string(),
            passwd: "!".to_string(),
            last_change_date: Some(18000),
            min_password_age: None,
            max_password_age: None,
            warn_period: None,
            inact_period: Some(30),
            expire_date: Some(19000),
        },
    ];
    write_shadow_file(&shadow_path, &original_entries)?;

    set_root_passwordless_at(&shadow_path)?;

    let result = read_shadow_file(&shadow_path)?;
    assert_eq!(result.len(), 3);

    // Root entry modified
    assert_eq!(result[0].name, "root");
    assert_eq!(result[0].passwd, "");

    // Non-root entries preserved exactly
    assert_eq!(result[1], original_entries[1]);
    assert_eq!(result[2], original_entries[2]);
    Ok(())
}

#[test]
fn test_shadow_round_trip_many_entries() -> Result<()> {
    let dir = tempfile::tempdir()?;
    let shadow_path = dir.path().join("shadow");

    let original_entries = vec![
        ShadowEntry {
            name: "root".to_string(),
            passwd: "$6$rounds=5000$saltsalt$hash".to_string(),
            last_change_date: Some(19000),
            min_password_age: Some(1),
            max_password_age: Some(90),
            warn_period: Some(14),
            inact_period: Some(7),
            expire_date: Some(20000),
        },
        ShadowEntry {
            name: "alice".to_string(),
            passwd: "x".to_string(),
            last_change_date: Some(18500),
            min_password_age: Some(0),
            max_password_age: Some(99999),
            warn_period: Some(7),
            inact_period: None,
            expire_date: None,
        },
        ShadowEntry {
            name: "bob".to_string(),
            passwd: "!!".to_string(),
            last_change_date: None,
            min_password_age: None,
            max_password_age: None,
            warn_period: None,
            inact_period: None,
            expire_date: None,
        },
        ShadowEntry {
            name: "charlie".to_string(),
            passwd: "*".to_string(),
            last_change_date: Some(18000),
            min_password_age: Some(0),
            max_password_age: Some(365),
            warn_period: Some(30),
            inact_period: Some(60),
            expire_date: None,
        },
    ];
    write_shadow_file(&shadow_path, &original_entries)?;

    set_root_passwordless_at(&shadow_path)?;

    let result = read_shadow_file(&shadow_path)?;
    assert_eq!(result.len(), 4);

    // Root password cleared, other fields preserved
    assert_eq!(result[0].name, "root");
    assert_eq!(result[0].passwd, "");
    assert_eq!(result[0].last_change_date, Some(19000));
    assert_eq!(result[0].inact_period, Some(7));
    assert_eq!(result[0].expire_date, Some(20000));

    // All non-root entries preserved exactly
    assert_eq!(result[1], original_entries[1]);
    assert_eq!(result[2], original_entries[2]);
    assert_eq!(result[3], original_entries[3]);
    Ok(())
}

#[test]
fn test_shadow_round_trip_from_raw_file() -> Result<()> {
    let dir = tempfile::tempdir()?;
    let shadow_path = dir.path().join("shadow");

    // Write raw shadow content like a real /etc/shadow file
    {
        let mut file = fs::File::create(&shadow_path)?;
        writeln!(file, "root:*:18881:0:99999:7:::")?;
        writeln!(file, "daemon:*:18881:0:99999:7:::")?;
        writeln!(file, "bin:*:18881:0:99999:7:::")?;
    }

    set_root_passwordless_at(&shadow_path)?;

    let result = read_shadow_file(&shadow_path)?;
    assert_eq!(result.len(), 3);

    assert_eq!(result[0].name, "root");
    assert_eq!(result[0].passwd, "");

    assert_eq!(result[1].name, "daemon");
    assert_eq!(result[1].passwd, "*");

    assert_eq!(result[2].name, "bin");
    assert_eq!(result[2].passwd, "*");
    Ok(())
}
