mod bridge;
mod config;
mod colors;

use std::{
    error::Error,
    process::{Command, Stdio},
};

use clap::Parser;
use std::path::PathBuf;

use crate::bridge::{Bridge, Tristate};
use colored::Colorize;
use colors::*;


const VERSION: &'static str = env!("CARGO_PKG_VERSION");

#[derive(Parser, Debug)] // requires `derive` feature
struct Args {
    /// config toml
    #[clap(short, long, value_name = "FILE", default_value = "config.toml")]
    config: PathBuf,

    /// Optional kernel_dir, default /usr/src/linux/
    #[clap(short, long, value_parser, value_name = "DIR", value_hint = clap::ValueHint::DirPath, default_value = "/usr/src/linux/")]
    kernel_dir: PathBuf,

    #[clap(subcommand)]
    action: Action,
}

#[derive(Debug, clap::Subcommand)]
enum Action {
    Build {
        /// wether to interactively configure
        #[clap(short, long)]
        clean: bool,
        #[clap(short, long)]
        bundled_initramfs: bool
    },
    Config {
        /// wether to interactively configure
        #[clap(short, long)]
        interactive: bool,
    },
    Noop,
}

fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();

    println!(
        "{} {} {}",
        colorize!("Welcome to", COLOR_WHITE),
        "autokernel".green().bold(),
        colorize!(format!("(v{})", VERSION), COLOR_WHITE)
    );
    println!();

    println!(
        "{} {}",
        colorize!(">> Loading config:", COLOR_MAIN),
        colorize!(args.config.to_string_lossy(), COLOR_MAIN)
    );
    let config = config::load(args.config)?;
    println!();

    println!("{}", colorize!(">> creating bridge", COLOR_MAIN));
    print!("{}", termcolor!(COLOR_VERBOSE));
    let mut bridge = Bridge::new(args.kernel_dir.clone())?;
    println!("\x1b[0m");

    print!("{}", termcolor!(COLOR_VERBOSE));
    println!("{:?}={:?}", bridge.symbols[100].name(), bridge.symbols[100].get_value());
    bridge.symbols[100].set_symbol_value_tristate(Tristate::Yes)?;
    println!(
        "{:?}={:?} (after set)",
        bridge.symbols[100].name(),
        bridge.symbols[100].get_value()
    );
    println!("\x1b[0m");

    match args.action {
        Action::Build { clean, bundled_initramfs } => {
            // let bridge = Bridge::new(kernel_dir)
            // umask 022 // do we want this from the config? or better: detect from the kernel_dir permissions?

            // run make clean, IFF the user specified --clean
            if clean {
                // run "make clean" in the kernel folder
                println!(">> make clean");
                Command::new("make")
                    .arg("clean")
                    .current_dir(&args.kernel_dir)
                    .stderr(Stdio::inherit())
                    .output()
                    .expect("failed to execute make clean");
            }

            /*
             * Setting symbols
             */

            // let kernel_version = bridge.kernel_version();
            // let config_output = args.config_output or args.kernel_dir, '.config.autokernel'

            /*
             * Commandline shenanigans
             */
            // integrate a terminal in the kernel (e.g. only spectre mitigation can be changed
            // here)
            let pos = bridge.get_symbol_pos_by_name("CMDLINE_BOOL").unwrap();
            let sym_cmdline_bool = &mut bridge.symbols[pos];
            println!("{:?}", sym_cmdline_bool.get_value());
            sym_cmdline_bool.set_symbol_value_tristate(Tristate::Yes)?;

            let pos = bridge.get_symbol_pos_by_name("CMDLINE").unwrap();
            let sym_cmdline = &mut bridge.symbols[pos];
            println!("{:?}", sym_cmdline.get_value());
            sym_cmdline.set_symbol_value_string("")?; // TODO set to the proper commandline, this
                                                      // can only be set after the config was built
            // ## Python example from v1
            //
            //def _build_kernel():
            //    # Write configuration to file
            //    kconfig.write_config(
            //            filename=config_output,
            //            header=generated_by_autokernel_header(),
            //            save_old=False)

            //    # Copy file to .config, which may get changed by the makefiles
            //    shutil.copyfile(config_output, os.path.join(args.kernel_dir, '.config'))
            //    # Build the kernel
            //    build_kernel(args)

            //def set_cmdline():
            //    kernel_cmdline_str = ' '.join(kernel_cmdline)

            //    has_user_cmdline_bool = sym_cmdline_bool in autokernel.symbol_tracking.symbol_changes
            //    has_user_cmdline = sym_cmdline in autokernel.symbol_tracking.symbol_changes

            //    if has_user_cmdline_bool and sym_cmdline_bool.str_value == 'n':
            //        # The user has explicitly disabled the builtin commandline,
            //        # so there is no need to set it.
            //        pass
            //    else:
            //        sym_cmdline_bool.set_value('y')

            //        # Issue a warning, if a custom cmdline does not contain "{CMDLINE}", and we have gathered add_cmdline options.
            //        if has_user_cmdline and not sym_cmdline.str_value.contains('{CMDLINE}') and len(kernel_cmdline) > 0:
            //            log.warn("CMDLINE was set manually and doesn't contain a '{CMDLINE}' token, although add_cmdline has also been used.")

            //        if has_user_cmdline:
            //            sym_cmdline.set_value(sym_cmdline.str_value.replace('{CMDLINE}', kernel_cmdline_str))
            //        else:
            //            sym_cmdline.set_value(kernel_cmdline_str)

            //info!("Building kernel");
            //# On the first pass, disable all initramfs sources
            //sym_initramfs_source.set_value('')
            //# Start the build process
            //_build_kernel()


            // TODO execute pre-build hook

            /*
             * Build step
             */
            if bundled_initramfs {
                // TODO
                // three stage build
                // - build without initramfs
                // - build initramfs
                // - build initramfs into kernel

                let pos = bridge.get_symbol_pos_by_name("INITRAMFS_SOURCE").unwrap();
                let sym_initramfs_source = &mut bridge.symbols[pos];
                println!("{:?}", sym_initramfs_source.get_value());
                sym_initramfs_source.set_symbol_value_string("{INITRAMFS}")?;

                let pos = bridge.get_symbol_pos_by_name("MODULES").unwrap();
                let sym_modules = &bridge.symbols[pos];
                println!("{:?}", sym_modules.get_value());
            } else {

            }

            // execute post-build hook
            println!("{}", "Build mode not supported yet".yellow());
        }
        Action::Config { interactive: _ } => {
            println!("{}", "Config mode not supported yet".yellow());
            println!();

            // validate config
            println!(">> {} {}", config.validate(&bridge)?.to_string().green().bold(), colorize!("user-config symbols verified", COLOR_MAIN));
            println!();

            println!("{}\n{}{:?}\x1b[0m",colorize!(">> dumping config", COLOR_MAIN), termcolor!(COLOR_VERBOSE), config.build);
            for (sym, _) in &config.build {
                let pos = bridge.get_symbol_pos_by_name(sym).unwrap();
                println!("defaults: {:?}", bridge.symbols[pos].get_defaults().collect::<Vec<&Tristate>>());

                let s = &mut bridge.symbols[pos];
                println!("{:?}", s.get_value());
                s.set_symbol_value_tristate(Tristate::Yes)?;
                println!("{:?}", s.get_value());
            }
        }
        Action::Noop => {}
    };
    Ok(())
}

// TODO extract into test file (needs lib setup for it)
// TODO use test_env_logger

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
    Command::new("rm").arg(&kernel_tar).current_dir(&tmp).status().unwrap();
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
        .arg(format!("https://cdn.kernel.org/pub/linux/kernel/v5.x/{}", kernel_tar))
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
    //let symbols = bridge::run_bridge(kernel_dir).unwrap();
    let mut bridge = Bridge::new(kernel_dir).unwrap();
    println!("name: {}", bridge.symbols[100].name().unwrap());
    println!("cur_val: {:?}", bridge.symbols[100].get_value());
    println!(
        "defaults: {:?}",
        bridge.symbols[100].get_defaults().collect::<Vec<&Tristate>>()
    );

    bridge.symbols[100].set_symbol_value_tristate(Tristate::Yes).unwrap();
    assert_eq!(
        *bridge.symbols[100].get_value(),
        Tristate::Yes,
        "Setting the symbol failed"
    );

    // remove kernel tar and folder if they already exists
    println!("cleaning up");
    Command::new("rm").arg("-r").arg(&tmp).status().expect("cleanup failed");
}
