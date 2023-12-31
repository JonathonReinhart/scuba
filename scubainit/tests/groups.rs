use anyhow::Result;
use std::fs;
use std::io::{BufRead, BufReader};
use std::io::{Read, Seek, Write};

use scubainit::groups::{GroupEntry, GroupFileReader, GroupFileWriter};
use scubainit::string_vec;
use scubainit::util::open_read_append;

const SAMPLE_LINE: &str = "snap:x:3456:crackle,pop";

fn get_sample_ent() -> GroupEntry {
    GroupEntry {
        name: "snap".to_string(),
        passwd: "x".to_string(),
        gid: 3456,
        members: string_vec!["crackle", "pop"],
    }
}

#[test]
fn test_group_empty() -> Result<()> {
    let file = fs::File::open("testdata/group_empty")?;
    let mut reader = GroupFileReader::new(file);
    assert!(reader.next().is_none());
    Ok(())
}

#[test]
fn test_group1() -> Result<()> {
    let file = fs::File::open("testdata/group1")?;
    let mut reader = GroupFileReader::new(file);

    let g = reader.next().unwrap()?;
    assert_eq!(g.name, "foo");
    assert_eq!(g.passwd, "x");
    assert_eq!(g.gid, 1234);
    assert_eq!(g.members.as_slice(), ["moe", "larry", "shemp"]);

    let g = reader.next().unwrap()?;
    assert_eq!(g.name, "bar");
    assert_eq!(g.passwd, "x");
    assert_eq!(g.gid, 2345);
    assert_eq!(g.members.as_slice(), ["moe"]);

    let g = reader.next().unwrap()?;
    assert_eq!(g.name, "snap");
    assert_eq!(g.passwd, "x");
    assert_eq!(g.gid, 3456);
    assert_eq!(g.members.as_slice(), [] as [&str; 0]);

    assert!(reader.next().is_none());
    Ok(())
}

#[test]
fn test_write() -> Result<()> {
    let file = tempfile::tempfile()?;
    let mut writer = GroupFileWriter::new(file);

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

    let mut writer = GroupFileWriter::new(file);
    let ent_w = get_sample_ent();
    writer.write(&ent_w)?;

    let mut file = writer.into_inner();
    file.rewind()?;

    let mut reader = GroupFileReader::new(file);
    let ent_r = reader.next().unwrap()?;

    assert_eq!(ent_w, ent_r);
    Ok(())
}

#[test]
fn test_read_write() -> Result<()> {
    const LINE1: &str = "foo:x:1234:moe,larry,shemp";
    const LINE2: &str = "bar:x:2345:moe";

    // First populate a file with some content
    let mut content = tempfile::NamedTempFile::new()?;
    writeln!(content, "{LINE1}").unwrap();
    writeln!(content, "{LINE2}").unwrap();

    // Process the tempfile
    {
        let file = open_read_append(content.path())?;

        // Now read
        let mut reader = GroupFileReader::new(file);

        let r = reader.next().unwrap()?;
        assert_eq!(r.name, "foo");

        let r = reader.next().unwrap()?;
        assert_eq!(r.name, "bar");

        let file = reader.into_inner();

        // Now write
        let mut writer = GroupFileWriter::new(file);
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
