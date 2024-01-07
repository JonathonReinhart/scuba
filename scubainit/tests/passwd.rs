use anyhow::Result;
use std::fs;
use std::io::{BufRead, BufReader};
use std::io::{Read, Seek, Write};

use scubainit::passwd::{PasswdEntry, PasswdFileReader, PasswdFileWriter};
use scubainit::util::open_read_append;

const SAMPLE_LINE: &str = "shemp:x:1003:1003:Shemp Howard:/home/shemp:/bin/fish";

fn get_sample_ent() -> PasswdEntry {
    PasswdEntry {
        name: "shemp".to_string(),
        passwd: "x".to_string(),
        uid: 1003,
        gid: 1003,
        gecos: "Shemp Howard".to_string(),
        home_dir: "/home/shemp".to_string(),
        shell: "/bin/fish".to_string(),
    }
}

#[test]
fn test_passwd_empty() -> Result<()> {
    let file = fs::File::open("testdata/passwd_empty")?;
    let mut reader = PasswdFileReader::new(file);
    assert!(reader.next().is_none());
    Ok(())
}

#[test]
fn test_passwd1() -> Result<()> {
    let file = fs::File::open("testdata/passwd1")?;
    let mut reader = PasswdFileReader::new(file);

    let pw = reader.next().unwrap()?;
    assert_eq!(pw.name, "moe");
    assert_eq!(pw.passwd, "x");
    assert_eq!(pw.uid, 1001);
    assert_eq!(pw.gid, 1001);
    assert_eq!(pw.gecos, "Moe Howard");
    assert_eq!(pw.home_dir, "/home/moe");
    assert_eq!(pw.shell, "/bin/zsh");

    let pw = reader.next().unwrap()?;
    assert_eq!(pw.name, "larry");
    assert_eq!(pw.passwd, "x");
    assert_eq!(pw.uid, 1002);
    assert_eq!(pw.gid, 1002);
    assert_eq!(pw.gecos, "Larry Fine");
    assert_eq!(pw.home_dir, "/home/larry");
    assert_eq!(pw.shell, "/bin/ksh");

    let pw = reader.next().unwrap()?;
    assert_eq!(pw.name, "shemp");
    assert_eq!(pw.passwd, "x");
    assert_eq!(pw.uid, 1003);
    assert_eq!(pw.gid, 1003);
    assert_eq!(pw.gecos, "Shemp Howard");
    assert_eq!(pw.home_dir, "/home/shemp");
    assert_eq!(pw.shell, "/bin/fish");

    assert!(reader.next().is_none());
    Ok(())
}

#[test]
fn test_write() -> Result<()> {
    let file = tempfile::tempfile()?;
    let mut writer = PasswdFileWriter::new(file);
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

    let mut writer = PasswdFileWriter::new(file);
    let ent_w = get_sample_ent();
    writer.write(&ent_w)?;

    let mut file = writer.into_inner();
    file.rewind()?;

    let mut reader = PasswdFileReader::new(file);
    let ent_r = reader.next().unwrap()?;

    assert_eq!(ent_w, ent_r);
    Ok(())
}

#[test]
fn test_read_write() -> Result<()> {
    const LINE1: &str = "moe:x:1001:1001:Moe Howard:/home/moe:/bin/zsh";
    const LINE2: &str = "larry:x:1002:1002:Larry Fine:/home/larry:/bin/ksh";

    // First populate a file with some content
    let mut content = tempfile::NamedTempFile::new()?;
    writeln!(content, "{LINE1}").unwrap();
    writeln!(content, "{LINE2}").unwrap();

    // Process the tempfile
    {
        let file = open_read_append(content.path())?;

        // Now read
        let mut reader = PasswdFileReader::new(file);

        let r = reader.next().unwrap()?;
        assert_eq!(r.name, "moe");

        let r = reader.next().unwrap()?;
        assert_eq!(r.name, "larry");

        let file = reader.into_inner();

        // Now write
        let mut writer = PasswdFileWriter::new(file);
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
