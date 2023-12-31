use anyhow::Result;
use std::fs;
use std::io::{BufRead, BufReader};
use std::io::{Read, Seek, Write};

use scubainit::shadow::{ShadowEntry, ShadowFileReader, ShadowFileWriter};
use scubainit::util::open_read_append;

const SAMPLE_LINE: &str = "joe:!:18881:0:99999:7::19876:";

fn get_sample_ent() -> ShadowEntry {
    ShadowEntry {
        name: "joe".to_string(),
        passwd: "!".to_string(),
        last_change_date: Some(18881),
        min_password_age: Some(0),
        max_password_age: Some(99999),
        warn_period: Some(7),
        inact_period: None,
        expire_date: Some(19876),
    }
}

#[test]
fn test_shadow_empty() -> Result<()> {
    let file = fs::File::open("testdata/shadow_empty")?;
    let mut reader = ShadowFileReader::new(file);
    assert!(reader.next().is_none());
    Ok(())
}

#[test]
fn test_shadow1() -> Result<()> {
    let file = fs::File::open("testdata/shadow1")?;
    let mut reader = ShadowFileReader::new(file);

    // root:$y$j9T$zzzzzzzzzzzzzzz:18881:0:99999:7:::
    let result = reader.next().unwrap()?;
    assert_eq!(result.name, "root");
    assert_eq!(result.passwd, "$y$j9T$zzzzzzzzzzzzzzz");
    assert_eq!(result.last_change_date, Some(18881));
    assert_eq!(result.min_password_age, Some(0));
    assert_eq!(result.max_password_age, Some(99999));
    assert_eq!(result.warn_period, Some(7));
    assert_eq!(result.inact_period, None);
    assert_eq!(result.expire_date, None);

    // systemd-timesync:*:18881:0:99999:7:::
    let result = reader.next().unwrap()?;
    assert_eq!(result.name, "systemd-timesync");
    assert_eq!(result.passwd, "*");
    assert_eq!(result.last_change_date, Some(18881));
    assert_eq!(result.min_password_age, Some(0));
    assert_eq!(result.max_password_age, Some(99999));
    assert_eq!(result.warn_period, Some(7));
    assert_eq!(result.inact_period, None);
    assert_eq!(result.expire_date, None);

    assert!(reader.next().is_none());
    Ok(())
}

#[test]
fn test_write() -> Result<()> {
    let file = tempfile::tempfile()?;
    let mut writer = ShadowFileWriter::new(file);
    let ent = get_sample_ent();
    writer.write(&ent)?;

    let mut file = writer.into_inner();
    file.rewind()?;

    let mut buffer = String::with_capacity(128);
    file.read_to_string(&mut buffer)?;

    assert_eq!(buffer, SAMPLE_LINE.to_owned() + "\n");
    Ok(())
}

#[test]
fn test_write_read() -> Result<()> {
    let file = tempfile::tempfile()?;

    let mut writer = ShadowFileWriter::new(file);
    let ent_w = get_sample_ent();
    writer.write(&ent_w)?;

    let mut file = writer.into_inner();
    file.rewind()?;

    let mut reader = ShadowFileReader::new(file);
    let ent_r = reader.next().unwrap()?;

    assert_eq!(ent_w, ent_r);
    Ok(())
}

#[test]
fn test_read_write() -> Result<()> {
    const LINE1: &str = "root:$y$j9T$zzzzzzzzzzzzzzz:18881:0:99999:7:::";
    const LINE2: &str = "systemd-timesync:*:18881:0:99999:7:::";

    // First populate a file with some content
    let mut content = tempfile::NamedTempFile::new()?;
    writeln!(content, "{LINE1}").unwrap();
    writeln!(content, "{LINE2}").unwrap();

    // Process the tempfile
    {
        let file = open_read_append(content.path())?;

        // Now read
        let mut reader = ShadowFileReader::new(file);

        let r = reader.next().unwrap()?;
        assert_eq!(r.name, "root");

        let r = reader.next().unwrap()?;
        assert_eq!(r.name, "systemd-timesync");

        let file = reader.into_inner();

        // Now write
        let mut writer = ShadowFileWriter::new(file);
        let new_ent = get_sample_ent();
        writer.write(&new_ent)?;
    }

    content.rewind()?;

    // Read back the modified file and verify
    let mut content_reader = BufReader::new(content);
    let mut line = String::with_capacity(128);

    line.clear();
    content_reader.read_line(&mut line)?;
    assert_eq!(line.trim_end(), LINE1);

    line.clear();
    content_reader.read_line(&mut line)?;
    assert_eq!(line.trim_end(), LINE2);

    line.clear();
    content_reader.read_line(&mut line)?;
    assert_eq!(line.trim_end(), SAMPLE_LINE);

    Ok(())
}
