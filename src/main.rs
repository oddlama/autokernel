mod bridge;
mod kconfig_types;
mod config;

use std::error::Error;

use clap::Parser;
use std::path::PathBuf;

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

    /// Optional kernel_dir, default /usr/src/linux/
    #[clap(short, long, value_parser, value_name = "DIR", value_hint = clap::ValueHint::DirPath, default_value = "/usr/src/linux/")]
    kernel_dir: PathBuf,
}

fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();

    println!("## Loading Config ##");
    let _config = config::load(args.config)?;
    println!("-> Loaded config.");

    println!("## Running the bridge ##");
    let symbols = bridge::run_bridge(args.kernel_dir)?;
    println!("-> Loaded {} symbols.", symbols.symbols.len());


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
    use std::fs;
    use std::env;
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
        .current_dir(&tmp).status().unwrap();
    Command::new("rm")
        .arg("-r")
        .arg(&kernel_version)
        .current_dir(&tmp).status().unwrap();

    // download kernel
    println!("downloading kernel {} ...", kernel_version);
    Command::new("wget")
        .arg("-q")
        .arg(format!("https://cdn.kernel.org/pub/linux/kernel/v5.x/{}", kernel_tar))
        .current_dir(&tmp).status().unwrap();

    println!("extracting kernel {} ...", kernel_version);
    Command::new("tar")
        .arg("-xvf")
        .arg(&kernel_tar)
        .current_dir(&tmp)
        .stdout(Stdio::null())
        .status().unwrap();

    let kernel_dir = tmp.join(kernel_version);

    println!("building and running bridge to extract all symbols");
    let symbols = bridge::run_bridge(kernel_dir).unwrap();

    // remove kernel tar and folder if they already exists
    println!("cleaning up");
    Command::new("rm")
        .arg("-r")
        .arg(&tmp)
        .status().expect("cleanup failed");

    assert!(symbols.symbols.len() > 0)
}
