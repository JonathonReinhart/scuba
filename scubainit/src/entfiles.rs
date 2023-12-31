use std::fs::File;
use std::io::{BufRead, BufReader, Write};
use std::marker::PhantomData;

use crate::util::short_write;

pub trait Entry: Sized {
    fn from_line(line: &str) -> Result<Self, ReadEntryError>;
    fn to_line(&self) -> String;
}

////////////////////////////////////////////////////////////////////////////////
// ReadEntryError

#[derive(Debug)]
pub enum ReadEntryError {
    Io(std::io::Error),
    ParseInt(std::num::ParseIntError),
    Invalid,
}

impl std::fmt::Display for ReadEntryError {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        match *self {
            // The wrapped error contains additional information and is available
            // via the source() method.
            ReadEntryError::Io(_) => write!(f, "error reading entry from file"),

            ReadEntryError::ParseInt(..) => write!(f, "an integer field could not be parsed"),

            ReadEntryError::Invalid => write!(f, "the entry line is invalid"),
        }
    }
}

impl std::error::Error for ReadEntryError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match *self {
            ReadEntryError::Io(ref e) => Some(e),
            ReadEntryError::ParseInt(ref e) => Some(e),
            _ => None,
        }
    }
}

////////////////////////////////////////////////////////////////////////////////
// EntLineParser

pub struct EntLineParser<'a> {
    fields: std::str::Split<'a, char>,
}

impl<'a> EntLineParser<'a> {
    pub fn new(line: &str) -> EntLineParser {
        EntLineParser {
            fields: line.split(':'),
        }
    }

    pub fn next_field_str(&mut self) -> Result<&'a str, ReadEntryError> {
        self.fields.next().ok_or(ReadEntryError::Invalid)
    }

    pub fn next_field_string(&mut self) -> Result<String, ReadEntryError> {
        self.next_field_str().map(|s| s.to_string())
    }

    pub fn next_field_u32(&mut self) -> Result<u32, ReadEntryError> {
        self.next_field_str()?
            .parse::<u32>()
            .map_err(ReadEntryError::ParseInt)
    }

    pub fn next_field_u32_opt(&mut self) -> Result<Option<u32>, ReadEntryError> {
        let value = self.next_field_str()?;
        if value.is_empty() {
            Ok(None)
        } else {
            Ok(Some(
                value.parse::<u32>().map_err(ReadEntryError::ParseInt)?,
            ))
        }
    }
}

////////////////////////////////////////////////////////////////////////////////
// EntFileReader

pub struct EntFileReader<T> {
    reader: BufReader<File>,
    marker: PhantomData<T>, // T must be used
}

impl<T> EntFileReader<T> {
    pub fn new(file: File) -> EntFileReader<T> {
        EntFileReader {
            reader: BufReader::new(file),
            marker: PhantomData,
        }
    }

    /// Unwraps this `EntFileReader<T>`, returning the underlying File.
    ///
    /// Note that the position of the File is undefined.
    pub fn into_inner(self) -> File {
        self.reader.into_inner()
    }
}

impl<T: Entry> Iterator for EntFileReader<T> {
    type Item = Result<T, ReadEntryError>;

    fn next(&mut self) -> Option<Self::Item> {
        let mut line = String::with_capacity(128);

        loop {
            line.clear();
            let n = match self.reader.read_line(&mut line) {
                Err(err) => return Some(Err(ReadEntryError::Io(err))),
                Ok(n) => n,
            };
            if n == 0 {
                return None; // EOF
            }
            if line.starts_with("#") {
                continue;
            }
            let line = line.trim_end();
            if line.len() == 0 {
                continue;
            }
            return Some(T::from_line(line));
        }
    }
}

////////////////////////////////////////////////////////////////////////////////
// EntFileWriter

pub struct EntFileWriter<T> {
    file: File,
    marker: PhantomData<T>, // T must be used
}

impl<T: Entry> EntFileWriter<T> {
    pub fn new(file: File) -> EntFileWriter<T> {
        EntFileWriter {
            file: file,
            marker: PhantomData,
        }
    }

    /// Unwraps this `EntFileWriter<T>`, returning the underlying File.
    ///
    /// Note that the position of the File is undefined.
    pub fn into_inner(self) -> File {
        self.file
    }

    pub fn write(&mut self, entry: &T) -> std::io::Result<()> {
        let line = entry.to_line() + "\n";
        let data = line.as_bytes();
        let written = self.file.write(data)?;
        if written != data.len() {
            return Err(short_write());
        }
        Ok(())
    }
}

////////////////////////////////////////////////////////////////////////////////
// tests

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn next_field_str_works() -> Result<(), String> {
        let mut parser = EntLineParser::new("aaa:bbb");
        assert_eq!(parser.next_field_str().unwrap(), "aaa");
        assert_eq!(parser.next_field_str().unwrap(), "bbb");
        assert!(parser
            .next_field_str()
            .is_err_and(|e| matches!(e, ReadEntryError::Invalid)));
        Ok(())
    }

    #[test]
    fn next_field_string_works() -> Result<(), String> {
        let mut parser = EntLineParser::new("aaa:bbb");
        assert_eq!(parser.next_field_string().unwrap(), "aaa");
        assert_eq!(parser.next_field_string().unwrap(), "bbb");
        assert!(parser
            .next_field_string()
            .is_err_and(|e| matches!(e, ReadEntryError::Invalid)));
        Ok(())
    }

    #[test]
    fn next_field_u32_works() -> Result<(), String> {
        let mut parser = EntLineParser::new("123:456:7zz");
        assert_eq!(parser.next_field_u32().unwrap(), 123);
        assert_eq!(parser.next_field_u32().unwrap(), 456);
        assert!(parser
            .next_field_u32()
            .is_err_and(|e| matches!(e, ReadEntryError::ParseInt(_))));
        Ok(())
    }

    #[test]
    fn next_field_u32_opt_works() -> Result<(), String> {
        let mut parser = EntLineParser::new("xxx::");
        assert_eq!(parser.next_field_str().unwrap(), "xxx");
        assert_eq!(parser.next_field_u32_opt().unwrap(), None);
        assert_eq!(parser.next_field_u32_opt().unwrap(), None);
        Ok(())
    }
}
