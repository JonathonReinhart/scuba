use crate::entfiles::{EntFileReader, EntFileWriter, EntLineParser, Entry, ReadEntryError};
use crate::util::split_csv_str;

#[derive(Debug, Eq, PartialEq)]
pub struct GroupEntry {
    pub name: String,
    pub passwd: String,
    pub gid: u32,
    pub members: Vec<String>,
}

pub type GroupFileReader = EntFileReader<GroupEntry>;
pub type GroupFileWriter = EntFileWriter<GroupEntry>;

impl Entry for GroupEntry {
    fn from_line(line: &str) -> Result<GroupEntry, ReadEntryError> {
        // https://man7.org/linux/man-pages/man5/group.5.html
        //     group_name:password:GID:user_list
        let mut parser = EntLineParser::new(line);
        Ok(GroupEntry {
            name: parser.next_field_string()?,
            passwd: parser.next_field_string()?,
            gid: parser.next_field_u32()?,
            members: split_csv_str(parser.next_field_str()?),
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
