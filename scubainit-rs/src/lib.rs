mod entfiles;
pub mod groups;
pub mod passwd;
pub mod shadow;
pub mod util;

/// Create a `Vec<String>` from any number of string literals.
///
/// # Examples
///
/// ```
/// use scubainit::string_vec;
///
/// let stooges = string_vec!["Larry", "Curly", "Moe"];
/// ```
#[macro_export]
macro_rules! string_vec {
    ( $( $str:literal ),* ) => {
        vec![$( $str.to_owned(), )*] as Vec<String>
    };
}
