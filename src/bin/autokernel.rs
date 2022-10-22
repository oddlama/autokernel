use autokernel::{bridge::{Bridge, validate_transactions}, config::{self, Config}};

use std::path::PathBuf;
use std::process::{Command, Stdio};

use anyhow::{Ok, Result};
use clap::Parser;

#[derive(Parser, Debug)]
#[clap(version, about, long_about = None)]
struct Args {
    /// The configuration file to use
    #[clap(short, long, value_name = "FILE", default_value = "config.lua")]
    config: PathBuf,

    /// kernel_dir, default /usr/src/linux/
    #[clap(short, long, value_parser, value_name = "DIR", value_hint = clap::ValueHint::DirPath, default_value = "/usr/src/linux/")]
    kernel_dir: PathBuf,

    #[clap(subcommand)]
    action: Action,
}

#[derive(Debug, clap::Args)]
struct ActionBuild {
    /// Run make clean before building
    #[clap(short, long)]
    clean: bool,
}

#[derive(Debug, clap::Args)]
struct ActionGenerateConfig {
    /// The output file, defaults to {kernel_dir}/.config if not given.
    #[clap(short, long, value_parser, value_name = "DIR", value_hint = clap::ValueHint::FilePath)]
    output: Option<PathBuf>,
}

#[derive(Debug, clap::Subcommand)]
enum Action {
    Build(ActionBuild),
    GenerateConfig(ActionGenerateConfig),
}

fn main() -> Result<()> {
    let args = Args::parse();
    let mut config = config::load(&args.config)?;
    let bridge = Bridge::new(args.kernel_dir.clone())?;

    match &args.action {
        Action::Build(action) => build_kernel(&args, config.as_mut(), &bridge, action),
        Action::GenerateConfig(action) => generate_config(&args, config.as_mut(), &bridge, action),
    }
}

fn generate_config(args: &Args, config: &mut dyn Config, bridge: &Bridge, action: &ActionGenerateConfig) -> Result<()> {
    println!("Generating config...");
    config.apply_kernel_config(bridge)?;

    // Write to given output file or fallback to .config in the kernel directory
    let output = action.output.clone().unwrap_or(args.kernel_dir.join(".config"));
    bridge.write_config(output)?;
    Ok(())
}

fn build_kernel(args: &Args, config: &mut dyn Config, bridge: &Bridge, action: &ActionBuild) -> Result<()> {
    println!("Building kernel...");
    // umask 022 // do we want this from the config?

    // Clean output from previous builds if requested
    if action.clean {
        // run "make clean" in the kernel folder
        println!(">> make clean");
        Command::new("make")
            .arg("clean")
            .current_dir(&args.kernel_dir)
            .stderr(Stdio::inherit())
            .output()
            .expect("make clean failed");
    }

    config.apply_kernel_config(bridge)?;
    validate_transactions(bridge, &bridge.history.borrow())?;

    let output = args.kernel_dir.join(".config");
    bridge.write_config(output)?;

    // make

    // if config.initramfs {
    //   initramfs build
    //   initramfs integrate
    //   make
    // }

    // if action.install {
    //    // make modules_install
    // }

    Ok(())
}
