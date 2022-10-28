use autokernel::bridge::{types::SymbolType, Bridge, Expr, Symbol};
use colored::Colorize;

use std::path::PathBuf;

use anyhow::{Ok, Result};
use clap::Parser;

#[derive(Parser, Debug)]
#[clap(version, about, long_about = None)]
struct Args {
    /// kernel_dir, default /usr/src/linux/
    #[clap(short, long, value_parser, value_name = "DIR", value_hint = clap::ValueHint::DirPath, default_value = "/usr/src/linux/")]
    kernel_dir: PathBuf,

    #[clap(subcommand)]
    action: Action,
}

#[derive(Debug, clap::Args)]
struct ActionAnalyzeConfig {
    /// The output file. Will print to stdout if not given.
    output: Option<PathBuf>,
    /// The configuration file to index
    #[clap(short, long, value_parser, value_name = "DIR", value_hint = clap::ValueHint::FilePath)]
    config: PathBuf,
}

#[derive(Debug, clap::Args)]
struct ActionAnalyzeDefaults {
    /// The output file. Will print to stdout if not given.
    output: Option<PathBuf>,
}

#[derive(Debug, clap::Subcommand)]
enum Action {
    /// Analyze the default symbol values
    AnalyzeConfig(ActionAnalyzeConfig),
    /// Analyze the default symbol values
    AnalyzeDefaults(ActionAnalyzeDefaults),
}

fn main() -> Result<()> {
    let args = Args::parse();
    let bridge = Bridge::new(args.kernel_dir.clone())?;

    match &args.action {
        Action::AnalyzeConfig(action) => analyze_config(&args, &bridge, action),
        Action::AnalyzeDefaults(action) => analyze_defaults(&args, &bridge, action),
    }
}

fn analyze_config(args: &Args, bridge: &Bridge, action: &ActionAnalyzeConfig) -> Result<()> {
    println!("Analyzing config {:?}...", args.kernel_dir);
    Ok(())
}

fn valid_symbol(symbol: &Symbol) -> bool {
    return !symbol.is_const() && symbol.name().is_some();
}

fn dump_symbol(bridge: &Bridge, symbol: &Symbol) {
    println!(
        "{} {:?} {:?}\n  VISIBI: {}\n", //  REVERSE: {}\n  IMPLIED: {}",
        symbol.name().unwrap(),
        symbol.symbol_type(),
        symbol.visible(),
        symbol.visibility_expression().unwrap().display(bridge),
        //symbol.reverse_dependencies().unwrap().display(bridge),
        //symbol.implied().unwrap().display(bridge)
    );
}

fn analyze_defaults(args: &Args, bridge: &Bridge, action: &ActionAnalyzeDefaults) -> Result<()> {
    println!("{:>12} defaults...", "Analyzing".green());
    for symbol in &bridge.symbols {
        let symbol = bridge.wrap_symbol(*symbol);
        if symbol.symbol_type() == SymbolType::Unknown {
            println!("{}", symbol);
        }
        if valid_symbol(&symbol) {}
    }
    Ok(())
}
