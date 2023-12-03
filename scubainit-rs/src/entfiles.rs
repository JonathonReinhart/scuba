use std::fs::File;
use std::io::{BufRead, BufReader, Write};
use std::marker::PhantomData;

use crate::util::short_write;

pub trait Entry: Sized {
    fn from_line(line: &str) -> Option<Self>;
    fn to_line(&self) -> String;
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
    type Item = T;

    fn next(&mut self) -> Option<Self::Item> {
        let mut line = String::with_capacity(128);

        loop {
            line.clear();
            if self.reader.read_line(&mut line).ok()? == 0 {
                return None;
            }
            if line.starts_with("#") {
                continue;
            }
            match T::from_line(line.trim_end()) {
                Some(result) => return Some(result),
                None => continue,
            }
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
