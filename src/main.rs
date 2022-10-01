use autokernel::config::run_lua;
use autokernel::bridge::{Bridge, Tristate};

use std::process::{Command, Stdio};
use std::path::PathBuf;

use anyhow::{Context, Ok, Result};
use clap::Parser;

#[derive(Parser, Debug)]
struct Args {
    /// config
    #[clap(short, long, value_name = "FILE", default_value = "config.lua")]
    config: PathBuf,

    /// Optional kernel_dir, default /usr/src/linux/
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
    /// Run make clean before building
    #[clap(short, long)]
    clean: bool,
}

#[derive(Debug, clap::Subcommand)]
enum Action {
    Build(ActionBuild),
    GenerateConfig(ActionGenerateConfig),
}

fn main() -> Result<()> {
    let args = Args::parse();
    let bridge = Bridge::new(args.kernel_dir.clone())?;

    match &args.action {
        Action::Build(action) => build_kernel(&args, &bridge, action)?,
        Action::GenerateConfig(action) => generate_config(&args, &bridge, action)?,
    };
    Ok(())
}

fn build_kernel(args: &Args, bridge: &Bridge, action: &ActionBuild) -> Result<()> {
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

    run_lua(bridge, "build.lua")?;
    bridge.write_config(".config")?;

    Ok(())
}
