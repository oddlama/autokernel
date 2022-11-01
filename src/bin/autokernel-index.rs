use autokernel::bridge::{Bridge, Symbol};
use rusqlite::Connection;
use uuid::Uuid;

use std::io::{self, Write};
use std::path::PathBuf;
use std::time::Instant;

use anyhow::{Ok, Result};
use clap::Parser;
use colored::Colorize;

#[derive(Parser, Debug)]
#[clap(version, about, long_about = None)]
struct Args {
    /// The kernel directory
    #[clap(short, long, value_name = "DIR", value_hint = clap::ValueHint::DirPath, default_value = "/usr/src/linux")]
    kernel_dir: PathBuf,

    #[clap(subcommand)]
    action: Action,
}

#[derive(Debug, clap::Args)]
struct ActionAnalyze {
    /// The database to write to
    #[clap(short, long, value_name = "SQLITE_DB", value_hint = clap::ValueHint::FilePath, default_value = "index.db")]
    db: PathBuf,

    /// The name for this configuration
    #[clap(short, long)]
    name: String,

    /// The kconf configuration file to apply before analyzing
    #[clap(short, long, value_name = "DIR", value_hint = clap::ValueHint::FilePath)]
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

fn init_db(db: &PathBuf) -> Result<Connection> {
    let mut conn = Connection::open(db)?;

    // Create tables
    let tx = conn.transaction()?;
    tx.execute(
        "CREATE TABLE IF NOT EXISTS configs (
            id             TEXT PRIMARY KEY NOT NULL,
            name           TEXT NOT NULL,
            arch           TEXT NOT NULL,
            kernel_version TEXT NOT NULL)",
        (), // empty list of parameters.
    )?;
    tx.execute(
        "CREATE TABLE IF NOT EXISTS symbols (
            config           TEXT NOT NULL,
            name             TEXT NOT NULL,
            type             TEXT NOT NULL,
            value            TEXT NOT NULL,
            visibility_expression TEXT,
            reverse_dependencies  TEXT,
            PRIMARY KEY (config, name))",
        (), // empty list of parameters.
    )?;

    tx.commit()?;
    Ok(conn)
}

fn analyze(_args: &Args, bridge: &Bridge, action: &ActionAnalyze) -> Result<()> {
    if let Some(kconf) = &action.kconf {
        bridge.read_config_unchecked(kconf)?;
        println!("{:>12} kconf ({})", "Loaded".green(), kconf.display());
    }

    print!("{:>12} symbol values...\r", "Analyzing".cyan());
    io::stdout().flush()?;

    let mut conn = init_db(&action.db)?;
    let time_start = Instant::now();
    let tx = conn.transaction()?;
    let config_id = Uuid::new_v4().to_string();
    tx.execute(
        "INSERT INTO configs VALUES (?1, ?2, ?3, ?4)",
        (
            &config_id,
            &action.name,
            bridge.get_env("ARCH"),
            bridge.get_env("KERNELVERSION"),
        ),
    )?;

    fn valid_symbol(symbol: &Symbol) -> bool {
        return !symbol.is_const() && symbol.name().is_some();
    }

    colored::control::set_override(false);
    let mut n_analyzed_symbols = 0;
    for symbol in &bridge.symbols {
        let symbol = bridge.wrap_symbol(*symbol);
        if valid_symbol(&symbol) {
            n_analyzed_symbols += 1;

            tx.execute(
                "INSERT INTO symbols VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
                (
                    &config_id,
                    symbol.name().unwrap().to_string(),
                    symbol.symbol_type().as_ref(),
                    symbol.get_string_value(),
                    symbol
                        .visibility_expression_bare()
                        .unwrap()
                        .map(|e| e.display(bridge).to_string()),
                    symbol
                        .reverse_dependencies_bare()
                        .unwrap()
                        .map(|e| e.display(bridge).to_string()),
                ),
            )?;
        }
    }
    colored::control::unset_override();
    tx.commit()?;

    println!(
        "{:>12} {} symbols to {} in {:.2?}",
        "Analyzed".green(),
        n_analyzed_symbols,
        action.db.display(),
        time_start.elapsed()
    );
    Ok(())
}
