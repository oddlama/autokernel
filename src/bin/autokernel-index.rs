use autokernel::bridge::types::SymbolType;
use autokernel::bridge::{Bridge, Symbol};

use std::fs::File;
use std::io::{self, Write};
use std::path::PathBuf;
use std::time::Instant;

use anyhow::{Ok, Result};
use clap::Parser;
use colored::Colorize;
use serde::Serialize;

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
struct ActionAnalyze {
    /// The output file.
    #[clap(value_name = "OUTPUT.csv")]
    output: PathBuf,
    /// The kconf configuration file to apply before analyzing
    #[clap(short, long, value_parser, value_name = "DIR", value_hint = clap::ValueHint::FilePath)]
    kconf: Option<PathBuf>,
}

#[derive(Debug, clap::Subcommand)]
enum Action {
    /// Analyze all symbols and write a summary file
    Analyze(ActionAnalyze),
}

fn main() -> Result<()> {
    let args = Args::parse();
    let bridge = Bridge::new(args.kernel_dir.clone())?;

    match &args.action {
        Action::Analyze(action) => analyze(&args, &bridge, action),
    }
}

fn analyze(_args: &Args, bridge: &Bridge, action: &ActionAnalyze) -> Result<()> {
    if let Some(kconf) = &action.kconf {
        bridge.read_config_unchecked(kconf)?;
    }
    create_analysis(bridge, &action.output)
}

#[derive(Debug, Serialize)]
struct Record {
    symbol: String,
    r#type: SymbolType,
    value: String,
    dependencies: Option<String>,
    reverse_dependencies: Option<String>,
}

fn create_analysis(bridge: &Bridge, output: &PathBuf) -> Result<()> {
    print!("{:>12} symbol values...\r", "Analyzing".cyan());
    io::stdout().flush()?;
    let time_start = Instant::now();
    let mut writer = csv::Writer::from_writer(File::create(output)?);

    fn valid_symbol(symbol: &Symbol) -> bool {
        return !symbol.is_const() && symbol.name().is_some();
    }

    colored::control::set_override(false);
    let mut n_analyzed_symbols = 0;
    for symbol in &bridge.symbols {
        let symbol = bridge.wrap_symbol(*symbol);
        if valid_symbol(&symbol) {
            n_analyzed_symbols += 1;
            writer.serialize(Record {
                symbol: symbol.name().unwrap().to_string(),
                r#type: symbol.symbol_type(),
                value: symbol.get_string_value(),
                dependencies: symbol
                    .visibility_expression_bare()
                    .unwrap()
                    .map(|e| e.display(bridge).to_string()),
                reverse_dependencies: symbol
                    .reverse_dependencies_bare()
                    .unwrap()
                    .map(|e| e.display(bridge).to_string()),
            })?;
        }
    }
    colored::control::unset_override();

    writer.flush()?;
    println!(
        "{:>12} {} symbols to {} in {:.2?}",
        "Analyzed".green(),
        n_analyzed_symbols,
        output.display(),
        time_start.elapsed()
    );
    Ok(())
}
