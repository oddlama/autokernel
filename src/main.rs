mod bridge;
mod config;
mod kconfig_types;
mod validate;

use std::{collections::HashSet, error::Error};

use clap::Parser;
use kconfig_types::Symbols;
use std::path::PathBuf;

use crate::kconfig_types::{Direction, Expr};

#[derive(Parser, Debug)] // requires `derive` feature
struct Args {
    /// config toml
    #[clap(short, long, value_name = "FILE", default_value = "config.toml")]
    config: PathBuf,

    /// build flag
    #[clap(short, long)]
    build: bool,

    /// build flag
    #[clap(short, long)]
    interactive: bool,

    /// config toml
    #[clap(short, long, value_name = "FILE", default_value = ".config")]
    validate: PathBuf,

    /// Optional kernel_dir, default /usr/src/linux/
    #[clap(short, long, value_parser, value_name = "DIR", value_hint = clap::ValueHint::DirPath, default_value = "/usr/src/linux/")]
    kernel_dir: PathBuf,
}

fn print_smybol_types(symbols: &Symbols) {
    let mut sym_types = HashSet::<&String>::new();
    let mut prop_types = HashSet::<&String>::new();
    let mut expr_types = HashSet::<&String>::new();

    for sym in &symbols.symbols {
        sym_types.insert(&sym.typ);
        for prop in &sym.properties {
            prop_types.insert(&prop.typ);
            let mut exprs: Vec<Option<&Expr>> = vec![prop.expr.as_ref()];
            while let Some(Some(e)) = exprs.pop() {
                expr_types.insert(&e.typ);
                if let Direction::There(ex) = &e.left {
                    exprs.push(Some(ex));
                }
                if let Direction::There(ex) = &e.right {
                    exprs.push(Some(ex));
                }
            }
        }
    }

    println!();
    for t in &sym_types {
        println!("sym type {:?}", t);
    }
    println!();
    for t in &prop_types {
        println!("prop type {:?}", t);
    }
    println!();
    for t in &expr_types {
        println!("expr type {:?}", t);
    }
}

fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();

    println!("## Loading Config ##");
    let _config = config::load(args.config)?;
    println!("-> Loaded config.");

    println!("## Running the bridge ##");
    let symbols = bridge::run_bridge(args.kernel_dir)?;
    println!("-> Loaded {} symbols.", symbols.symbols.len());

    print_smybol_types(&symbols);

    if args.validate.exists() {
        println!("## Validating the kernel config ##");
        validate::validate_dotconfig(&symbols, &args.validate);
    }

    //let kconfig = kconfig_types::Kconfig::from_toml(&config.config);
    //println!("-> Loaded {} Kconfigs.", kconfig

    if args.build {
        println!("Build mode not supported yet");
        // Merge configs
        // Build kernel
        // Build modules
        // Build initramfs
    } else {
        println!("Config mode not supported yet")
    }

    Ok(())
}

// TODO extract into test file (needs lib setup for it)
// TODO use test_env_logger

#[test]
fn test_parse_args() {
    let args = Args::parse();

    assert_eq!(args.kernel_dir, PathBuf::from("/usr/src/linux/"))
}

#[test]
fn integrationtest_parse_symbols() {
    use std::env;
    use std::fs;
    use std::process::{Command, Stdio};

    let tmp = env::temp_dir().join("autokernel-test");
    println!("creating {} directory", &tmp.display());
    fs::create_dir_all(&tmp).unwrap();

    // latest="$(curl -s https://www.kernel.org/ | grep -A1 'stable:' | grep -oP '(?<=strong>).*(?=</strong.*)' | head -1)"
    let kernel_version = "linux-5.19.1";
    let kernel_tar = format!("{}.tar.xz", kernel_version);

    // remove kernel tar and folder if they already exists
    println!("cleaning previous test if exists");
    Command::new("rm")
        .arg(&kernel_tar)
        .current_dir(&tmp)
        .status()
        .unwrap();
    Command::new("rm")
        .arg("-r")
        .arg(&kernel_version)
        .current_dir(&tmp)
        .status()
        .unwrap();

    // download kernel
    println!("downloading kernel {} ...", kernel_version);
    Command::new("wget")
        .arg("-q")
        .arg(format!(
            "https://cdn.kernel.org/pub/linux/kernel/v5.x/{}",
            kernel_tar
        ))
        .current_dir(&tmp)
        .status()
        .unwrap();

    println!("extracting kernel {} ...", kernel_version);
    Command::new("tar")
        .arg("-xvf")
        .arg(&kernel_tar)
        .current_dir(&tmp)
        .stdout(Stdio::null())
        .status()
        .unwrap();

    let kernel_dir = tmp.join(kernel_version);

    println!("building and running bridge to extract all symbols");
    let symbols = bridge::run_bridge(kernel_dir).unwrap();

    // remove kernel tar and folder if they already exists
    println!("cleaning up");
    Command::new("rm")
        .arg("-r")
        .arg(&tmp)
        .status()
        .expect("cleanup failed");

    assert!(symbols.symbols.len() > 0)
}
