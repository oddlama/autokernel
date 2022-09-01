mod bridge;
mod config;

use std::error::Error;

use clap::Parser;
use std::path::PathBuf;

use crate::bridge::{Tristate, Bridge};

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
    Build,
    Config {
        /// wether to interactively configure
        #[clap(short, long)]
        interactive: bool,
    },
    Noop,
}

fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();

    println!("Loading config: {}", args.config.display());
    let _config = config::load(args.config)?;

    let mut bridge = Bridge::new(args.kernel_dir)?;
    println!("{:?}={:?}", bridge.symbols[100].name(), bridge.symbols[100].get_value());
    bridge.symbols[100].set_symbol_value_tristate(Tristate::Yes)?;
    println!("{:?}={:?} (after set)", bridge.symbols[100].name(), bridge.symbols[100].get_value());

    match args.action {
        Action::Build => {
            println!("Build mode not supported yet");

            // let bridge = Bridge::new(kernel_dir)
            // umask 022 // do we want this from the config? or better: detect from the kernel_dir permissions?

            // run make clean, IFF the user specified --clean
            // execute pre-build hook

            // let kernel_version = bridge.kernel_version();
            // let config_output = args.config_output or args.kernel_dir, '.config.autokernel'

            // Load some important symbol values
            // sym_cmdline_bool = kconfig.syms['CMDLINE_BOOL']
            // sym_cmdline = kconfig.syms['CMDLINE']
            // sym_initramfs_source = kconfig.syms['INITRAMFS_SOURCE']
            // sym_modules = kconfig.syms['MODULES']

            // Set some defaults
            // sym_cmdline_bool.set_value('y')
            // sym_cmdline.set_value('')
            // sym_initramfs_source.set_value('{INITRAMFS}')

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

            // execute post-build hook
        }
        Action::Config { interactive: _ } => {
            println!("Config mode not supported yet")
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
    assert_eq!(*bridge.symbols[100].get_value(), Tristate::Yes, "Setting the symbol failed");

    // remove kernel tar and folder if they already exists
    println!("cleaning up");
    Command::new("rm").arg("-r").arg(&tmp).status().expect("cleanup failed");
}
