use crate::entfiles::{EntFileReader, EntFileWriter, Entry, ReadEntryError};
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
    fn from_line(line: &str) -> Result<GroupEntry, ReadEntryError> {
        // https://man7.org/linux/man-pages/man5/group.5.html
        //     group_name:password:GID:user_list
        let mut parts = line.split(":");
        let mut next_field = || parts.next().ok_or(ReadEntryError::Invalid);

        Ok(GroupEntry {
            name: next_field()?.to_string(),
            passwd: next_field()?.to_string(),
            gid: next_field()?.parse().map_err(ReadEntryError::ParseInt)?,
            members: split_csv_str(next_field()?),
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
