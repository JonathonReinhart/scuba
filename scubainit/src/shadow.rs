use crate::entfiles::{EntFileReader, EntFileWriter, Entry, ReadEntryError};
use crate::util::{maybe_parse, to_string_or_empty};

#[derive(Debug, Eq, PartialEq)]
pub struct ShadowEntry {
    pub name: String,
    pub passwd: String,
    pub last_change_date: Option<u32>,
    pub min_password_age: Option<u32>,
    pub max_password_age: Option<u32>,
    pub warn_period: Option<u32>,
    pub inact_period: Option<u32>,
    pub expire_date: Option<u32>,
    // reserved
}

pub type ShadowFileReader<'a> = EntFileReader<'a, ShadowEntry>;
pub type ShadowFileWriter<'a> = EntFileWriter<'a, ShadowEntry>;

impl Entry for ShadowEntry {
    fn from_line(line: &str) -> Result<ShadowEntry, ReadEntryError> {
        // https://man7.org/linux/man-pages/man5/shadow.5.html
        let mut parts = line.split(":");
        let mut next_field = || parts.next().ok_or(ReadEntryError::Invalid);

        // Any integer parsing errors result in the entire entry being skipped via the final .ok()?
        Ok(ShadowEntry {
            name: next_field()?.to_string(),
            passwd: next_field()?.to_string(),
            last_change_date: maybe_parse(next_field()?).map_err(ReadEntryError::ParseInt)?,
            min_password_age: maybe_parse(next_field()?).map_err(ReadEntryError::ParseInt)?,
            max_password_age: maybe_parse(next_field()?).map_err(ReadEntryError::ParseInt)?,
            warn_period: maybe_parse(next_field()?).map_err(ReadEntryError::ParseInt)?,
            inact_period: maybe_parse(next_field()?).map_err(ReadEntryError::ParseInt)?,
            expire_date: maybe_parse(next_field()?).map_err(ReadEntryError::ParseInt)?,
            // 9th field unused
        })
    }

    fn to_line(&self) -> String {
        format!(
            "{}:{}:{}:{}:{}:{}:{}:{}:",
            self.name,
            self.passwd,
            to_string_or_empty(self.last_change_date),
            to_string_or_empty(self.min_password_age),
            to_string_or_empty(self.max_password_age),
            to_string_or_empty(self.warn_period),
            to_string_or_empty(self.inact_period),
            to_string_or_empty(self.expire_date),
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::matches;

    const SAMPLE_LINE: &str = "joe:*:18881:0:99999:7:::";

    fn get_sample_ent() -> ShadowEntry {
        ShadowEntry {
            name: "joe".to_string(),
            passwd: "*".to_string(),
            last_change_date: Some(18881),
            min_password_age: Some(0),
            max_password_age: Some(99999),
            warn_period: Some(7),
            inact_period: None,
            expire_date: None,
        }
    }

    #[test]
    fn from_line_works() -> Result<(), String> {
        let result = ShadowEntry::from_line(SAMPLE_LINE).unwrap();
        assert_eq!(result, get_sample_ent());
        Ok(())
    }

    #[test]
    fn too_few_fields_none() -> Result<(), String> {
        let line = "joe:*:18881:0:99999:7";
        assert!(ShadowEntry::from_line(line).is_err_and(|e| matches!(e, ReadEntryError::Invalid)));
        Ok(())
    }

    #[test]
    fn invalid_integer_none() -> Result<(), String> {
        let line = "joe:*:18881:0:9999x:7:::";
        assert!(
            ShadowEntry::from_line(line).is_err_and(|e| matches!(e, ReadEntryError::ParseInt(_)))
        );
        Ok(())
    }

    #[test]
    fn to_line_works() -> Result<(), String> {
        let line = get_sample_ent().to_line();
        assert_eq!(line, SAMPLE_LINE);
        Ok(())
    }
}
