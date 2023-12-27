use crate::entfiles::{EntFileReader, EntFileWriter, Entry};

#[derive(Debug, Eq, PartialEq)]
pub struct PasswdEntry {
    pub name: String,
    pub passwd: String,
    pub uid: u32,
    pub gid: u32,
    pub gecos: String, // TODO: Vec<String> or struct
    pub home_dir: String,
    pub shell: String, // TODO: Option<String>
}

pub type PasswdFileReader<'a> = EntFileReader<'a, PasswdEntry>;
pub type PasswdFileWriter<'a> = EntFileWriter<'a, PasswdEntry>;

impl Entry for PasswdEntry {
    fn from_line(line: &str) -> Option<PasswdEntry> {
        // https://man7.org/linux/man-pages/man5/passwd.5.html
        //   name:password:UID:GID:GECOS:directory:shell
        let mut parts = line.split(":");

        Some(PasswdEntry {
            name: parts.next()?.to_string(),
            passwd: parts.next()?.to_string(),
            uid: parts.next()?.parse().ok()?,
            gid: parts.next()?.parse().ok()?,
            gecos: parts.next()?.to_string(),
            home_dir: parts.next()?.to_string(),
            shell: parts.next()?.to_string(),
        })
    }

    fn to_line(&self) -> String {
        format!(
            "{}:{}:{}:{}:{}:{}:{}",
            self.name, self.passwd, self.uid, self.gid, self.gecos, self.home_dir, self.shell,
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const SAMPLE_LINE: &str = "joe:x:1234:5678:Joe Blow:/home/joe:/bin/bash";

    fn get_sample_ent() -> PasswdEntry {
        PasswdEntry {
            name: "joe".to_string(),
            passwd: "x".to_string(),
            uid: 1234,
            gid: 5678,
            gecos: "Joe Blow".to_string(),
            home_dir: "/home/joe".to_string(),
            shell: "/bin/bash".to_string(),
        }
    }

    #[test]
    fn from_line_works() -> Result<(), String> {
        let result = PasswdEntry::from_line(SAMPLE_LINE).unwrap();
        assert_eq!(result, get_sample_ent());
        Ok(())
    }

    #[test]
    fn to_line_works() -> Result<(), String> {
        let line = get_sample_ent().to_line();
        assert_eq!(line, SAMPLE_LINE);
        Ok(())
    }
}
