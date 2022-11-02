use autokernel::bridge::{Bridge, Symbol};
use rusqlite::Connection;

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

    /// The database to write to
    #[clap(short, long, value_name = "SQLITE_DB", value_hint = clap::ValueHint::FilePath, default_value = "index.db")]
    db: PathBuf,

    #[clap(subcommand)]
    action: Action,
}

#[derive(Debug, clap::Args)]
struct ActionValues {
    /// The name for this configuration
    #[clap(short, long)]
    name: String,

    /// The kconf configuration file to apply before indexing
    #[clap(short, long, value_name = "CONFIG", value_hint = clap::ValueHint::FilePath)]
    kconf: PathBuf,
}

#[derive(Debug, clap::Subcommand)]
enum Action {
    /// Index symbol metadata and default values
    Symbols,
    /// Index symbol values
    Values(ActionValues),
}

fn main() -> Result<()> {
    let args = Args::parse();
    let bridge = Bridge::new(args.kernel_dir.clone())?;

    match &args.action {
        Action::Symbols => {
            index_symbols(&args, &bridge)?;
            index_values(&args, &bridge, "defaults", None)
        }
        Action::Values(action) => index_values(&args, &bridge, &action.name, Some(&action.kconf)),
    }
}

fn init_db(db: &PathBuf) -> Result<Connection> {
    let mut conn = Connection::open(db)?;

    // Create tables
    let tx = conn.transaction()?;
    tx.execute(
        "CREATE TABLE IF NOT EXISTS symbol (
            name             TEXT NOT NULL,
            kernel_version   TEXT NOT NULL,
            type             TEXT NOT NULL,
            visibility_expression TEXT,
            reverse_dependencies  TEXT,
            PRIMARY KEY (name, kernel_version))",
        (), // empty list of parameters.
    )?;
    tx.execute(
        "CREATE TABLE IF NOT EXISTS value (
            symbol           TEXT NOT NULL,
            kernel_version   TEXT NOT NULL,
            config_name      TEXT NOT NULL,
            value            TEXT NOT NULL,
            PRIMARY KEY (symbol, kernel_version, config_name))",
        (), // empty list of parameters.
    )?;

    tx.commit()?;
    Ok(conn)
}

fn is_valid_symbol(symbol: &Symbol) -> bool {
    return !symbol.is_const() && symbol.name().is_some();
}

fn index_symbols(args: &Args, bridge: &Bridge) -> Result<()> {
    print!("{:>12} symbols...\r", "Indexing".cyan());
    io::stdout().flush()?;

    let mut conn = init_db(&args.db)?;
    let time_start = Instant::now();
    let tx = conn.transaction()?;
    let kernel_version = bridge.get_env("KERNELVERSION").unwrap();

    colored::control::set_override(false);
    let mut n_indexed_symbols = 0;
    for symbol in &bridge.symbols {
        let symbol = bridge.wrap_symbol(*symbol);
        if is_valid_symbol(&symbol) {
            n_indexed_symbols += 1;

            tx.execute(
                "INSERT INTO symbol VALUES (?1, ?2, ?3, ?4, ?5)",
                (
                    symbol.name().unwrap().to_string(),
                    &kernel_version,
                    symbol.symbol_type().as_ref(),
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
        "Indexed".green(),
        n_indexed_symbols,
        args.db.display(),
        time_start.elapsed()
    );
    Ok(())
}

fn index_values(args: &Args, bridge: &Bridge, name: &str, kconf: Option<&PathBuf>) -> Result<()> {
    if let Some(kconf) = kconf {
        bridge.read_config_unchecked(kconf)?;
        println!("{:>12} kconf ({})", "Loaded".green(), kconf.display());
    }

    print!("{:>12} symbol values...\r", "Indexing".cyan());
    io::stdout().flush()?;

    let mut conn = init_db(&args.db)?;
    let time_start = Instant::now();
    let tx = conn.transaction()?;
    let kernel_version = bridge.get_env("KERNELVERSION").unwrap();

    let mut n_indexed_symbols = 0;
    for symbol in &bridge.symbols {
        let symbol = bridge.wrap_symbol(*symbol);
        if is_valid_symbol(&symbol) {
            n_indexed_symbols += 1;

            tx.execute(
                "INSERT INTO value VALUES (?1, ?2, ?3, ?4)",
                (
                    symbol.name().unwrap().to_string(),
                    &kernel_version,
                    name,
                    symbol.get_string_value(),
                ),
            )?;
        }
    }
    tx.commit()?;

    println!(
        "{:>12} {} symbol values [{}] to {} in {:.2?}",
        "Indexed".green(),
        n_indexed_symbols,
        name,
        args.db.display(),
        time_start.elapsed()
    );
    Ok(())
}
