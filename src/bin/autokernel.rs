use autokernel::bridge::satisfier::SolverConfig;
use autokernel::bridge::{print_satisfy_result, SymbolValue, Tristate};
use autokernel::config::Config;
use autokernel::script;
use autokernel::{
    bridge::{validate_transactions, Bridge},
    config,
};
use itertools::Itertools;

use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

use anyhow::{anyhow, ensure, Context, Ok, Result};
use clap::Parser;
use colored::Colorize;
use tempdir::TempDir;

/// Autokernel is a tool for managing your kernel configuration that guarantees semantic correctness.
/// It checks symbol assignments for validity by creating a native bridge to the kernel's
/// Kconfig interface and ensures that your configuration does not silently break during kernel updates.
/// It can be used to generate a `.config` file, or even to build the kernel.
#[derive(Parser, Debug)]
#[clap(version, about, long_about = None)]
struct Args {
    /// The configuration file to use
    #[clap(short, long, value_name = "FILE", default_value = "/etc/autokernel/config.toml")]
    config: PathBuf,
    /// The kernel directory to operate on
    #[clap(short, long, value_parser, value_name = "DIR", value_hint = clap::ValueHint::DirPath, default_value = "/usr/src/linux")]
    kernel_dir: PathBuf,

    #[clap(subcommand)]
    action: Action,
}

#[derive(Debug, clap::Args)]
struct ActionBuild {
    /// Run make clean before building
    #[clap(short, long)]
    clean: bool,
    /// Install the resulting artifacts after building
    #[clap(short, long)]
    install: bool,
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
    /// Don't apply a config before satisfying, instead run the solver directly with all symbols set to their default values
    #[clap(short, long)]
    ignore_config: bool,
    /// Recursively satisfy dependencies of encountered symbols
    #[clap(short, long)]
    recursive: bool,
}

#[derive(Debug, clap::Subcommand)]
enum Action {
    /// First generate a .config file by applying the autokernel config and afterwards build the
    /// kernel. Additional options may be given to generate an initramfs, integrate it into the
    /// kernel and to install resulting artifacts (make install, make modules_install, ...).
    Build(ActionBuild),
    /// Generate a .config file by applying the autokernel config
    GenerateConfig(ActionGenerateConfig),
    /// Automatically satisfy the dependencies of a given symbol. This will evaluate and
    /// print the necessary changes to other symbols that are required before the given symbol can be set
    Satisfy(ActionSatisfy),
}

fn main() {
    if let Err(err) = try_main() {
        eprintln!("{}: {}", "error".red(), err);
        err.chain()
            .skip(1)
            .for_each(|cause| eprintln!("{}: {}", "because".yellow(), cause));
        std::process::exit(1);
    }
}

fn try_main() -> Result<()> {
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
        script::apply(config.config.script, bridge)?;
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
        Result::Ok(c) if c.is_empty() => println!("Nothing to do :)"),
        _ => print_satisfy_result(&satisfying_configuration),
    };
    Ok(())
}

fn generate_config(args: &Args, bridge: &Bridge, action: &ActionGenerateConfig) -> Result<()> {
    let config = config::load(&args.config)?;
    println!("{:>12} configuration ({})", "Applying".green(), args.config.display());
    script::apply(config.config.script, bridge)?;
    validate_transactions(&bridge.history.borrow())?;

    let output = action.output.clone().unwrap_or_else(|| args.kernel_dir.join(".config"));
    println!("{:>12} kernel config ({})", "Writing".green(), output.display());
    bridge.write_config(output)?;
    Ok(())
}

fn build_kernel(args: &Args, bridge: &Bridge, action: &ActionBuild) -> Result<()> {
    let config = config::load(&args.config)?;
    unsafe { libc::umask(0o022) };

    // Clean output from previous builds if requested
    if action.clean {
        println!("{:>12} `make clean`", "Running".green());
        ensure!(Command::new("make")
            .arg("clean")
            .current_dir(&args.kernel_dir)
            .status()
            .context("Failed to clean")?
            .success());
    }

    script::apply(&config.config.script, bridge)?;
    validate_transactions(&bridge.history.borrow())?;

    let tmpdir = TempDir::new("autokernel")?;
    let config_output = args.kernel_dir.join(".config");
    let initramfs_out = tmpdir.path().join("initramfs.img");

    // If an initramfs is built, ensure that the relevant option is enabled
    if config.initramfs.enable {
        ensure!(
            bridge
                .symbol("BLK_DEV_INITRD")
                .context("Could not find symbol")?
                .get_tristate_value()
                == Tristate::Yes,
            "When using an initramfs, make sure to enable BLK_DEV_INITRD in your config."
        );
    }

    if config.initramfs.enable && config.initramfs.builtin {
        // Setting INITRAMFS_SOURCE manually when using a builtin initramfs
        // makes no sense. Abort if this happens to be the case.
        let mut initramfs_source = bridge.symbol("INITRAMFS_SOURCE").context("Could not find symbol")?;
        ensure!(
            initramfs_source.get_string_value().is_empty(),
            "When using a builtin initramfs, please make sure that INITRAMFS_SOURCE is set to an empty string."
        );

        // Write current config and build kernel once to compile all modules,
        // which are needed for the initramfs generation.
        println!(
            "{:>12} kernel config ({}) [stage 1/2]",
            "Writing".green(),
            config_output.display()
        );
        bridge.write_config(&config_output)?;
        println!("{:>12} `make` [stage 1/2]", "Running".green());
        ensure!(Command::new("make")
            .current_dir(&args.kernel_dir)
            .status()
            .context("Failed to make kernel")?
            .success());

        // Build the initramfs now that the modules are built, and
        // set the INITRAMFS_SOURCE to the output file for the next step
        build_initramfs(args, bridge, &config, tmpdir.path(), &initramfs_out)?;
        initramfs_source.set_value(SymbolValue::String(initramfs_out.to_str().unwrap().to_string()))?;

        // Build kernel again to integrate initramfs into the kernel
        println!(
            "{:>12} kernel config ({}) [stage 2/2]",
            "Writing".green(),
            config_output.display()
        );
        bridge.write_config(&config_output)?;
        println!("{:>12} `make` [stage 2/2]", "Running".green());
        ensure!(Command::new("make")
            .current_dir(&args.kernel_dir)
            .status()
            .context("Failed to make kernel")?
            .success());
    } else {
        println!("{:>12} kernel config ({})", "Writing".green(), config_output.display());
        bridge.write_config(&config_output)?;

        println!("{:>12} `make`", "Running".green());
        ensure!(Command::new("make")
            .current_dir(&args.kernel_dir)
            .status()
            .context("Failed to make kernel")?
            .success());

        if config.initramfs.enable {
            build_initramfs(args, bridge, &config, tmpdir.path(), &initramfs_out)?;
        }
    }

    println!("{:>12} building kernel", "Finished".green());

    if action.install {
        let kernel_version = bridge.get_env("KERNELVERSION").unwrap();
        let replace_variables = |s: &String| -> String { s.replace("{KERNEL_VERSION}", &kernel_version) };

        if config.config.install.enable {
            let out = replace_variables(&config.config.install.path);
            println!("{:>12} config to {}", "Installing".green(), out);
            fs::copy(config_output, out)?;
        }

        if config.initramfs.install.enable && !config.initramfs.builtin {
            let out = replace_variables(&config.initramfs.install.path);
            println!("{:>12} initramfs to {}", "Installing".green(), out);
            fs::copy(initramfs_out, out)?;
        }

        if config.modules.install.enable {
            let out = replace_variables(&config.modules.install.path);
            println!("{:>12} modules to {}", "Installing".green(), out);
            ensure!(Command::new("make")
                .arg("modules_install")
                .arg(format!("INSTALL_MOD_PATH={}", out))
                .current_dir(&args.kernel_dir)
                .status()
                .context("Failed to install modules")?
                .success());
        }

        if config.kernel.install.enable {
            println!("{:>12} kernel with `make install`", "Installing".green());
            ensure!(Command::new("make")
                .arg("install")
                .current_dir(&args.kernel_dir)
                .status()
                .context("Failed to install kernel")?
                .success());
        }

        println!("{:>12} installing kernel", "Finished".green());
    }

    Ok(())
}

fn build_initramfs(args: &Args, bridge: &Bridge, config: &Config, tmpdir: &Path, out: &Path) -> Result<()> {
    let tmpdir_str = tmpdir.to_str().unwrap();
    println!("{:>12} modules to {}", "Installing".green(), tmpdir.display());
    ensure!(Command::new("make")
        .arg("modules_install")
        .arg(format!("INSTALL_MOD_PATH={}", tmpdir_str))
        .current_dir(&args.kernel_dir)
        .status()
        .context("Failed to install modules to temporary directory")?
        .success());

    let kernel_version = bridge.get_env("KERNELVERSION").unwrap();
    let replace_variables = |s: &String| -> String {
        s.replace("{INSTALL_MOD_PATH}", tmpdir_str)
            .replace("{KERNEL_VERSION}", &kernel_version)
            .replace("{OUTPUT}", out.to_str().unwrap())
            .replace(
                "{MODULES_DIR}",
                &format!("{}/lib/modules/{}", tmpdir_str, &kernel_version),
            )
    };

    let command = config.initramfs.command.iter().map(replace_variables).collect_vec();
    println!(
        "{:>12} initramfs with `{}`",
        "Building".green(),
        command.iter().format(" ")
    );
    ensure!(Command::new(&command[0])
        .args(&command[1..])
        .current_dir(&args.kernel_dir)
        .status()
        .context("Failed to build initramfs")?
        .success());
    ensure!(
        out.exists(),
        "Initramfs generator succeeded but {} does not exist",
        out.display()
    );
    Ok(())
}
