use anyhow::{ensure, Context, Error, Result};
use libc::c_char;
use std::collections::HashMap;
use std::ffi::{CStr, CString};
use std::fs;
use std::io::prelude::*;
use std::os::unix::fs::OpenOptionsExt;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

pub struct Transaction {
}

#[derive(Debug)]
pub struct TransactionHistory {
}
