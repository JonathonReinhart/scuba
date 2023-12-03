use crate::entfiles::{EntFileReader, EntFileWriter, Entry};
use crate::util::split_csv_str;

#[derive(Debug, Eq, PartialEq)]
pub struct GroupEntry {
    pub name: String,
    pub passwd: String,
    pub gid: u32,
    pub members: Vec<String>,
}

pub type GroupFileReader<'a> = EntFileReader<'a, GroupEntry>;
pub type GroupFileWriter<'a> = EntFileWriter<'a, GroupEntry>;

impl Entry for GroupEntry {
    fn from_line(line: &str) -> Option<GroupEntry> {
        // https://man7.org/linux/man-pages/man5/group.5.html
        //     group_name:password:GID:user_list
        let mut parts = line.split(":");

        Some(GroupEntry {
            name: parts.next()?.to_string(),
            passwd: parts.next()?.to_string(),
            gid: parts.next()?.parse().ok()?,
            members: split_csv_str(parts.next()?),
        })
    }

    fn to_line(&self) -> String {
        format!(
            "{}:{}:{}:{}",
            self.name,
            self.passwd,
            self.gid,
            self.members.join(","),
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::string_vec;

    const SAMPLE_LINE: &str = "foo:x:1234:moe,larry,shemp";

    fn get_sample_ent() -> GroupEntry {
        GroupEntry {
            name: "foo".to_string(),
            passwd: "x".to_string(),
            gid: 1234,
            members: string_vec!["moe", "larry", "shemp"],
        }
    }

    #[test]
    fn from_line_works() -> Result<(), String> {
        let result = GroupEntry::from_line(SAMPLE_LINE).unwrap();
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
