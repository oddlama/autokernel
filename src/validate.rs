use crate::kconfig_types::{Symbol, Symbols};
use std::{
    fs::File,
    io::{BufRead, BufReader},
    path::PathBuf,
};

fn get_symbol_by_name<'a>(symbols: &'a Symbols, name: &'a str) -> Option<&'a Symbol> {
    for s in &symbols.symbols {
        if let Some(n) = &s.name {
            if n == name {
                return Some(s);
            }
        }
    }
    None
}

fn validate_line(symbols: &Symbols, line: &str) {
    let mut parts = line.split('=');
    let name: &str = parts.next().expect("Couldn't get name from config line");
    let value = parts
        .next()
        .expect(&format!("Couldn't get value from config line '{:?}'", line));
    let value = value.trim();
    let name = name.trim().strip_prefix("CONFIG_").expect("Malformed name");
    if name.len() == 0 || value.len() == 0 {
        panic!("Couldn't parse line: {:?}", line);
    }
    let symbol = get_symbol_by_name(symbols, &name);
    if symbol.is_none() {
        panic!("Couldn't find symbol by name: {:?}", name)
    }
}

pub fn validate_dotconfig(symbols: &Symbols, kernel_config: &PathBuf) {
    let config_file = File::open(kernel_config).expect("Couldn't open kernel config file");

    for line in BufReader::new(config_file).lines() {
        if let Ok(line) = line {
            let line = line.trim();
            if line.len() == 0 || line.trim().starts_with("#") {
                continue;
            }
            validate_line(symbols, line);
        }
    }
}
