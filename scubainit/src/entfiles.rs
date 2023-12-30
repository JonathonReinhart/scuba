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
// EntFileReader

pub struct EntFileReader<'a, T> {
    reader: BufReader<&'a File>,
    marker: PhantomData<T>, // T must be used
}

impl<T> EntFileReader<'_, T> {
    pub fn new(file: &File) -> EntFileReader<T> {
        EntFileReader {
            reader: BufReader::new(file),
            marker: PhantomData,
        }
    }
}

impl<T: Entry> Iterator for EntFileReader<'_, T> {
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

pub struct EntFileWriter<'a, T> {
    file: &'a File,
    marker: PhantomData<T>, // T must be used
}

impl<T: Entry> EntFileWriter<'_, T> {
    pub fn new(file: &File) -> EntFileWriter<T> {
        EntFileWriter {
            file: file,
            marker: PhantomData,
        }
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
