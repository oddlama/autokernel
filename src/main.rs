mod bridge;
mod kconfig_types;
use std::error::Error;

use clap::Parser;

#[derive(Parser, Debug)] // requires `derive` feature
struct Args {
    /// Optional kernel_dir, default /usr/src/linux/
    #[clap(value_name = "DIR", value_hint = clap::ValueHint::DirPath, default_value = "/usr/src/linux/")]
    #[clap(short, long, value_parser, value_name = "DIR", value_hint = clap::ValueHint::DirPath, default_value = "/usr/src/linux/")]
    kernel_dir: std::path::PathBuf,
}

fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();

    println!();
    println!(" ## Building and installing the bridge ##");
    println!();

    let symbols = bridge::run_bridge(args.kernel_dir)?;

    println!();
    println!(" -> Loaded {} symbols.", symbols.symbols.len());

    Ok(())
}
