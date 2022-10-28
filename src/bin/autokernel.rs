use autokernel::bridge::satisfier::SolverConfig;
use autokernel::bridge::{print_satisfy_result, Tristate};
use autokernel::{
    bridge::{validate_transactions, Bridge},
    config,
};

use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::result::Result::Ok as StdOk;

use anyhow::{anyhow, Context, Ok, Result};
use clap::Parser;
use colored::Colorize;

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

#[derive(Debug, clap::Args)]
struct ActionSatisfy {
    /// The symbol to satisfy
    symbol: String,
    /// The value to solve for (either m or y)
    #[clap(default_value = "y")]
    value: String,
    /// Don't load the config before satisfying, instead run the solver directly with all symbols set to their default values
    #[clap(short, long)]
    ignore_config: bool,
    /// Recursively satisfy any encountered dependencies
    #[clap(short, long)]
    recursive: bool,
}

#[derive(Debug, clap::Subcommand)]
enum Action {
    /// Build the kernel using a .config file generated from the autokernel configuration
    Build(ActionBuild),
    /// Generate a .config by applying the autokernel configuration
    GenerateConfig(ActionGenerateConfig),
    /// Automatically Satisfy the dependencies of a given symbol
    Satisfy(ActionSatisfy),
}

fn main() -> Result<()> {
    let args = Args::parse();
    let bridge = Bridge::new(args.kernel_dir.clone())?;

    match &args.action {
        Action::Build(action) => build_kernel(&args, &bridge, action),
        Action::GenerateConfig(action) => generate_config(&args, &bridge, action),
        Action::Satisfy(action) => satisfy_symbol(&args, &bridge, action),
    }
}

fn satisfy_symbol(args: &Args, bridge: &Bridge, action: &ActionSatisfy) -> Result<()> {
    if !action.ignore_config {
        let config = config::load(&args.config)?;
        config.apply_kernel_config(bridge)?;
        validate_transactions(&bridge.history.borrow())?;
    }

    let value: Tristate = action
        .value
        .parse()
        .map_err(|_| anyhow!("Invalid symbol value '{}'", action.value))?;
    println!(
        "Trying to satisfy {}={}...",
        action.symbol.blue(),
        value.to_string().color(value.color())
    );
    let satisfying_configuration = bridge
        .symbol(&action.symbol)
        .context("This symbol doesn't exist")?
        .satisfy(SolverConfig {
            recursive: action.recursive,
            desired_value: value,
            ..SolverConfig::default()
        });

    match satisfying_configuration {
        StdOk(c) if c.is_empty() => println!("Nothing to do :)"),
        _ => print_satisfy_result(&satisfying_configuration),
    };
    Ok(())
}

fn generate_config(args: &Args, bridge: &Bridge, action: &ActionGenerateConfig) -> Result<()> {
    let config = config::load(&args.config)?;
    println!("{:>12} configuration ({})", "Applying".green(), args.config.display());
    config.apply_kernel_config(bridge)?;
    validate_transactions(&bridge.history.borrow())?;

    let output = action.output.clone().unwrap_or(args.kernel_dir.join(".config"));
    println!("{:>12} kernel config ({})", "Writing".green(), output.display());
    bridge.write_config(output)?;
    Ok(())
}

fn build_kernel(args: &Args, bridge: &Bridge, action: &ActionBuild) -> Result<()> {
    let config = config::load(&args.config)?;
    println!(
        "{:>12} kernel using {} {}",
        "Building".green(),
        env!("CARGO_PKG_NAME"),
        env!("CARGO_PKG_VERSION")
    );
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
    validate_transactions(&bridge.history.borrow())?;

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
